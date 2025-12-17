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
from datetime import datetime, timedelta

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from pianos.models import Reservation
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.sms_sender import SMSSender
from pianos.automation.conflict_checker import ConflictChecker
from pianos.automation.account_sync import AccountSyncManager
from pianos.automation.payment_matcher import PaymentMatcher
from pianos.automation.coupon_manager import CouponManager
from django.utils import timezone


class ReservationMonitor:
    """예약 실시간 모니터링 시스템 (통합)"""
    ALLOWED_CUSTOMER_NAMES = {"박수민", "하건수", "박성원"}  # ✅ 테스트 허용 명단

    def _is_allowed_customer(self, name: str) -> bool:
        return (name or "").strip() in self.ALLOWED_CUSTOMER_NAMES
    
    def __init__(self, naver_url, dry_run=True):
        """
        Args:
            naver_url: 네이버 플레이스 예약 관리 페이지 URL
            dry_run: True이면 DB 업데이트만, 실제 버튼 클릭/문자 발송 안함
        """
        self.naver_url = naver_url
        self.dry_run = dry_run
        
        # 컴포넌트 초기화
        self.scraper = NaverPlaceScraper(use_existing_chrome=True, dry_run=dry_run)
        self.conflict_checker = ConflictChecker(dry_run=dry_run)
        self.sms_sender = SMSSender(dry_run=dry_run)
        self.account_sync = AccountSyncManager(dry_run=dry_run)
        self.payment_matcher = PaymentMatcher(dry_run=dry_run)
        self.coupon_manager = CouponManager(dry_run=dry_run)
        
        # 이전 예약 리스트 (변경 감지용)
        self.previous_bookings = []
        # 이전 확정대기 개수 (상단 '확정대기 N' 탭의 N 값 추적)
        # self.previous_pending_count = 0
        
        # 계좌 동기화 타이머
        self.last_account_sync = datetime.now()
        self.account_sync_interval = timedelta(minutes=5)
    
    def run(self):
        """메인 루프"""
        print("=" * 60)
        print("🚀 이지피아노스튜디오 예약 자동화 시스템 시작")
        if self.dry_run:
            print("⚠️ DRY_RUN 모드: DB 업데이트 O, '예약확정/예약취소' 버튼·문자 발송 X (탭 이동/체크박스 클릭은 O)")
        print("=" * 60)
        
        # 초기 페이지 로드
        self.scraper.driver.get(self.naver_url)
        time.sleep(3)
        
        # 초기 예약 리스트 로드
        self.previous_bookings = self.scraper.scrape_all_bookings()
        print(f"📋 초기 예약 리스트: {len(self.previous_bookings)}건")
        # 초기 확정대기 개수 기록
        # self.previous_pending_count = self.scraper.get_pending_count()
        # print(f"📌 초기 확정대기 개수: {self.previous_pending_count}")

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
                current_time = datetime.now()
                cycle_count += 1
                
                # ★ 1. 5분마다 계좌 내역 동기화
                if current_time - self.last_account_sync >= self.account_sync_interval:
                    print(f"\n{'='*60}")
                    print(f"💳 계좌 내역 동기화 (5분 주기) - {current_time.strftime('%H:%M:%S')}")
                    print(f"{'='*60}")
                    self.account_sync.sync_transactions()
                    self.last_account_sync = current_time
                
                # 2. 예약 리스트 스크래핑 (기본 예약리스트 탭 기준)
                current_bookings = self.scraper.scrape_all_bookings()
                
                # 3. 새로운 예약 확인
                new_bookings = self.find_new_bookings(current_bookings)
                
                # 3-1. 새 예약 중 '신청' 상태가 있는지 확인
                has_new_application = any(
                    b.get('reservation_status') == '신청'
                    for b in new_bookings
                )

                # ---- (A) 새 예약 처리 파트 직전에 플래그 추가 ----
                did_actions = False  # ✅ 네이버 화면 조작(확정/취소/refresh)이 있었는지

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
                    return
                
                # ---- (C) ✅ 조작이 있었으면 fresh scrape로 동기화 + previous 갱신 ----
                if did_actions:
                    # 네이버 화면은 이미 내부에서 refresh가 일어났을 수 있으니, 여기서 확실히 최신화
                    self.scraper.refresh_page()
                    time.sleep(2)

                    fresh_bookings = self.scraper.scrape_all_bookings()

                    # ✅ 최신 스냅샷으로 DB 상태 동기화
                    self.update_existing_bookings(fresh_bookings)

                    # ✅ previous도 최신 스냅샷으로 저장 (중요)
                    self.previous_bookings = fresh_bookings
                else:
                    # ✅ 이건 “상태동기화는 매 사이클”로 바꾸는 걸 추천
                    self.update_existing_bookings(current_bookings)
                    self.previous_bookings = current_bookings
                    self.scraper.refresh_page()

                time.sleep(7)
                
            except KeyboardInterrupt:
                print("\n\n⏹️ 사용자에 의해 중단됨")
                break
            except Exception as e:
                print(f"\n❌ 모니터링 오류: {e}")
                import traceback
                traceback.print_exc()
                print("\n⏰ 10초 후 재시도...")
                time.sleep(10)
        
        self.scraper.close()
        print("\n🔚 시스템 종료")
    
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
            # 테스트 박수민,하건수
            allowed = self._is_allowed_customer(booking.get("customer_name"))
            if not allowed:
                print(f"      🛡️ 안전모드: '{booking.get('customer_name')}' 는 테스트 대상 아님 → 확정/취소/문자 동작 스킵")

            try:
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

                    if allowed:
                        if not self.dry_run:
                            ok = self.scraper.cancel_in_pending_tab(booking['naver_booking_id'], reason=reason)
                            did_actions |= bool(ok)   # ✅ 취소 성공했으면 조작 발생 True
                        else:
                            print(f"      [DRY_RUN] 네이버 취소 시뮬레이션")
                        self.sms_sender.send_cancel_message(reservation, reason)
                    else:
                        print("      🛡️ 안전모드: 네이버 취소/문자 스킵")
                        continue
                    # 네이버 취소
                    if not self.dry_run:
                        self.scraper.cancel_in_pending_tab(booking['naver_booking_id'], reason=reason)
                    else:
                        print(f"      [DRY_RUN] 네이버 취소 시뮬레이션")
                    
                    # DB에는 저장하되 취소 상태로
                    reservation = self.save_booking_to_db(booking, status='취소')
                    # 취소 문자
                    self.sms_sender.send_cancel_message(reservation, conflict_result['message'])
                    continue
                
                # 2. DB 저장 (네이버에서 가져온 상태 그대로 저장)
                naver_status = booking.get('reservation_status', '신청')
                reservation = self.save_booking_to_db(booking, status=naver_status)
                
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
            allowed = self._is_allowed_customer(reservation.customer_name)
            if not allowed:
                print(f"      🛡️ 안전모드: '{reservation.customer_name}' 계좌문자/클릭 스킵")
                return
            
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
        allowed = self._is_allowed_customer(reservation.customer_name)
        if not allowed:
            print(f"      🛡️ 안전모드: '{reservation.customer_name}' 쿠폰 확정/취소/문자 스킵 (DB 기록만)")
            return False
        print(f"      🎫 쿠폰 예약 처리 시작")

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
            
            self.sms_sender.send_confirm_message(reservation)
            reservation.complete_sms_status = '전송완료'
            reservation.save(update_fields=['complete_sms_status', 'updated_at'])
            
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
                # 이미 저장된 데이터라면 문자상태 덮어쓰지 않게 주의!
                # 처음 생성일 때만 기본값 넣고 싶으면 아래처럼 분기 권장
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
    
    if not NAVER_URL:
        print("❌ NAVER_RESERVATION_URL 환경 변수가 설정되지 않았습니다.")
        NAVER_URL = "https://partner.booking.naver.com/bizes/686937/booking-list-view?bookingBusinessId=686937"  # 기본값 (테스트용)
    
    # TODO: 실제 URL로 변경 필요
    print("⚠️ NAVER_URL을 실제 주소로 변경해주세요!")
    
    # DRY_RUN 모드로 실행
    monitor = ReservationMonitor(
        naver_url=NAVER_URL,
        dry_run=False
    )
    
    monitor.run()


if __name__ == "__main__":
    main()
