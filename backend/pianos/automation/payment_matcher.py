"""
입금 확인 및 예약 매칭 (계좌 내역 DB 기반)
"""
import os
import sys
import django
from datetime import datetime
from collections import defaultdict

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from django.db import transaction
from django.db.models import Q
from django.conf import settings
from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from pianos.models import Reservation, AccountTransaction, normalize_name, name_matches
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.sms_sender import SMSSender
from pianos.automation.utils import is_allowed_customer


class PaymentMatcher:
    def __init__(self, dry_run=True, scraper=None, sms_sender=None, naver_url: str = ""):
        self.dry_run = dry_run
        self.naver_url = naver_url

        # ✅ 외부에서 주입되면 그걸 쓰고, 없으면(단독 실행 테스트)만 새로 만든다
        self.scraper = scraper or NaverPlaceScraper(use_existing_chrome=True, dry_run=dry_run)
        self.sms_sender = sms_sender or SMSSender(dry_run=dry_run)

        print(f"🧪 PM.scraper.driver id={id(self.scraper.driver)}")
        print(f"🧪 PM.handle={self.scraper.driver.current_window_handle}")
        print(f"🧪 PM.handles={len(self.scraper.driver.window_handles)}")
    def _is_window_gone(self, e: Exception) -> bool:
        msg = str(e)
        return (
            isinstance(e, NoSuchWindowException)
            or "no such window" in msg.lower()
            or "target window already closed" in msg.lower()
            or "web view not found" in msg.lower()
        )
        
    # def _depositor_match_q(self, customer_name: str) -> Q:
    #     """
    #     입금자명 매칭 조건:
    #     - 기본: 완전일치
    #     - 보강: 이름이 포함된 경우도 허용 (예: '신한홍길동'에 '홍길동' 포함)
    #     - 단, 이름이 너무 짧으면(1글자) 오탐 위험이 커서 포함 매칭 제외
    #     """
    #     target = normalize_name(customer_name)
    #     if len(target) < 2:
    #         return Q(normalized_depositor_name__iexact=target)
    #     return Q(normalized_depositor_name__iexact=target) | Q(normalized_depositor_name__icontains=target)

    # # 잘림 매칭(방향2)을 인정할 최소 비율. 입금자명 길이가 예약명 길이의 이 비율 이상일 때만
    # # "예약명이 입금자명으로 시작"을 매칭으로 본다. (예: 'CHUNSUKJ'(8) vs 'CHUNSUKJUN'(10) → 0.8 통과)
    # _TRUNC_MIN_RATIO = 0.6

    # def _name_matches(self, res_name: str, dep_name: str) -> bool:
    #     """
    #     예약자명(res_name) ↔ 입금자명(dep_name) 양방향 매칭.

    #     a = 정규화된 예약자명, b = 정규화된 입금자명
    #     1) 완전일치:            a == b
    #     2) 방향1(접두어 포함):   입금자명이 예약명을 통째로 포함
    #                             예) 은행이 앞에 붙는 경우 '신한홍길동'(b) ⊃ '홍길동'(a)
    #                                 → 예약명 2글자 이상일 때만 (오탐 방지)
    #     3) 방향2(뒤 잘림):       예약명이 입금자명으로 '시작'
    #                             예) 은행이 뒤를 자른 경우 예약 'CHUNSUKJUN'(a) 가
    #                                 입금 'CHUNSUKJ'(b) 로 시작
    #                                 → 입금자명 4글자 이상 + 길이비율 조건을 만족할 때만
    #     """
    #     a = normalize_name(res_name)
    #     b = normalize_name(dep_name)

    #     if not a or not b:
    #         return False

    #     # 1) 완전일치
    #     if a == b:
    #         return True

    #     # 2) 방향1: 입금자명 ⊃ 예약명 (은행 접두어 등)
    #     if len(a) >= 2 and a in b:
    #         return True

    #     # 3) 방향2: 예약명이 입금자명으로 시작 (은행이 뒤를 잘라낸 경우)
    #     #    - 너무 짧은 입금자명(예: 'PARK'만)이 긴 예약명에 걸리는 오탐을 막기 위해
    #     #      길이 하한(4)과 비율 하한(_TRUNC_MIN_RATIO)을 동시에 요구
    #     if len(b) >= 4 and a.startswith(b) and len(b) >= len(a) * self._TRUNC_MIN_RATIO:
    #         return True

    #     return False

    def _filter_by_name(self, transactions, name):
        """이름 조건(name_matches)으로만 거래 리스트를 걸러낸다."""
        return [t for t in transactions if name_matches(name, t.depositor_name)]
    
    def check_pending_payments(self):
        """
        입금 대기 중인 예약들을 계좌 내역 DB와 매칭
        
        Returns:
            int: 확정 처리된 예약 개수
        """
        # 1. 예약자별로 그룹화하여 처리
    
    
        pending_customers = self._get_pending_customers()

        if not pending_customers:
            return 0
        
        print(f"\n{'='*60}")
        print(f"💰 입금 확인 프로세스")
        print(f"{'='*60}")
        print(f"   📋 입금 대기 중인 고객: {len(pending_customers)}명")
        
        # 2. 각 고객에 대해 매칭 시도
        confirmed_count = 0
        for customer_info in pending_customers:
            matched = self.try_match_customer(customer_info)
            if matched:
                confirmed_count += matched
        
        if confirmed_count > 0:
            print(f"\n   ✅ 입금 확인 완료: {confirmed_count}건")
        
        return confirmed_count
    
    def _get_pending_customers(self):
        """
        입금 대기 중인 고객 정보를 예약자별로 그룹화
        
        Returns:
            [
                {
                    'name': '박수민',
                    'phone': '010-0000-0000',
                    'total_amount': 40000,  # 이 사람이 보내야 할 총 금액
                    'reservations': [<Reservation>, <Reservation>]
                },
                ...
            ]
        """
        # 입금 대기 중인 예약 조회
        pending_reservations = Reservation.objects.filter(
            reservation_status='신청',
            is_coupon=False,
            account_sms_status='전송완료'  # 계좌 문자를 보낸 것들만
        ).order_by('created_at')
        
        # 예약자별로 그룹화
        customer_groups = defaultdict(lambda: {
            'name': '',
            'phone': '',
            'total_amount': 0,
            'reservations': []
        })
        
        for res in pending_reservations:
            key = res.phone_number  # 전화번호로 그룹화
            customer_groups[key]['name'] = res.customer_name
            customer_groups[key]['phone'] = res.phone_number
            customer_groups[key]['total_amount'] += res.price
            customer_groups[key]['reservations'].append(res)
        
        return list(customer_groups.values())
    
    def try_match_customer(self, customer_info):
        """
        고객 1명에 대해 입금 매칭 시도
        
        Args:
            customer_info: {
                'name': '박수민',
                'phone': '010-0000-0000',
                'total_amount': 40000,
                'reservations': [<Reservation>, <Reservation>]
            }
        
        Returns:
            int: 확정 처리된 예약 개수
        """
        
        name = customer_info['name']
        total_amount = customer_info['total_amount']
        reservations = customer_info['reservations']
        
        # # 이미 처리된 예약이 하나라도 있으면 스킵
        # if any(r.match_status in ('확정완료', '취소') for r in reservations):
        #     return 0
        
        print(f"\n   🔍 고객 확인: {name}")
        print(f"      - 신청 예약: {len(reservations)}건")
        print(f"      - 총 입금 필요 금액: {total_amount:,}원")
        
        # 각 예약 정보 출력
        for res in reservations:
            print(f"        • {res.room_name} | {res.reservation_date} {res.start_time}~{res.end_time} | {res.price:,}원")
        
        # 예약 중 가장 빠른 생성일
        earliest_created = min(res.created_at for res in reservations)
        
        # 1. 정확히 총액과 일치하는 입금 내역 찾기
        matched_transactions = self._find_matching_transactions(
            name, 
            total_amount, 
            earliest_created.date()
        )
        
        if matched_transactions:
            print(f"      ✅ 입금 내역 발견! (매칭 방식: 단일 입금)")
            for trans in matched_transactions:
                print(f"         - {trans.depositor_name} | {trans.amount:,}원 | {trans.transaction_date} {trans.transaction_time}")
            
            return self._confirm_reservations(reservations, matched_transactions)
        
        # 2. 분할 입금 확인 (여러 건의 입금이 합쳐서 총액과 일치)
        split_transactions = self._find_split_transactions(
            name,
            total_amount,
            earliest_created.date()
        )
        
        if split_transactions:
            print(f"      ✅ 입금 내역 발견! (매칭 방식: 분할 입금)")
            for trans in split_transactions:
                print(f"         - {trans.depositor_name} | {trans.amount:,}원 | {trans.transaction_date} {trans.transaction_time}")
            
            return self._confirm_reservations(reservations, split_transactions)
        
        # 매칭 안되면 조용히 0 반환 (로그 없음)
        return 0
    
    def _find_matching_transactions(self, name, amount, from_date):
        """
        정확히 금액이 일치하는 입금 내역 찾기
        
        Returns:
            QuerySet: 매칭된 거래 내역들
        """
        candidates = AccountTransaction.objects.filter(
            transaction_type='입금',
            match_status='확정전',  # ★ 확정전 상태만
            amount=amount,
            transaction_date__gte=from_date
        ).order_by('transaction_date', 'transaction_time')

        for t in candidates:
            if name_matches(name, t.depositor_name):
                return [t]
        return []
    
    def _find_split_transactions(self, name, total_amount, from_date):
        """
        분할 입금 찾기 (여러 건의 입금 합계가 총액과 일치)
        
        Returns:
            list: 매칭된 거래 내역 리스트
        """
        # 해당 고객의 확정전 입금 내역 조회
        # (이름은 파이썬에서 양방향 판정 → combinations 전에 반드시 이름으로 먼저 걸러야
        #  다른 사람 입금이 조합에 섞이지 않는다)
        base_qs = AccountTransaction.objects.filter(
            transaction_type='입금',
            match_status='확정전',  # ★ 확정전 상태만
            transaction_date__gte=from_date
        ).order_by('transaction_date', 'transaction_time')
        candidate_transactions = self._filter_by_name(base_qs, name)

        # 조합 찾기 (최대 5개까지)
        from itertools import combinations
        
        for r in range(1, min(6, len(candidate_transactions) + 1)):
            for combo in combinations(candidate_transactions, r):
                if sum(t.amount for t in combo) == total_amount:
                    return list(combo)
        
        return []
    
    def _confirm_reservations(self, reservations, transactions):
        print(f"      🔄 예약 확정 처리 중...")

        confirmed_count = 0
        confirmed_reservations = []

        try:
            with transaction.atomic():
                for res in reservations:
                    if not is_allowed_customer(res.customer_name):
                        print(f"      🛡️ 안전모드: '{res.customer_name}' 확정 처리 스킵")
                        continue

                    if not self.dry_run:
                        try:
                            success = self.scraper.confirm_in_pending_tab(res.naver_booking_id)

                        except (NoSuchWindowException, WebDriverException) as e:
                            # ✅ 창/탭 죽음이면: 새 창 복구 → 1회 재시도
                            if self._is_window_gone(e) and self.naver_url:
                                print("🧯 window 죽음 감지 → 새 창 복구 후 확정 1회 재시도")
                                self.scraper.reopen_reservation_tab(
                                    self.naver_url,
                                    close_old=False,
                                    as_window=True,
                                )
                                success = self.scraper.confirm_in_pending_tab(res.naver_booking_id)
                            else:
                                raise

                        if not success:
                            print(f"      ❌ 네이버 확정 실패: {res.naver_booking_id}")
                            continue
                    else:
                        print(f"      [DRY_RUN] 네이버 확정 시뮬레이션: {res.naver_booking_id}")

                    self.sms_sender.send_confirm_message(res)

                    res.reservation_status = '확정'
                    res.complete_sms_status = '전송완료'
                    res.save(update_fields=['reservation_status', 'complete_sms_status', 'updated_at'])

                    confirmed_reservations.append(res)
                    confirmed_count += 1

                # ⚠️ transactions는 reservations '전체 합계'와 매칭된 것이므로,
                # 일부 예약만 확정됐을 때 거래를 확정완료로 닫아버리면
                # 나머지 예약분 금액이 아무 예약에도 안 걸린 채로 사라진 것처럼 보인다.
                # → 그룹 전원이 확정된 경우에만 거래를 확정완료로 닫는다.
                all_confirmed = confirmed_reservations and len(confirmed_reservations) == len(reservations)

                if all_confirmed:
                    for trans in transactions:
                        trans.match_status = '확정완료'
                        trans.save(update_fields=['match_status', 'updated_at'])
                        trans.matched_reservations.set(confirmed_reservations)
                elif confirmed_reservations:
                    print(
                        f"      ⚠️ 일부만 확정됨({confirmed_count}/{len(reservations)}) "
                        f"→ 거래 매칭은 보류(확정전 유지), 수동 확인 필요"
                    )

            print(f"      ✅ 입금 확인 처리 완료!")
            print(f"         - 확정 예약: {confirmed_count}건")
            # 
            print(f"         - 매칭 거래: {len(transactions) if all_confirmed else 0}건")
            return confirmed_count

        except Exception as e:
            print(f"      ❌ 입금 확인 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def _is_overlap(self, a_start, a_end, b_start, b_end) -> bool:
        return a_start < b_end and b_start < a_end
    
    def _cancel_overlapping_pending_reservations(self, winner: Reservation, reason: str):
        """
        winner(확정된 예약)와 시간이 겹치는 '신청' 상태 예약들을 모두 취소한다.
        - 입금/미입금 상관없이 동일 취소문자
        - 입금 내역 있으면 match_status='취소'로 표시
        """
        # ✅ 안전모드: winner가 허용된 고객이 아닐 때는 아무 것도 하지 않음
        if not is_allowed_customer(winner.customer_name):
            return

        candidates = Reservation.objects.filter(
            room_name=winner.room_name,
            reservation_date=winner.reservation_date,
            reservation_status='신청',
            is_coupon=False
        ).exclude(id=winner.id)

        losers = []
        for r in candidates:
            if self._is_overlap(winner.start_time, winner.end_time, r.start_time, r.end_time):
                losers.append(r)

        if not losers:
            return

        print(f"      🧹 확정 후 중복 신청 예약 취소: {len(losers)}건")

        for loser in losers:
            if not is_allowed_customer(loser.customer_name):
                print(f"         🛡️ 안전모드: '{loser.customer_name}' 취소 스킵")
                continue

            trans = self._get_earliest_payment(loser)  # 있으면 취소표시
            self._cancel_loser(reservation=loser, reason=reason, trans=trans)

    
    def handle_first_payment_wins(self) -> bool:
        """
        선입금/충돌 처리에서 실제 확정/취소 등 액션이 발생했는지 반환
        +
        선입금자 확정 처리
        
        같은 시간대에 여러 일반 예약이 있을 때:
        1. 선입금자만 확정
        2. 후입금자는 취소+환불 예정 문자
        3. 미입금자는 취소 문자
        """
        # 1. 같은 시간대에 여러 신청이 있는 경우 찾기
        conflicting_groups = self._find_conflicting_groups()
        
        if not conflicting_groups:
            return False
        
        did_actions = False
        print(f"\n{'='*60}")
        print(f"🏆 선입금 확정 처리")
        print(f"{'='*60}")
        print(f"   📋 충돌 그룹: {len(conflicting_groups)}개")
        
        # 2. 각 그룹에 대해 선입금자 확정
        for group in conflicting_groups:
            did_actions |= bool(self._process_conflicting_group(group))  # ✅ group 처리 결과 누적

        return did_actions
    
    def _find_conflicting_groups(self):
        """
        겹치는(Overlap) 시간대에 여러 신청이 있는 그룹 찾기
        - room_name + reservation_date 단위로 모아서
        - start_time 기준 정렬 후, 겹치는 구간을 하나의 클러스터로 묶는다.
        """
        pending_reservations = Reservation.objects.filter(
            reservation_status='신청',
            is_coupon=False
        ).order_by('room_name', 'reservation_date', 'start_time', 'end_time')

        # (room, date) 단위로 묶기
        by_room_date = defaultdict(list)
        for res in pending_reservations:
            by_room_date[(res.room_name, res.reservation_date)].append(res)

        conflicting_groups = []

        for (room, date), reservations in by_room_date.items():
            # start_time 기준 정렬된 상태라고 가정(위 order_by)
            if len(reservations) < 2:
                continue

            cluster = [reservations[0]]
            cluster_start = reservations[0].start_time
            cluster_end = reservations[0].end_time

            for res in reservations[1:]:
                # overlap 조건: res.start < cluster_end
                if res.start_time < cluster_end:
                    cluster.append(res)
                    # 클러스터 끝 시간은 가장 늦은 end로 확장
                    if res.end_time > cluster_end:
                        cluster_end = res.end_time
                else:
                    # 클러스터 종료
                    if len(cluster) >= 2:
                        conflicting_groups.append({
                            'room_name': room,
                            'date': date,
                            'time_range': (cluster_start, cluster_end),
                            'reservations': cluster
                        })
                    # 새 클러스터 시작
                    cluster = [res]
                    cluster_start = res.start_time
                    cluster_end = res.end_time

            # 마지막 클러스터 처리
            if len(cluster) >= 2:
                conflicting_groups.append({
                    'room_name': room,
                    'date': date,
                    'time_range': (cluster_start, cluster_end),
                    'reservations': cluster
                })

        return conflicting_groups
    
    def _process_conflicting_group(self, group) -> bool:
        """
        충돌 그룹 처리: "입금자 있으면 선입금자만 확정", 나머지는 전부 취소(문자 동일)
        정책:
        - 입금자 0명 => 아무 처리 안 함(유지)
        - loser는 입금/미입금 상관없이 동일한 취소문자
        - 단, 입금한 loser는 거래내역 match_status='취소'로 표시
        """
        room = group['room_name']
        time_range = group['time_range']
        reservations = group['reservations']

        print(f"\n   🔍 충돌 그룹: {room} | {time_range[0]}~{time_range[1]}")
        print(f"      - 신청 예약: {len(reservations)}건")

        # 1) 각 예약의 입금 상태 확인 (확정전 거래만)
        payment_info = []
        for res in reservations:
            trans = self._get_earliest_payment(res)
            payment_info.append({
                'reservation': res,
                'transaction': trans,
                'payment_time': (trans.transaction_date, trans.transaction_time) if trans else None
            })

        # ✅ 입금자 0명 => 유지
        paid_list = [x for x in payment_info if x['transaction'] is not None]
        if not paid_list:
            print("      ℹ️ 입금자 없음 → 그룹 유지(확정/취소 없음)")
            return False

        # 2) 선입금자(가장 빠른 payment_time) 선정
        paid_list.sort(key=lambda x: x['payment_time'])
        first_payer = paid_list[0]

        winner_res = first_payer['reservation']
        winner_tx = first_payer['transaction']

        print(f"      🏆 선입금자: {winner_res.customer_name}")

        # 3) winner 확정
        confirmed_cnt = self._confirm_reservations([winner_res], [winner_tx])
        did_actions = (confirmed_cnt > 0)

        # 4) loser 전부 취소 (문자 동일), 입금한 loser는 거래만 '취소' 표시
        reason = "같은 시간대 선입금자 우선"
        for info in payment_info:
            res = info['reservation']
            trans = info['transaction']

            if res.id == winner_res.id:
                continue

            print(f"      ❌ 자동 취소: {res.customer_name} (입금여부: {'입금' if trans else '미입금'})")
            self._cancel_loser(reservation=res, reason=reason, trans=trans)
            did_actions = True   # ✅ 취소 시도하면 조작 발생으로 간주
        return did_actions
    
    def _get_earliest_payment(self, reservation):
        """예약에 대한 가장 빠른 입금 내역 반환"""
        name = reservation.normalized_customer_name or reservation.customer_name
        candidates = AccountTransaction.objects.filter(
            transaction_type='입금',
            amount=reservation.price,
            transaction_date__gte=reservation.created_at.date(),
            match_status='확정전'
        ).order_by('transaction_date', 'transaction_time')

        for t in candidates:
            if name_matches(name, t.depositor_name):
                return t
        return None
    
    def _cancel_loser(self, reservation, reason, trans=None) -> bool:
        """
        loser 취소 처리 (문자 통합)
        - 입금/미입금 상관없이 같은 취소 문자
        - 입금한 loser면 거래내역 match_status='취소'로 표시
        """
        # 테스트 박수민, 하건수
        if not is_allowed_customer(reservation.customer_name):
            print(f"         🛡️ 안전모드: '{reservation.customer_name}' 취소 처리 스킵")
            return False
        try:
            if not self.dry_run:
                ok = self.scraper.cancel_in_pending_tab(reservation.naver_booking_id, reason=reason)
                if not ok:
                    return False
            else:
                print(f"         [DRY_RUN] 네이버 취소 시뮬레이션")

            # ✅ 취소 문자(통합)
            self.sms_sender.send_cancel_message(reservation, reason)

            # ✅ DB 업데이트 (원자적으로)
            with transaction.atomic():
                reservation.reservation_status = '취소'
                reservation.save(update_fields=[
                    'reservation_status',
                    'updated_at'
                ])

                if trans:
                    trans.match_status = '취소'
                    trans.save(update_fields=['match_status', 'updated_at'])

            return True
        
        except Exception as e:
            print(f"         ❌ 취소 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return False




def main():
    """메인 실행 함수 (테스트용)"""
    print("=" * 60)
    print("💰 입금 확인 매칭 시스템 (단독 실행)")
    print("=" * 60)
    
    # DRY_RUN 모드
    matcher = PaymentMatcher(dry_run=True)
    
    # 입금 확인
    matcher.check_pending_payments()
    
    # 선입금 확정
    matcher.handle_first_payment_wins()


if __name__ == "__main__":
    main()