"""
예약 실시간 모니터링 시스템
"""
import os
import sys
import django
import time
from datetime import datetime

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from pianos.models import Reservation, CouponCustomer
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.conflict_checker import ConflictChecker
from pianos.automation.sms_sender import SMSSender


class ReservationMonitor:
    """예약 실시간 모니터링 시스템"""
    
    def __init__(self, naver_url, dry_run=True):
        self.naver_url = naver_url
        self.dry_run = dry_run
        self.scraper = NaverPlaceScraper(use_existing_chrome=True, dry_run=dry_run)
        self.conflict_checker = ConflictChecker()
        self.sms_sender = SMSSender(dry_run=dry_run)
        
    def run(self):
        """메인 루프"""
        print("=" * 60)
        print("🚀 이지피아노스튜디오 예약 자동화 시스템 시작")
        if self.dry_run:
            print("⚠️ DRY_RUN 모드: DB 저장 O, 확정/취소는 시뮬레이션")
        print("=" * 60)
        
        # 초기 페이지 로드
        self.scraper.driver.get(self.naver_url)
        time.sleep(3)
        
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 예약 리스트 확인 중...")
                
                # 1. 예약 리스트 전체 스크래핑
                current_bookings = self.scraper.scrape_all_bookings()
                
                print(f"   📋 현재 예약 리스트: {len(current_bookings)}건")
                
                # 2. DB와 비교하여 새로운 예약 찾기
                new_bookings = self.find_new_bookings(current_bookings)
                
                # 3. 기존 예약의 상태 변경 확인 및 업데이트
                self.update_existing_bookings(current_bookings)
                
                # 4. 새로운 예약이 있으면 처리
                if new_bookings:
                    print(f"\n✅ 새 예약 {len(new_bookings)}건 발견!")
                    self.handle_new_bookings(new_bookings)
                else:
                    print("   ℹ️ 새로운 예약 없음")
                
                # 5. 새로고침
                print("   🔄 새로고침 중...")
                self.scraper.refresh_page()
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("\n\n⏹️ 사용자에 의해 중단됨")
                break
            except Exception as e:
                print(f"❌ 모니터링 오류: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(10)
        
        self.scraper.close()
        print("\n🔚 시스템 종료")
    
    def find_new_bookings(self, current_bookings):
        """DB에 없는 새로운 예약 찾기"""
        new_bookings = []
        
        for booking in current_bookings:
            # DB에 해당 예약번호가 있는지 확인
            exists = Reservation.objects.filter(
                naver_booking_id=booking['naver_booking_id']
            ).exists()
            
            if not exists:
                new_bookings.append(booking)
        
        return new_bookings
    
    def update_existing_bookings(self, current_bookings):
        """기존 예약의 상태 변경 확인 및 업데이트"""
        for booking in current_bookings:
            try:
                # DB에서 해당 예약 찾기
                reservation = Reservation.objects.get(
                    naver_booking_id=booking['naver_booking_id']
                )
                
                # 상태가 변경되었는지 확인
                if reservation.reservation_status != booking['reservation_status']:
                    old_status = reservation.reservation_status
                    reservation.reservation_status = booking['reservation_status']
                    reservation.save()
                    
                    print(f"   🔄 상태 변경: {booking['customer_name']} ({old_status} → {booking['reservation_status']})")
                    
            except Reservation.DoesNotExist:
                continue
    
    def handle_new_bookings(self, new_bookings):
        """새로운 예약들 처리"""
        print("\n" + "="*60)
        print("📋 새 예약 처리 시작")
        print("="*60)
        
        # 1. 먼저 모든 새 예약을 DB에 저장
        reservations = []
        for booking in new_bookings:
            reservation = self.save_to_db(booking)
            if reservation:
                reservations.append(reservation)
        
        # 2. 각 예약에 대해 충돌 검사 및 처리
        cancelled_reservations = []
        normal_reservations = []
        coupon_reservations = []
        
        for reservation in reservations:
            # 충돌 검사
            has_conflict, conflicted = self.conflict_checker.check(reservation)
            
            if has_conflict:
                print(f"\n⚠️ 시간 충돌: {reservation.customer_name}")
                print(f"   기존 예약: {conflicted.customer_name} ({conflicted.naver_booking_id})")
                
                # 충돌 안내 문자
                self.sms_sender.send_conflict_message(reservation)
                
                # 취소 리스트에 추가
                cancelled_reservations.append(reservation)
                
                # DB 상태 업데이트
                reservation.reservation_status = '취소'
                reservation.save()
            else:
                # 쿠폰 예약인지 확인
                if reservation.is_coupon:
                    # 쿠폰 잔여시간 확인
                    has_balance = self.check_coupon_balance(reservation)
                    
                    if has_balance:
                        coupon_reservations.append(reservation)
                    else:
                        # 잔여시간 부족
                        cancelled_reservations.append(reservation)
                        reservation.reservation_status = '취소'
                        reservation.save()
                else:
                    # 일반 예약
                    normal_reservations.append(reservation)
        
        # 3. 확정대기 버튼 클릭 (문자 발송 및 취소 처리)
        if normal_reservations or cancelled_reservations or coupon_reservations:
            self.process_in_pending_tab(
                normal_reservations, 
                cancelled_reservations,
                coupon_reservations
            )
        
        print("\n✅ 모든 새 예약 처리 완료")
    
    def save_to_db(self, booking):
        """DB 저장"""
        try:
            reservation = Reservation.objects.create(
                naver_booking_id=booking['naver_booking_id'],
                customer_name=booking['customer_name'],
                phone_number=booking['phone_number'],
                room_name=booking['room_name'],
                reservation_date=booking['reservation_date'],
                start_time=booking['start_time'],
                end_time=booking['end_time'],
                price=booking['price'],
                is_coupon=booking['is_coupon'],
                reservation_status='신청',
            )
            
            print(f"✅ DB 저장: {booking['customer_name']} (ID: {reservation.id})")
            return reservation
            
        except Exception as e:
            print(f"❌ DB 저장 실패: {e}")
            return None
    
    def check_coupon_balance(self, reservation):
        """쿠폰 잔여시간 확인"""
        try:
            customer = CouponCustomer.objects.get(
                phone_number=reservation.phone_number
            )
            
            duration = reservation.get_duration_minutes()
            
            if customer.remaining_time >= duration:
                print(f"✅ 쿠폰 충분: {customer.customer_name} (잔여: {customer.remaining_time}분)")
                return True
            else:
                print(f"⚠️ 쿠폰 부족: {customer.customer_name} (잔여: {customer.remaining_time}분)")
                self.sms_sender.send_insufficient_message(reservation, customer)
                return False
                
        except CouponCustomer.DoesNotExist:
            print(f"⚠️ 쿠폰 정보 없음: {reservation.customer_name}")
            self.sms_sender.send_insufficient_message(reservation, None)
            return False
    
    def process_in_pending_tab(self, normal_reservations, cancelled_reservations, coupon_reservations):
        """
        확정대기 탭에서 처리
        - 일반 예약: 계좌 안내 문자 발송
        - 취소 예약: 취소 처리
        - 쿠폰 예약: 즉시 확정
        """
        print("\n" + "─"*60)
        print("⏸️ 확정대기 탭으로 이동")
        print("─"*60)
        
        # 1. 확정대기 버튼 클릭
        if not self.scraper.click_pending_button():
            print("❌ 확정대기 버튼 클릭 실패")
            return
        
        # 2. 일반 예약 - 계좌 안내 문자 발송
        for reservation in normal_reservations:
            print(f"\n📤 계좌 안내 문자: {reservation.customer_name}")
            success = self.sms_sender.send_account_message(reservation)
            
            if success:
                reservation.account_sms_status = '전송완료'
                reservation.save()
        
        # 3. 취소 예약 - 취소 처리
        for reservation in cancelled_reservations:
            print(f"\n🚫 취소 처리: {reservation.customer_name}")
            self.scraper.cancel_in_pending_tab(reservation.naver_booking_id)
        
        # 4. 쿠폰 예약 - 즉시 확정
        for reservation in coupon_reservations:
            print(f"\n✅ 쿠폰 예약 확정: {reservation.customer_name}")
            success = self.scraper.confirm_in_pending_tab(reservation.naver_booking_id)
            
            if success:
                # 쿠폰 차감
                self.deduct_coupon(reservation)
                
                # DB 상태 업데이트
                reservation.reservation_status = '확정'
                reservation.save()
        
        # 5. 새로고침 (메인 페이지로 복귀)
        print("\n🔄 메인 페이지로 복귀")
        self.scraper.refresh_page()
    
    def deduct_coupon(self, reservation):
        """쿠폰 차감"""
        try:
            customer = CouponCustomer.objects.get(
                phone_number=reservation.phone_number
            )
            
            duration = reservation.get_duration_minutes()
            old_remaining = customer.remaining_time
            customer.remaining_time -= duration
            customer.save()
            
            print(f"   💾 쿠폰 차감: {old_remaining}분 → {customer.remaining_time}분")
            
            # 이력 생성
            from pianos.models import CouponHistory
            CouponHistory.objects.create(
                customer=customer,
                reservation=reservation,
                customer_name=customer.customer_name,
                room_name=reservation.room_name,
                transaction_date=reservation.reservation_date,
                start_time=reservation.start_time,
                end_time=reservation.end_time,
                remaining_time=customer.remaining_time,
                used_or_charged_time=-duration,
                transaction_type='사용'
            )
            
        except Exception as e:
            print(f"   ❌ 쿠폰 차감 실패: {e}")


def main():
    """메인 실행 함수"""
    NAVER_BOOKING_URL = "https://partner.booking.naver.com/bizes/686937/booking-list-view?bookingBusinessId=686937"
    
    monitor = ReservationMonitor(NAVER_BOOKING_URL, dry_run=True)
    monitor.run()


if __name__ == "__main__":
    main()