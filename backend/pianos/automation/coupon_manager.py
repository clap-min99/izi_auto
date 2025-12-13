"""
쿠폰 잔여시간 확인 및 차감
"""
from pianos.models import CouponCustomer, CouponHistory
from django.db import transaction
from django.utils import timezone

ROOM_CATEGORY_MAP = {
    "Room1": "수입",
    "Room3": "수입",
    "Room5": "수입",
    "Room2": "국산",
    "Room4": "국산",
    "Room6": "국산",
}

def get_room_category(room_name: str):
    if not room_name:
        return None
    for key, cat in ROOM_CATEGORY_MAP.items():
        if key in room_name:
            return cat
    return None


class CouponManager:
    """쿠폰 관리"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run  # ⭐ DRY_RUN 모드
    
    def check_balance(self, reservation):
        """
        쿠폰 잔여시간 확인
        Returns: (has_balance, customer)
        """
        try:
            customer = CouponCustomer.objects.get(phone_number=reservation.phone_number)

            # ✅ 쿠폰 메타 정보 없으면 불가
            if not customer.coupon_type or not customer.piano_category or not customer.coupon_expires_at:
                return False, customer

            # ✅ 만료 갱신
            customer.refresh_expire_status(today=timezone.localdate())
            if customer.coupon_status == "만료":
                return False, customer

            # ✅ 룸 매칭 체크
            room_category = get_room_category(getattr(reservation, "room_name", ""))
            if room_category and customer.piano_category != room_category:
                return False, customer

            duration = reservation.get_duration_minutes()
            if customer.remaining_time >= duration:
                return True, customer
            return False, customer

        except CouponCustomer.DoesNotExist:
            return False, None
    
    @transaction.atomic
    def confirm_and_deduct(self, reservation, customer, scraper):
        """
        쿠폰 차감 및 예약 확정
        
        Args:
            reservation: Reservation 객체
            customer: CouponCustomer 객체
            scraper: NaverPlaceScraper 객체
            
        Returns:
            success: bool
        """
        try:
            # 1. 네이버 확정 버튼 클릭 (⭐ DRY_RUN이면 시뮬레이션만)
            success = scraper.confirm_booking(reservation.naver_booking_id)
            
            if not success:
                return False
            
            # 2. 쿠폰 차감 (⭐ DB는 항상 업데이트)
            duration = reservation.get_duration_minutes()
            old_remaining = customer.remaining_time
            customer.remaining_time -= duration
            customer.save()
            
            print(f"   💾 쿠폰 차감 완료")
            print(f"      - 차감 전: {old_remaining}분")
            print(f"      - 차감 시간: {duration}분")
            print(f"      - 차감 후: {customer.remaining_time}분")
            
            # 3. 이력 생성 (⭐ DB는 항상 업데이트)
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
            
            print(f"   💾 쿠폰 이력 생성 완료")
            
            # 4. DB 상태 업데이트 (⭐ DB는 항상 업데이트)
            reservation.reservation_status = '확정'
            reservation.complete_sms_status = '전송완료'
            reservation.save()
            
            print(f"   💾 예약 상태 업데이트 완료 (확정)")
            
            return True
            
        except Exception as e:
            print(f"❌ 쿠폰 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return False