"""
계좌 내역 동기화 (팝빌 EasyFinBank)
- 5분 주기로 최신 거래 내역을 DB(AccountTransaction)에 저장
- requestJob -> getJobState(완료/성공 확인) -> search
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from popbill import EasyFinBankService, PopbillException  # pip install popbill

from pianos.models import AccountTransaction


@dataclass(frozen=True)
class PopbillConfig:
    link_id: str
    secret_key: str
    corp_num: str          # 사업자번호(10자리, '-' 제외)
    user_id: str           # 팝빌 회원 아이디
    bank_code: str         # 은행 기관코드 (팝빌 문서 기준)
    account_number: str    # 계좌번호
    is_test: bool = False
    ip_restrict: bool = True
    use_static_ip: bool = False
    use_local_time: bool = True


class AccountSyncManager:
    """계좌 내역 동기화 매니저"""

    def __init__(self, dry_run: bool = False, cfg: Optional[PopbillConfig] = None):
        self.dry_run = dry_run
        self.cfg = cfg or self._load_cfg_from_settings()
        self.svc = self._build_service(self.cfg)

    def _load_cfg_from_settings(self) -> PopbillConfig:
        return PopbillConfig(
            link_id=getattr(settings, "POPBILL_LINK_ID"),
            secret_key=getattr(settings, "POPBILL_SECRET_KEY"),
            corp_num=getattr(settings, "POPBILL_CORP_NUM"),
            user_id=getattr(settings, "POPBILL_USER_ID"),
            bank_code=getattr(settings, "POPBILL_BANK_CODE"),
            account_number=getattr(settings, "POPBILL_ACCOUNT_NUMBER"),
            is_test=getattr(settings, "POPBILL_IS_TEST", False),
            ip_restrict=getattr(settings, "POPBILL_IP_RESTRICT", True),
            use_static_ip=getattr(settings, "POPBILL_USE_STATIC_IP", False),
            use_local_time=getattr(settings, "POPBILL_USE_LOCAL_TIME", True),
        )

    def _build_service(self, cfg: PopbillConfig) -> EasyFinBankService:
        svc = EasyFinBankService(cfg.link_id, cfg.secret_key)
        svc.IsTest = cfg.is_test
        svc.IPRestrictOnOff = cfg.ip_restrict
        svc.UseStaticIP = cfg.use_static_ip
        svc.UseLocalTimeYN = cfg.use_local_time
        return svc
    
    @staticmethod
    def parse_depositor_name(memo: str) -> str:
        if not memo:
            return ""
        return memo.split("|", 1)[0].strip()

    def sync_transactions(self, lookback_days: int = 2, initial: bool = False) -> int:
        """
        팝빌에서 거래내역을 가져와 DB 저장.
        - lookback_days: 5분 주기라도 은행 반영 지연/재수집 대비로 1~2일 겹쳐 조회 추천
        """
        now = timezone.now()
        print(f"[{now:%Y-%m-%d %H:%M:%S}] 💳 계좌 내역 동기화 시작...")

        if self.dry_run:
            print("   [DRY_RUN] 팝빌 호출/DB저장 생략")
            return 0

        try:
            items = self._fetch_from_popbill(lookback_days=lookback_days)
            if not items:
                print("   ℹ️ 새로운(또는 미저장) 거래 내역 없음")
                return 0

            new_count = self._save_transactions(items, initial=initial)
            print(f"   ✅ 신규 저장: {new_count}건")
            return new_count

        except PopbillException as e:
            print(f"   ❌ 팝빌 오류 [{e.code}] {e.message}")
            return 0
        except Exception as e:
            print(f"   ❌ 동기화 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0

    # -----------------------
    # Popbill fetch pipeline
    # -----------------------

    def _fetch_from_popbill(self, lookback_days: int) -> List[Dict[str, Any]]:
        """
        requestJob -> getJobState(완료/성공) -> search
        반환은 AccountTransaction 저장에 필요한 dict list로 변환해서 반환.
        """
        # requestJob은 날짜 범위만 받는 경우가 많아서, lookback으로 겹치게 잡습니다.
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=lookback_days)
        sdate = start_date.strftime("%Y%m%d")
        edate = end_date.strftime("%Y%m%d")

        # 1) 수집 요청
        job_id = self.svc.requestJob(
            self.cfg.corp_num,
            self.cfg.bank_code,
            self.cfg.account_number,
            sdate,
            edate,
            self.cfg.user_id,
        )

        # 2) 수집 상태 확인
        state = self._wait_job_done(job_id, timeout_sec=25, interval_sec=2)
        if not state:
            return []

        if str(getattr(state, "jobState", "")) != "3" or int(getattr(state, "errorCode", 0)) != 1:
            print(
                f"   ⚠️ 수집 미완료/실패: jobState={getattr(state,'jobState',None)}, "
                f"errorCode={getattr(state,'errorCode',None)}"
            )
            print(f"      reason={getattr(state,'errorReason','')}")
            return []

        # 3) 거래내역 조회(Search) - 입금만
        result = self.svc.search(
            self.cfg.corp_num,
            job_id,
            ["I"],   # 입금만
            "",      # SearchString
            1,       # Page
            1000,    # PerPage
            "D",     # Order: 최신순
            self.cfg.user_id,
        )

        rows: List[Dict[str, Any]] = []
        for d in getattr(result, "list", []) or []:
            tid = (getattr(d, "tid", "") or "").strip()
            trdt = (getattr(d, "trdt", "") or "").strip()  # yyyyMMddHHmmss
            acc_in = (getattr(d, "accIn", "0") or "0").replace(",", "").strip()
            bal = (getattr(d, "balance", "0") or "0").replace(",", "").strip()

            if not tid or not trdt:
                continue

            dt = datetime.strptime(trdt, "%Y%m%d%H%M%S")
            aware_dt = timezone.make_aware(dt) if timezone.is_naive(dt) else dt

            amount_in = int(acc_in) if acc_in.isdigit() else 0
            balance = int(bal) if bal.isdigit() else 0

            if amount_in <= 0:
                continue

            # remark1~4를 memo로 저장 (입금자명은 은행별 포맷 차이가 있어서 1차는 비움)
            memo_parts = [
                getattr(d, "remark1", "") or "",
                getattr(d, "remark2", "") or "",
                getattr(d, "remark3", "") or "",
                getattr(d, "remark4", "") or "",
            ]
            memo = " | ".join([p.strip() for p in memo_parts if p and p.strip()])
            depositor = self.parse_depositor_name(memo)

            rows.append({
                "transaction_id": tid,                         # 모델: transaction_id
                "transaction_date": aware_dt.date(),            # 모델: transaction_date
                "transaction_time": aware_dt.time(),            # 모델: transaction_time
                "transaction_type": "입금",                    # 모델: transaction_type
                "amount": amount_in,                            # 모델: amount
                "balance": balance,                             # 모델: balance
                "depositor_name": depositor,                           # 모델: depositor_name
                "memo": memo,                                   # 모델: memo
            })

        return rows

    def _wait_job_done(self, job_id: str, timeout_sec: int = 25, interval_sec: int = 2):
        deadline = time.time() + timeout_sec
        last_state = None

        while time.time() < deadline:
            st = self.svc.getJobState(self.cfg.corp_num, job_id, self.cfg.user_id)
            last_state = st
            if str(getattr(st, "jobState", "")) == "3":
                return st
            time.sleep(interval_sec)

        print("   ⚠️ getJobState timeout (다음 주기에 다시 조회합니다)")
        return last_state

    # -----------------------
    # DB save
    # -----------------------

    def _save_transactions(self, items: List[Dict[str, Any]], initial: bool = False) -> int:
        """
        AccountTransaction 모델에 맞게 저장(get_or_create로 중복 제거).
        """
        new_count = 0
        status = "확정완료" if initial else "확정전"
        
        with db_transaction.atomic():
            for it in items:
                obj, created = AccountTransaction.objects.get_or_create(
                    transaction_id=it["transaction_id"],
                    defaults={
                        "transaction_date": it["transaction_date"],
                        "transaction_time": it["transaction_time"],
                        "transaction_type": it["transaction_type"],
                        "amount": it["amount"],
                        "balance": it["balance"],
                        "depositor_name": it["depositor_name"],
                        "memo": it["memo"],
                        "match_status": status,
                    },
                )

                if created:
                    new_count += 1
                    print(f"      ➕ 입금 | {it['amount']:,}원 | {it['memo'][:70]}")

        return new_count
