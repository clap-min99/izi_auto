"""
예약 실시간 모니터링 시스템 (통합 버전)
- 예약 스크래핑
- 5분마다:
    1) 팝빌 계좌내역 동기화 -> AccountTransaction 저장
    2) DB 기반 입금 매칭/확정 로직 수행
- 선입금 우선 처리
- 충돌 확인 및 처리
"""
import os
import sys
import django
import time
from datetime import datetime, timedelta, date

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from pianos.models import Reservation, AutomationControl
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.sms_sender import SMSSender
from pianos.automation.conflict_checker import ConflictChecker
from pianos.automation.account_sync import AccountSyncManager
from pianos.automation.payment_matcher import PaymentMatcher
from pianos.automation.coupon_manager import CouponManager
from pianos.automation.utils import is_allowed_customer

from django.utils import timezone
# 알림톡(2)
from django.conf import settings
# from pianos.automation.alimtalk_sender import AlimTalkSender


class ReservationMonitor:
    """예약 실시간 모니터링 시스템 (통합)"""

    def __init__(self, naver_url, dry_run=True):
        """
        Args:
            naver_url: 네이버 플레이스 예약 관리 페이지 URL
            dry_run: True이면 DB 업데이트만, 실제 버튼 클릭/문자 발송 안함
        """
        self.naver_url = naver_url
        self.dry_run = dry_run
        self.scraper = NaverPlaceScraper(use_existing_chrome=True, dry_run=dry_run)
        self.sms_sender = SMSSender(dry_run=dry_run)
        # 컴포넌트 초기화
        self.conflict_checker = ConflictChecker(
            dry_run=dry_run,
            scraper=self.scraper,
            sms_sender=self.sms_sender,
            naver_url=self.naver_url,
        )
        
        
        # ✅ PaymentMatcher에 scraper/sms_sender 주입
        self.payment_matcher = PaymentMatcher(
            dry_run=dry_run,
            scraper=self.scraper,
            sms_sender=self.sms_sender,
            naver_url=self.naver_url,   # 복구 때 다시 열 URL
        )

        # 알림톡(1)
        # self.alimtalk_sender = AlimTalkSender()
        self.account_sync = AccountSyncManager(dry_run=dry_run)
        # self.payment_matcher = PaymentMatcher(dry_run=dry_run)
        self.coupon_manager = CouponManager(dry_run=dry_run)

        self._logout_alert_sent = False

        # 이전 예약 리스트 (변경 감지용)
        self.previous_bookings = []
        # 이전 확정대기 개수 (상단 '확정대기 N' 탭의 N 값 추적)
        # self.previous_pending_count = 0
        
        # 계좌 동기화 타이머
        self.last_account_sync = datetime.now()
        self.account_sync_interval = timedelta(minutes=5)

        print(f"🧪 MON.scraper.driver id={id(self.scraper.driver)}")
    
    def refresh_all_coupon_statuses(self):
        from pianos.models import CouponCustomer
        today = timezone.localdate()

        qs = CouponCustomer.objects.all()
        updated = 0

        for customer in qs:
            old_status = customer.coupon_status
            customer.refresh_expiry_status(today=today)
            if customer.coupon_status != old_status:
                updated += 1

        print(f"🎫 쿠폰 상태 일괄 갱신 완료: {updated}건 변경")

    def handle_change_event_if_needed(self, current_bookings):
        """
        ✅ '변경' 배지 예약(B)이 화면에 있고,
        ✅ 그 B가 아직 change_event 처리되지 않은 경우에만,
        -> DB에는 있으나 네이버 리스트에는 없는 (오늘~30일) 예약(A)을 '변경' 처리한다.
        """
        today = timezone.localdate()
        end_date = today + timedelta(days=30)  # 네이버 기본 노출 범위와 동일

        # 이번 사이클 화면에 있는 예약번호 집합
        screen_ids = {
            b.get("naver_booking_id")
            for b in current_bookings
            if b.get("naver_booking_id")
        }
        if not screen_ids:
            return 0

        # 1) 트리거: 화면에 있는 예약 중 '변경 배지' + 아직 처리 안 된 B 존재?
        trigger_qs = Reservation.objects.filter(
            naver_booking_id__in=screen_ids,
            is_change_badge=True,
            is_change_event_handled=False,
        )
        if not trigger_qs.exists():
            return 0

        # 2) 타겟: DB에는 있는데 화면에는 없는 예약(A) (오늘~30일 범위)
        target_qs = (
            Reservation.objects
            .filter(reservation_date__gte=today, reservation_date__lte=end_date)
            .exclude(naver_booking_id__in=screen_ids)
        )
        # (선택) 이미 취소/변경은 건드릴 필요 없으면 제외
        target_qs = target_qs.exclude(reservation_status__in=["취소", "변경"])

        updated = target_qs.update(reservation_status="변경")

        # ✅ 추가: 쿠폰 사용 시간 환불
        for res in target_qs:
            if res.is_coupon:
                refunded = self.coupon_manager.refund_if_confirmed_coupon_canceled(res)
                if refunded:
                    print(f"      ♻️ 쿠폰 환불 완료 (+{res.get_duration_minutes()}분)")

        # 3) 트리거였던 B들 처리완료 표시(재실행 방지)
        trigger_qs.update(is_change_event_handled=True)

        print(f"🔁 예약변경 이벤트 처리: A(누락) {updated}건 → status='변경', B(배지) {trigger_qs.count()}건 handled=True")
        return updated
    # 알림톡(4)
    def _fmt_dt(self, r: Reservation) -> str:
        d = r.reservation_date
        dow = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
        return f"{d.strftime('%Y-%m-%d')}({dow}) {r.start_time.strftime('%H:%M')}~{r.end_time.strftime('%H:%M')}"
    
    # 알림톡, 문자 섞여있음
    def send_owner_request_notification_if_needed(self, reservation: Reservation):
        # 1) 신청 상태만
        if reservation.reservation_status != "신청":
            return

        # 2) 요청사항 없으면 스킵
        request_comment = (reservation.request_comment or "").strip()
        
        if request_comment in ("", "-", "—", "–"):
            return

        # 3) 이미 보냈으면 스킵
        if (reservation.owner_request_noti_status or "전송전") != "전송전":
            return

        owner_phone = getattr(settings, "OWNER_PHONE", "")
        if not owner_phone:
            print("   ⚠️ settings.OWNER_PHONE 없음 → 사장님 알림 스킵")
            return

        content = (
            "예약자가 요청사항을 남겼습니다.\n"
            f"예약자명: {reservation.customer_name}\n"
            f"전화번호: {reservation.phone_number}\n"
            f"예약일시: {self._fmt_dt(reservation)}\n"
            f"요청사항: {request_comment}"
        )

        try:
            # =========================
            # ✅ A안: 알림톡 (승인 나면 이걸 켜)
            # =========================
            # resp = self.alimtalk_sender.send_alimtalk(
            #     to_phone=owner_phone,
            #     template_code="OWNER_RESERVATION_NOTICE",  # 승인된 템플릿 코드로
            #     content=content,
            #     use_sms_failover=False,
            # )
            # ok = (200 <= resp.status_code < 300)

            # =========================
            # ✅ B안: 문자 (지금은 이걸 사용)
            # =========================
            self.sms_sender.send_plain_message(
                to=owner_phone,
                content=content,
                msg_type="사장님 요청사항"
            )
            ok = True

            reservation.owner_request_noti_status = "전송완료" if ok else "전송실패"
            reservation.save(update_fields=["owner_request_noti_status", "updated_at"])

        except Exception as e:
            reservation.owner_request_noti_status = "전송실패"
            reservation.save(update_fields=["owner_request_noti_status", "updated_at"])
            print(f"   ❌ 사장님 요청사항 알림 실패: {e}")


    
    def run(self):
        """메인 루프"""
        print("=" * 60)
        print("🚀 이지피아노스튜디오 예약 자동화 시스템 시작")
        if self.dry_run:
            print("⚠️ DRY_RUN 모드: DB 업데이트 O, '예약확정/예약취소' 버튼·문자 발송 X (탭 이동/체크박스 클릭은 O)")
        print("=" * 60)
        
        # ✅ 모니터 시작 시 쿠폰 상태 전체 동기화
        self.refresh_all_coupon_statuses()
        
        # 초기 페이지 로드
        self.scraper.driver.get(self.naver_url)
        time.sleep(3)
        
        # 초기 예약 리스트 로드
        self.previous_bookings = self.scraper.scrape_all_bookings()
        print(f"📋 초기 예약 리스트: {len(self.previous_bookings)}건")

        # 초기 예약들을 DB와 동기화
        self.sync_initial_bookings_to_db()
        
        # 초기 계좌 내역 동기화
        print(f"\n{'='*60}")
        print("💳 초기 계좌 내역 동기화")
        print(f"{'='*60}")
        self.account_sync.sync_transactions(initial=True)
        
        # 메인 루프
        cycle_count = 0
        while True:
            try:
                # ✅ 자동화 OFF면 아무 것도 하지 않고 대기
                ctrl = AutomationControl.objects.filter(id=1).first()
                if not ctrl or not ctrl.enabled:
                    time.sleep(5)
                    continue
                if self.scraper.is_logged_out():
                    if not self._logout_alert_sent:
                        self._logout_alert_sent = True

                        owner_phone = getattr(settings, "OWNER_PHONE", "")
                        msg = (
                            "네이버 로그아웃/세션만료 감지\n"
                            "자동화가 일시 중단되었습니다.\n"
                            "PC에서 네이버 예약관리 페이지 재로그인 후 다시 확인해주세요."
                        )

                        try:
                            if owner_phone:
                                self.sms_sender.send_plain_message(
                                    to=owner_phone,
                                    content=msg,
                                    msg_type="네이버 로그아웃"
                                )
                            print("🚨 로그아웃 알림 발송 + 자동화 일시 중단")
                        except Exception as e:
                            print(f"🚨 로그아웃 알림 발송 실패: {e}")

                    # 🔒 자동화 중단: 재로그인까지 계속 대기 (클릭/확정/취소 금지)
                    time.sleep(10)
                    continue
                else:
                    # 로그인 상태로 돌아오면 다시 알림 가능하게 리셋
                    if self._logout_alert_sent:
                        print("✅ 네이버 로그인 상태 복구 감지")
                    self._logout_alert_sent = False
                current_time = datetime.now()
                cycle_count += 1
                
                # # =========================
                # # ✅ 테스트용: 시작 60초 후 새 탭 강제 오픈 (한 번만)
                # # =========================
                # if not self._test_tab_opened and (time.time() - self._started_at_ts) >= 60:
                #     print("🧪 테스트: 60초 경과 → 새 창으로 예약 페이지 재오픈 시도")
                #     self.scraper.reopen_reservation_tab(
                #         self.naver_url,
                #         close_old=True,     # ✅ 눈으로 확인 확실
                #         as_window=True      # ✅ 새 창으로 띄움
                #     )
                #     self._test_tab_opened = True
                

                # ✅ [여기] 30분 경과 입금대기 자동취소
                did_actions = False
                did_actions |= self.cancel_expired_pending_deposits()
                
                # ★ 1. 5분마다 계좌 내역 동기화
                if current_time - self.last_account_sync >= self.account_sync_interval:
                    print(f"\n{'='*60}")
                    print(f"💳 계좌 내역 동기화 (5분 주기) - {current_time.strftime('%H:%M:%S')}")
                    print(f"{'='*60}")
                    ok, new_cnt = self.account_sync.sync_transactions()   # 👈 여기 바뀜

                    if ok:  
                        self.last_account_sync = current_time
                    else:
                        self.last_account_sync = current_time - (self.account_sync_interval - timedelta(seconds=60))
                        print("   🔁 계좌 동기화 실패 → 60초 후 재시도")

                # =========================
                # ✅ 세션/화면 이상 감지 → 새 창으로 복구 (실전)
                # =========================
                if self.scraper._looks_like_logged_out():
                    print("⚠️ 세션 만료/로그아웃/화면이상 감지 → 새 창으로 복구")
                    self.scraper.reopen_reservation_tab(
                        self.naver_url,
                        close_old=True,    # 문제창 닫아버리기 (꼬임 방지)
                        as_window=True     # 새 창으로 확실히 띄우기
                    )
                    continue  # ✅ 복구한 사이클은 건너뛰고 다음 사이클에서 안정적으로 진행


                # 2. 예약 리스트 스크래핑 (기본 예약리스트 탭 기준)
                current_bookings = self.scraper.scrape_all_bookings()
                
                # 3. 새로운 예약 확인
                new_bookings = self.find_new_bookings(current_bookings)

                # ---- (A) 새 예약 처리 파트 직전에 플래그 추가 ----

                # ★ 새 예약이 있을 때만 상세 로그
                if new_bookings:
                    print(f"\n{'='*60}")
                    print(f"🔔 사이클 #{cycle_count} - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"{'='*60}")
                    print(f"   📋 현재 예약 리스트: {len(current_bookings)}건")
                    print(f"\n{'─'*60}")
                    print(f"✨ 새 예약 {len(new_bookings)}건 발견!")
                    print(f"{'─'*60}")
                    did_actions |= self.handle_new_bookings(new_bookings)  # ✅ 여기서 bool 받기
                    
                    # 기존 예약 상태 변경 확인
                    print(f"\n{'─'*60}")
                    print("🔄 예약 상태 변경 확인")
                    print(f"{'─'*60}")
                # else:
                #     # 새 예약 없을 때는 간단한 로그만
                #     if cycle_count % 6 == 0:  # 1분마다 (10초 * 6)
                #         print(f"[{current_time.strftime('%H:%M:%S')}] ⏳ 대기 중... (예약: {len(current_bookings)}건)")
                #         # 새 예약 없을 때만 상태 동기화(스냅샷 신뢰 가능)
                #         self.update_existing_bookings(current_bookings)
                
                # ★ 4. 입금 확인 (새 예약이 있을 때만 상세 로그)
                # ---- (B) 입금 확인 파트에서 "조작 발생 가능"을 did_actions에 반영 ----
                handled = False

                if new_bookings:
                    did_conflict_actions = self.payment_matcher.handle_first_payment_wins()  # True/False
                    handled |= did_conflict_actions

                    # ✅ 선입금 로직에서 확정/취소가 일어났으면 같은 사이클에 check_pending_payments를 돌리지 않음
                    if not did_conflict_actions:
                        confirmed_cnt = self.payment_matcher.check_pending_payments()
                        handled |= (confirmed_cnt > 0)
                else:
                    self._silent_payment_check()

                did_actions |= handled

                if handled :
                    self.scraper.refresh_page()
                    time.sleep(2)
                    self.scraper.scroll_booking_list_to_bottom()
                    # 이 사이클에서는 추가 입금/확정 로직 금지
                    continue
                
                # ---- (C) ✅ 조작이 있었으면 fresh scrape로 동기화 + previous 갱신 ----
                if did_actions:
                    # 네이버 화면은 이미 내부에서 refresh가 일어났을 수 있으니, 여기서 확실히 최신화
                    self.scraper.refresh_page()
                    time.sleep(2)

                    fresh_bookings = self.scraper.scrape_all_bookings()

                    # ✅ (핵심) 화면 조작 중간에 들어온 예약이 있으면 여기서 추가 처리
                    while True:
                        missed_new = self.find_new_bookings(fresh_bookings)
                        if not missed_new:    # 더 이상 신규 예약이 없으면 루프 종료
                            break
                        print(f"🧷 조작 중 유입된 새 예약 {len(missed_new)}건 추가 처리")
                        did_actions |= self.handle_new_bookings(missed_new)
                        self.scraper.refresh_page()
                        time.sleep(2)
                        fresh_bookings = self.scraper.scrape_all_bookings()

                    # ✅ 최신 스냅샷으로 DB 상태 동기화
                    self.update_existing_bookings(fresh_bookings)
                    self.handle_change_event_if_needed(fresh_bookings)

                    # ✅ previous도 최신 스냅샷으로 저장 (중요)
                    self.previous_bookings = fresh_bookings
                else:
                    # ✅ 이건 “상태동기화는 매 사이클”로 바꾸는 걸 추천
                    self.update_existing_bookings(current_bookings)
                    self.handle_change_event_if_needed(current_bookings)
                    self.previous_bookings = current_bookings
                    self.scraper.refresh_page()

                time.sleep(3)
                
            except KeyboardInterrupt:
                print("\n\n⏹️ 사용자에 의해 중단됨")
                break
            except Exception as e:
                print(f"\n❌ 모니터링 오류: {e}")
                import traceback
                traceback.print_exc()

                recovered = False

                try:
                    msg = str(e)
                    if (
                        ("NewConnectionError" in msg) or
                        ("HTTPConnectionPool" in msg) or
                        ("WinError 10061" in msg) or
                        ("no such window" in msg) or
                        ("web view not found" in msg)
                    ):
                        print("🧯 드라이버 통신 오류 감지 → 새 창 복구 시도")
                        self.scraper.reopen_reservation_tab(
                            self.naver_url,
                            close_old=True,
                            as_window=True
                        )
                        recovered = True
                except Exception:
                    pass

                if recovered:
                    print("🔄 복구 완료 → 다음 사이클에서 재개")
                    time.sleep(2)
                    continue   # ✅ 이게 핵심 (같은 사이클 이어가지 않음)

                print("\n⏰ 10초 후 재시도...")
                time.sleep(10)
        
        self.scraper.close()
        print("\n🔚 시스템 종료")

    def cancel_expired_pending_deposits(self):
        """
        created_at 기준 30분 동안 입금이 확인되지 않은 '입금대기' 예약 자동 취소
        - 대상: 일반예약(쿠폰 X) + 신청 + 계좌안내 문자 전송완료
        - 네이버 화면 범위(오늘~한달) 안의 예약일만 취소 시도
        """
        now = timezone.now()
        # 입금 대기 시간 조정 현재 30분
        cutoff = now - timedelta(minutes=30)

        today = timezone.localdate()
        end_date = today + timedelta(days=30)  # 네이버 필터와 동일하게

        qs = Reservation.objects.filter(
            reservation_status="신청",
            is_coupon=False,
            account_sms_status="전송완료",
            created_at__lte=cutoff,
            reservation_date__gte=today,
            reservation_date__lte=end_date,
        ).order_by("created_at")

        if not qs.exists():
            return False

        print(f"⏰ 30분 경과 입금대기 자동취소 대상: {qs.count()}건")
        did_actions = False

        for r in qs:
            reason = "입금 기한(30분) 초과로 자동 취소되었습니다."

            # 1) 네이버 취소(실제 실행)
            if not self.dry_run:
                ok = self.scraper.cancel_in_pending_tab(r.naver_booking_id, reason=reason)
                if not ok:
                    print(f"   ⚠️ 네이버 취소 실패: {r.naver_booking_id} ({r.customer_name})")
                    continue
            else:
                print(f"   [DRY_RUN] 네이버 취소 시뮬레이션: {r.naver_booking_id} ({r.customer_name})")

            # 이번 사이클에 '화면 조작이 있었다' 표시
            did_actions = True

            # 2) DB 취소 반영
            r.reservation_status = "취소"
            # cancel_reason 같은 필드가 있으면 같이 저장 (필드명 다르면 이 부분만 맞춰)
            if hasattr(r, "cancel_reason"):
                r.cancel_reason = reason
            r.save(update_fields=["reservation_status", "updated_at"] + (["cancel_reason"] if hasattr(r, "cancel_reason") else []))

            # 3) 취소 문자 1회 발송
            self.sms_sender.send_cancel_message(r, reason)

            # (선택) cancel_sms_status 같은 게 있으면 찍기
            if hasattr(r, "cancel_sms_status"):
                r.cancel_sms_status = "전송완료"
                r.save(update_fields=["cancel_sms_status", "updated_at"])

        return did_actions
    
    def _silent_payment_check(self):
        """
        입금 확인을 조용히 실행 (로그 최소화)
        """
        try:
            from pianos.models import Reservation

            pending_qs = Reservation.objects.filter(
                reservation_status='신청',
                is_coupon=False,
                account_sms_status='전송완료'
            )

            pending_count = pending_qs.count()

            # 👉 입금 대기 예약이 없으면 아무 것도 안 함
            if pending_count == 0:
                return

            # 최소한의 로그
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💰 입금 확인 (대기 {pending_count}건)")

            # 입금 확인 및 선입금 우선 처리
            did_conflict_actions = self.payment_matcher.handle_first_payment_wins()
            if not did_conflict_actions:
                self.payment_matcher.check_pending_payments()

        except Exception as e:
            print(f"⚠️ 조용한 입금 확인 중 오류: {e}")

    def find_new_bookings(self, current_bookings):
        previous_ids = {b['naver_booking_id'] for b in self.previous_bookings}

        candidates = [
            b for b in current_bookings
            if b['naver_booking_id'] not in previous_ids
        ]

        # ✅ DB에도 없는 것만 "진짜 새 예약"
        candidate_ids = [b['naver_booking_id'] for b in candidates]
        existing_ids = set(
            Reservation.objects.filter(naver_booking_id__in=candidate_ids)
            .values_list('naver_booking_id', flat=True)
        )

        new_bookings = [b for b in candidates if b['naver_booking_id'] not in existing_ids]
        return new_bookings

    def sync_initial_bookings_to_db(self):
        """
        모니터링 시작 시 네이버에 이미 떠 있던 예약들을 DB와 동기화한다.
        (이미 DB에 같은 네이버 예약 ID가 있으면 건너뜀)
        """
        print("\n📌 초기 예약 DB 동기화 시작")

        from django.db import transaction

        with transaction.atomic():
            for booking in self.previous_bookings:
                try:
                    if Reservation.objects.filter(
                        naver_booking_id=booking['naver_booking_id']
                    ).exists():
                        continue

                    status = booking.get('reservation_status', '신청')
                    self.save_booking_to_db(booking, status=status)

                except Exception as e:
                    print(f"   ⚠️ 초기 예약 저장 중 오류: {e}")
                    import traceback
                    traceback.print_exc()

        print("📌 초기 예약 DB 동기화 완료")
        
        
    def handle_new_bookings(self, new_bookings):
        """
        새 예약 처리
        """
        did_actions = False

        for booking in new_bookings:
            try:
                # 네이버 상태 먼저 읽기
                naver_status = booking.get('reservation_status')

                # DB 저장은 무조건 한다
                reservation = self.save_booking_to_db(booking, status=naver_status)

                # 자동 처리 허용 상태는 오직 '신청'만
                if naver_status != '신청':
                    print(
                        f"      ⏭️ 상태={naver_status} 예약 - DB만 저장하고 자동 처리 스킵 "
                        f"({reservation.naver_booking_id})"
                    )
                    continue
                # 테스트 박수민,하건수
                # 테스트 대상 아니면 자동 처리 스킵 (DB는 이미 저장됨)
                if not is_allowed_customer(booking.get("customer_name")):
                    print("      🛡️ 안전모드: 테스트 대상 아님 → 자동 처리 스킵")
                    continue

                # ✅ 요청사항 알림(즉시 전송)
                self.send_owner_request_notification_if_needed(reservation)

                print(f"\n   📝 새 예약 처리: {booking['customer_name']} | {booking['room_name']}")
                print(f"      - 네이버 ID: {booking['naver_booking_id']}")
                print(f"      - 예약 시간: {booking['reservation_date']} {booking['start_time']}~{booking['end_time']}")
                print(f"      - 요금: {booking['price']:,}원")
                print(f"      - 쿠폰: {'O' if booking['is_coupon'] else 'X'}")
                
                # 1. 충돌 확인
                conflict_result = self.conflict_checker.check_and_handle_conflicts(booking)
                
                if conflict_result['action'] == 'cancel':
                    reason = conflict_result['message']  # ✅ 충돌 사유 그대로 사용
                    # 충돌로 인한 취소
                    print(f"      ❌ 충돌로 인한 취소: {conflict_result['message']}")
                    #### 테스트 박수민, 하건수
                    # DB에는 저장(취소로)만 해두고,
                    reservation = self.save_booking_to_db(booking, status='취소')

                    if not self.dry_run:
                        ok = self.scraper.cancel_in_pending_tab(booking['naver_booking_id'], reason=reason)
                        did_actions |= bool(ok)   # ✅ 취소 성공했으면 조작 발생 True
                    else:
                        print(f"      [DRY_RUN] 네이버 취소 시뮬레이션")
                    # 취소 문자
                    self.sms_sender.send_cancel_message(reservation, reason)
                    continue
                
                # 3. 쿠폰/일반 처리 딱 1번만 실행
                if booking['is_coupon']:
                    success = bool(self.handle_coupon_booking(reservation, booking))  # ✅ 한 번만

                else:
                    success = bool(self.handle_general_booking(reservation, booking))  # ✅ 한 번만

                did_actions |= success  # ✅ 조작 발생 여부 반영

                # 4. (쿠폰 성공 시에만) defer_cancel 처리
                if booking['is_coupon']:
                    if success and conflict_result.get('action') == 'defer_cancel_until_coupon_confirmed':
                        for target in conflict_result.get('cancel_targets', []):
                            self.conflict_checker._cancel_reservation(
                                target,
                                reason="쿠폰 예약과 시간대 충돌"
                            )
                    
            except Exception as e:
                print(f"   ❌ 예약 처리 오류: {e}")
                import traceback
                traceback.print_exc()
        return did_actions

    def handle_general_booking(self, reservation, booking):
        """
        일반(입금) 예약 처리
        1. 계좌 문자 발송
        2. 입금 대기
        """
        try:
            print(f"      💳 일반 예약 처리")
            # 테스트 박수민, 하건수
            allowed = is_allowed_customer(reservation.customer_name)
            if not allowed:
                print(f"      🛡️ 안전모드: '{reservation.customer_name}' 계좌문자/클릭 스킵")
                return False
            
            # 1. 계좌 안내 문자 발송 (Reservation 객체 기준)
            self.sms_sender.send_account_message(reservation)
            
            # 2) 문자 발송 상태 DB 반영
            reservation.account_sms_status = '전송완료'
            reservation.save(update_fields=['account_sms_status', 'updated_at'])
            print(f"      💬 입금 안내 문자 발송 완료")
            return False  # ✅ 네이버 확정/취소 조작 없음
            
        except Exception as e:
            print(f"      ❌ 일반 예약 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def handle_coupon_booking(self, reservation, booking):
        """
        쿠폰 예약 처리 (쿠폰 로직은 CouponManager로 통일)
        - check_balance로 가능/불가 + 사유 획득
        - 가능하면 confirm_and_deduct로 확정/차감/이력/DB업데이트까지 일괄 처리
        - 불가면 _cancel_coupon_booking로 취소
        """
        allowed = is_allowed_customer(reservation.customer_name)
        if not allowed:
            print(f"      🛡️ 안전모드: '{reservation.customer_name}' 쿠폰 확정/취소/문자 스킵 (DB 기록만)")
            return False
        print(f"      🎫 쿠폰 예약 처리 시작")
        if reservation.is_change_badge:
            original_res = Reservation.objects.filter(
                phone_number=reservation.phone_number,
                reservation_status='확정',
                is_coupon=True,
                is_change_badge=False
            ).exclude(naver_booking_id=reservation.naver_booking_id).first()

            if original_res:
                self.coupon_manager.refund_if_confirmed_coupon_canceled(original_res)
                original_res.reservation_status = '변경'
                original_res.save(update_fields=['reservation_status', 'updated_at'])
                print(f"   🔄 기존 예약 쿠폰 환불 처리: {original_res.naver_booking_id}")

        # ✅ 잔여 시간 확인 후 충분하면 차감, 부족하면 자동 취소
        ok, customer, reason = self.coupon_manager.check_balance(reservation)

        if not ok:
            print(f"      ❌ 쿠폰 처리 불가 → 취소 ({reason})")
            self._cancel_coupon_booking(reservation, reason, customer=customer)
            return True   # ✅ (취소 시도) = 네이버 조작 의도/발생

        print("      ✅ 쿠폰 조건 통과 → 즉시 확정/차감 진행")
        success = self.coupon_manager.confirm_and_deduct(
            reservation=reservation,
            customer=customer,
            scraper=self.scraper
        )

        if success:
            print("      ✅ 쿠폰 예약 확정/차감 완료")

            # ✅ 기본값: 쿠폰예약은 확정 문자 안 보냄
            complete_status = "쿠폰예약"

            # ✅ 단, 입시기간(날짜+시간대 겹침) 예약이면 20분내 취소 안내 문자 발송
            if self.sms_sender._is_exam_period(reservation):
                ok_sms = self.sms_sender.send_coupon_confirm_message(reservation)
                complete_status = "전송완료" if ok_sms else "전송실패(쿠폰입시)"
                print(f"      📩 쿠폰 입시기간 확정 문자: {'성공' if ok_sms else '실패'}")
            else:
                print("      ℹ️ 쿠폰 확정 문자 스킵(입시기간 아님)")

            reservation.complete_sms_status = complete_status
            reservation.save(update_fields=["complete_sms_status", "updated_at"])

            return True
        
        print("      ❌ 쿠폰 확정 실패 → 취소")
        self._cancel_coupon_booking(reservation, "쿠폰 확정 처리 실패")
        return True      # ✅ 취소 조작 발생
    
    def _cancel_coupon_booking(self, reservation, reason, customer=None):
        """쿠폰 예약 취소 처리"""
        try:
            # 네이버 취소
            if not self.dry_run:
                self.scraper.cancel_in_pending_tab(reservation.naver_booking_id, reason=reason)
            else:
                print(f"      [DRY_RUN] 네이버 취소 시뮬레이션")
            
            # DB 상태 변경
            reservation.reservation_status = '취소'
            reservation.save()
            
            # 취소 문자
            self.sms_sender.send_cancel_message(reservation, reason, customer=customer)
            
            print(f"      ✅ 쿠폰 예약 취소 완료 ({reason})")
            
        except Exception as e:
            print(f"      ❌ 쿠폰 취소 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def save_booking_to_db(self, booking, status='신청'):
        reservation, created = Reservation.objects.update_or_create(
            naver_booking_id=booking['naver_booking_id'],
            defaults={
                'customer_name': booking['customer_name'],
                'phone_number': booking['phone_number'],
                'room_name': booking['room_name'],
                'reservation_date': booking['reservation_date'],
                'start_time': booking['start_time'],
                'end_time': booking['end_time'],
                'price': booking['price'],
                'is_coupon': booking['is_coupon'],
                'reservation_status': status,
                'extra_people_qty': booking.get('extra_people_qty', 0),
                'is_proxy': booking.get('is_proxy', False),
                "request_comment": booking.get("request_comment", ""),
                # 이미 저장된 데이터라면 문자상태 덮어쓰지 않게 주의!
                # 처음 생성일 때만 기본값 넣고 싶으면 아래처럼 분기 권장
                "is_change_badge": booking.get("is_change_badge", False),
            }
        )

        if created:
            reservation.account_sms_status = '전송전'
            reservation.complete_sms_status = '입금확인전'
            reservation.save(update_fields=['account_sms_status', 'complete_sms_status', 'updated_at'])

        return reservation
    
    def update_existing_bookings(self, current_bookings):
        """
        기존 예약의 상태 변경 확인 (네이버에서 직접 처리된 경우)
        """
        updated_count = 0
        
        for booking in current_bookings:
            try:
                # DB에서 해당 예약 찾기
                reservation = Reservation.objects.filter(
                    naver_booking_id=booking['naver_booking_id']
                ).first()
                
                if not reservation:
                    continue
                
                # 네이버 상태
                naver_status = booking.get('reservation_status')
                
                if not naver_status:
                    continue
                
                # 상태가 다르면 업데이트
                old_status = reservation.reservation_status

                if old_status != naver_status:
                    # ✅ 역방향 방지
                    if old_status in ('확정', '취소') and naver_status == '신청':
                        print(f"   🛡️ 역변경 방지: {reservation.naver_booking_id} ({old_status} -> 신청) 스킵")
                        continue

                    print(f"   🔁 상태 변경 감지: {reservation.naver_booking_id}")
                    print(f"      - {old_status} → {naver_status}")

                    # ✅ (추가) 쿠폰 예약 확정 → 취소이면 쿠폰 환불
                    if old_status == '확정' and naver_status == '취소' and reservation.is_coupon:
                        refunded = self.coupon_manager.refund_if_confirmed_coupon_canceled(reservation)
                        if refunded:
                            print(f"      ♻️ 쿠폰 환불 처리 완료 (+{reservation.get_duration_minutes()}분)")

                    reservation.reservation_status = naver_status
                    reservation.save(update_fields=['reservation_status', 'updated_at'])
                    updated_count += 1
                    
            except Exception as e:
                print(f"   ❌ 상태 업데이트 오류: {e}")
                continue
        
        if updated_count > 0:
            print(f"   ✅ 상태 변경: {updated_count}건")
        else:
            print(f"   ℹ️ 상태 변경 없음")

    

# class BankSyncAndMatchMonitor:
#     def __init__(self, dry_run: bool = False, interval_sec: int = 300):
#         self.dry_run = dry_run
#         self.interval_sec = interval_sec

#         self.sync_manager = AccountSyncManager(dry_run=dry_run)
#         self.matcher = PaymentMatcher(dry_run=dry_run)

#         self.next_run_at = timezone.now()

#     def run_forever(self):
#         print("🚀 BankSyncAndMatchMonitor 시작")
#         print(f"   - interval: {self.interval_sec}s (5분이면 300)")
#         print(f"   - dry_run: {self.dry_run}")

#         while True:
#             now = timezone.now()
#             if now >= self.next_run_at:
#                 self.run_once()
#                 self.next_run_at = now + timedelta(seconds=self.interval_sec)

#             time.sleep(1)

    # def run_once(self):
    #     # 1) 계좌 동기화
    #     new_cnt = self.sync_manager.sync_transactions(lookback_days=2)

    #     # 2) 매칭/확정 로직
    #     # 신규 거래가 있을 때만 돌리고 싶으면 if new_cnt > 0: 로 감싸셔도 됩니다.
    #     self.matcher.check_pending_payments()
    #     self.matcher.handle_first_payment_wins()

def main():
    # 네이버 예약 관리 페이지 URL
    NAVER_URL = os.getenv('NAVER_RESERVATION_URL', '')
    
    # DRY_RUN 모드로 실행
    monitor = ReservationMonitor(
        naver_url=NAVER_URL,
        dry_run=False
    )
    
    monitor.run()


if __name__ == "__main__":
    main()
