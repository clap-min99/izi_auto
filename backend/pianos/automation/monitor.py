"""
예약 실시간 모니터링 시스템 (통합 버전)
- 예약 스크래핑
- 계좌 내역 동기화 (5분 주기)
- 입금 확인 및 매칭
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

from pianos.models import Reservation, CouponCustomer
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.sms_sender import SMSSender
from pianos.automation.conflict_checker import ConflictChecker
from pianos.automation.account_sync import AccountSyncManager
from pianos.automation.payment_matcher import PaymentMatcher
from django.utils import timezone


class ReservationMonitor:
    """예약 실시간 모니터링 시스템 (통합)"""
    
    ROOM_CATEGORY_MAP = {
        'Room1_야마하 그랜드': '수입',
        'Room3_야마하 그랜드': '수입',
        'Room5_가와이 그랜드': '수입',
        'Room2_삼익 그랜드': '국산',
        'Room4_삼익 그랜드': '국산',
        'Room6_영창 그랜드': '국산',
    }

    def get_room_category(self, room_name: str):
        return self.ROOM_CATEGORY_MAP.get(room_name)

    def refresh_coupon_expiry(self, coupon_customer):
        """만료일이 지났으면 쿠폰 상태를 '만료'로 갱신"""
        today = timezone.now().date()
        if getattr(coupon_customer, 'coupon_expires_at', None) and today > coupon_customer.coupon_expires_at:
            if coupon_customer.coupon_status != '만료':
                coupon_customer.coupon_status = '만료'
                coupon_customer.save(update_fields=['coupon_status'])
        return coupon_customer.coupon_status


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
        self.account_sync.sync_transactions()
        
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
                # 2-1. 현재 확정대기 개수 읽기
                # current_pending_count = self.scraper.get_pending_count()
                
                # 3. 새로운 예약 확인
                new_bookings = self.find_new_bookings(current_bookings)
                
                # 3-1. 새 예약 중 '신청' 상태가 있는지 확인
                has_new_application = any(
                    b.get('reservation_status') == '신청'
                    for b in new_bookings
                )

                # 3-2. 확정대기 숫자가 증가했는지 확인
                # pending_increased = current_pending_count > self.previous_pending_count

                # 조건: 새 '신청' 예약 발생 + 확정대기 개수가 이전보다 증가한 경우에만 확정대기 탭 클릭
                # if has_new_application and pending_increased:
                #     print(
                #         f"👉 새 '신청' 예약 + 확정대기 {self.previous_pending_count} → {current_pending_count} 증가 감지 → 확정대기 탭 클릭"
                #     )
                #     # 기본 예약리스트 네이버 창에서 조건 만족 시 확정대기 탭 클릭
                #     self.scraper.click_pending_button()

                # ★ 새 예약이 있을 때만 상세 로그
                if new_bookings:
                    print(f"\n{'='*60}")
                    print(f"🔔 사이클 #{cycle_count} - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"{'='*60}")
                    print(f"   📋 현재 예약 리스트: {len(current_bookings)}건")
                    print(f"\n{'─'*60}")
                    print(f"✨ 새 예약 {len(new_bookings)}건 발견!")
                    print(f"{'─'*60}")
                    self.handle_new_bookings(new_bookings)
                    
                    # 기존 예약 상태 변경 확인
                    print(f"\n{'─'*60}")
                    print("🔄 예약 상태 변경 확인")
                    print(f"{'─'*60}")
                    self.update_existing_bookings(current_bookings)
                else:
                    # 새 예약 없을 때는 간단한 로그만
                    if cycle_count % 6 == 0:  # 1분마다 (10초 * 6)
                        print(f"[{current_time.strftime('%H:%M:%S')}] ⏳ 대기 중... (예약: {len(current_bookings)}건)")
                
                # ★ 4. 입금 확인 (새 예약이 있을 때만 상세 로그)
                if new_bookings:
                    self.payment_matcher.check_pending_payments()
                    self.payment_matcher.handle_first_payment_wins()
                else:
                    # 조용히 실행
                    self._silent_payment_check()
                
                # 5. 이전 예약 리스트/확정대기 개수 업데이트
                self.previous_bookings = current_bookings
                # self.previous_pending_count = current_pending_count
                
                # 6. 새로고침
                self.scraper.refresh_page()
                
                # 7. 대기 (10초)
                time.sleep(10)
                
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
            self.payment_matcher.check_pending_payments()
            self.payment_matcher.handle_first_payment_wins()

        except Exception as e:
            print(f"⚠️ 조용한 입금 확인 중 오류: {e}")

    def find_new_bookings(self, current_bookings):
        """
        새로운 예약 찾기
        
        Returns:
            list: 새로운 예약 리스트
        """
        previous_ids = {b['naver_booking_id'] for b in self.previous_bookings}
        new_bookings = [
            b for b in current_bookings 
            if b['naver_booking_id'] not in previous_ids
        ]
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
        for booking in new_bookings:
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
                    
                    # 네이버 취소
                    if not self.dry_run:
                        self.scraper.cancel_in_pending_tab(booking['naver_booking_id'], reason=reason)
                    else:
                        print(f"      [DRY_RUN] 네이버 취소 시뮬레이션")
                    
                    # 취소 문자
                    self.sms_sender.send_cancel_message_for_new_booking(booking, conflict_result['message'])
                    
                    # DB에는 저장하되 취소 상태로
                    self.save_booking_to_db(booking, status='취소')
                    continue
                
                # 2. DB 저장 (네이버에서 가져온 상태 그대로 저장)
                naver_status = booking.get('reservation_status', '신청')
                reservation = self.save_booking_to_db(booking, status=naver_status)
                
                # 3. 쿠폰 예약 처리
                if booking['is_coupon']:
                    self.handle_coupon_booking(reservation, booking)
                else:
                    # 4. 일반 예약 처리
                    self.handle_general_booking(reservation, booking)
                    
            except Exception as e:
                print(f"   ❌ 예약 처리 오류: {e}")
                import traceback
                traceback.print_exc()
    
    def handle_general_booking(self, reservation, booking):
        """
        일반(입금) 예약 처리
        1. 계좌 문자 발송
        2. 입금 대기
        """
        try:
            print(f"      💳 일반 예약 처리")
            # 1. 계좌 안내 문자 발송 (Reservation 객체 기준)
            self.sms_sender.send_account_message(reservation)
            
            # 2) 문자 발송 상태 DB 반영
            reservation.account_sms_status = '전송완료'
            reservation.save()
            print(f"      💬 입금 안내 문자 발송 완료")
            
        except Exception as e:
            print(f"      ❌ 일반 예약 처리 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def handle_coupon_booking(self, reservation, booking):
        """
        쿠폰 예약 처리
        
        - 쿠폰 고객 잔여 시간 확인
        - 잔여 시간 충분하면 즉시 확정
        - 부족하면 취소
        """
        print(f"      🎫 쿠폰 예약 처리 시작")

        # 1. 쿠폰 고객 조회
        try:
            coupon_customer = CouponCustomer.objects.get(
                phone_number=booking['phone_number']
            )
        except CouponCustomer.DoesNotExist:
            print(f"      ❌ 쿠폰 고객 정보 없음")
            # 취소 처리
            self._cancel_coupon_booking(reservation, "쿠폰 고객 정보 없음")
            return
        
        # ✅ (추가) 쿠폰 메타 정보가 없으면 취소
        if not coupon_customer.coupon_type or not coupon_customer.piano_category or not coupon_customer.coupon_expires_at:
            print(f"      ❌ 쿠폰 정보 미등록(종류/수입국산/만료일 없음) → 취소")
            self._cancel_coupon_booking(reservation, "쿠폰 정보 미등록")
            return

        # ✅ (추가) 만료 체크 (만료면 DB 상태 '만료'로 갱신 후 취소)
        coupon_customer.refresh_expiry_status(today=timezone.localdate())
        if coupon_customer.coupon_status == "만료":
            print(f"      ❌ 쿠폰 만료 → 취소")
            self._cancel_coupon_booking(reservation, "쿠폰 유효기간 만료")
            return

        # ✅ (추가) 룸 수입/국산 매칭 체크
        room_category = self.get_room_category(booking.get('room_name'))
        if room_category and coupon_customer.piano_category != room_category:
            print(f"      ❌ 쿠폰({coupon_customer.piano_category}) vs 룸({room_category}) 불일치 → 취소")
            self._cancel_coupon_booking(reservation, "쿠폰 종류(수입/국산) 불일치")
            return
        
        # 2. 예약 시간 계산 (분)
        from datetime import datetime, timedelta
        start_dt = datetime.combine(booking['reservation_date'], booking['start_time'])
        end_dt = datetime.combine(booking['reservation_date'], booking['end_time'])
        booking_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        print(f"      - 예약 시간: {booking_minutes}분")
        print(f"      - 잔여 시간: {coupon_customer.remaining_time}분")
        
        # 3. 잔여 시간 확인
        if coupon_customer.remaining_time >= booking_minutes:
            # 충분함 → 즉시 확정
            print(f"      ✅ 잔여 시간 충분 → 즉시 확정")
            self._confirm_coupon_booking(reservation, coupon_customer, booking_minutes)
        else:
            # 부족함 → 취소
            print(f"      ❌ 잔여 시간 부족 → 취소")
            self._cancel_coupon_booking(reservation, "잔여 시간 부족")

    def _confirm_coupon_booking(self, reservation, coupon_customer, booking_minutes):
        """쿠폰 예약 확정"""
        try:
            # 네이버 상에서도 확정 (확정대기 탭 기준)
            if not self.dry_run:
                self.scraper.confirm_in_pending_tab(reservation.naver_booking_id)
            else:
                print(f"      [DRY_RUN] 네이버 확정 시뮬레이션")
            
            # DB 상태 변경
            reservation.reservation_status = '확정'
            reservation.save()
            
            # 쿠폰 잔여 시간 차감
            coupon_customer.remaining_time -= booking_minutes
            coupon_customer.save()
            
            # 쿠폰 사용 이력 생성
            from pianos.models import CouponHistory
            CouponHistory.objects.create(
                customer=coupon_customer,
                reservation=reservation,
                customer_name=reservation.customer_name,
                room_name=reservation.room_name,
                transaction_date=reservation.reservation_date,
                start_time=reservation.start_time,
                end_time=reservation.end_time,
                remaining_time=coupon_customer.remaining_time,
                used_or_charged_time=-booking_minutes,
                transaction_type='사용'
            )
        
            print(f"      ✅ 쿠폰 예약 확정 완료")
            print(f"         - 차감: {booking_minutes}분")
            print(f"         - 잔여: {coupon_customer.remaining_time}분")
            
        except Exception as e:
            print(f"      ❌ 쿠폰 확정 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _cancel_coupon_booking(self, reservation, reason):
        """쿠폰 예약 취소 처리"""
        try:
            # 네이버 취소
            if not self.dry_run:
                self.scraper.cancel_in_pending_tab(reservation.naver_booking_id)
            else:
                print(f"      [DRY_RUN] 네이버 취소 시뮬레이션")
            
            # DB 상태 변경
            reservation.reservation_status = '취소'
            reservation.save()
            
            # 취소 문자
            self.sms_sender.send_cancel_message_for_coupon_booking(
                reservation, reason
            )
            
            print(f"      ✅ 쿠폰 예약 취소 완료 ({reason})")
            
        except Exception as e:
            print(f"      ❌ 쿠폰 취소 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def save_booking_to_db(self, booking, status='신청'):
        """
        예약 정보를 DB에 저장
        
        Returns:
            Reservation: 저장된 예약 객체
        """
        reservation = Reservation.objects.create(
            naver_booking_id=booking['naver_booking_id'],
            # booking_datetime=booking.get('booking_datetime', datetime.now()),
            customer_name=booking['customer_name'],
            phone_number=booking['phone_number'],
            room_name=booking['room_name'],
            reservation_date=booking['reservation_date'],
            start_time=booking['start_time'],
            end_time=booking['end_time'],
            price=booking['price'],
            is_coupon=booking['is_coupon'],
            reservation_status=status,
            account_sms_status='전송전',
            complete_sms_status='입금확인전'
        )
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
                if reservation.reservation_status != naver_status:
                    print(f"   🔁 상태 변경 감지: {reservation.naver_booking_id}")
                    print(f"      - {reservation.reservation_status} → {naver_status}")
                    
                    reservation.reservation_status = naver_status
                    reservation.save()
                    updated_count += 1
                    
            except Exception as e:
                print(f"   ❌ 상태 업데이트 오류: {e}")
                continue
        
        if updated_count > 0:
            print(f"   ✅ 상태 변경: {updated_count}건")
        else:
            print(f"   ℹ️ 상태 변경 없음")


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
