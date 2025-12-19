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

    @transaction.atomic
    def refund_if_confirmed_coupon_canceled(self, reservation, reason="예약자 자발 취소"):
        """
        '확정' 처리되어 쿠폰이 차감된 예약이 '취소'로 바뀐 경우, 차감한 시간을 되돌립니다.
        - idempotent(중복 환불 방지)
        """
        if not getattr(reservation, "is_coupon", False):
            return False

        # 1) 이 예약에 대해 '사용' 이력이 있는지(=차감이 실제로 일어났는지) 확인
        used_exists = CouponHistory.objects.filter(
            reservation=reservation,
            transaction_type='사용',
        ).exists()

        if not used_exists:
            # 차감이 없었으면 환불할 것도 없음
            return False

        duration = reservation.get_duration_minutes()
        extra = getattr(reservation, "extra_people_qty", 0) or 0
        print(f"      - 인원추가 수량: {extra}")
        print(f"      - 차감 시간(인원추가 반영): {duration}분")

        # 2) 이미 환불 이력이 생성됐으면 중복 환불 방지
        refunded_exists = CouponHistory.objects.filter(
            reservation=reservation,
            transaction_type='환불',
            used_or_charged_time=duration
        ).exists()
        if refunded_exists:
            return False

        # 3) 고객 찾기
        room_category = get_room_category(getattr(reservation, "room_name", ""))
        customer = CouponCustomer.objects.filter(
            phone_number=reservation.phone_number,
            piano_category=room_category,
        ).first()
        if not customer:
            return False

        # 4) 잔여시간 복구 + 이력 생성(충전으로 기록)
        customer.remaining_time += duration
        customer.save(update_fields=["remaining_time", "updated_at"])

        CouponHistory.objects.create(
            customer=customer,
            reservation=reservation,
            customer_name=customer.customer_name,
            room_name=reservation.room_name,            # 추적용
            transaction_date=reservation.reservation_date,      # 환불 처리일
            start_time=reservation.start_time,
            end_time=reservation.end_time,
            remaining_time=customer.remaining_time,
            used_or_charged_time=duration,              # +duration (환불)
            transaction_type='환불'
        )

        return True
    
    def check_balance(self, reservation):
        """
        쿠폰 잔여시간 확인
        Returns: (has_balance, customer)
        """
        try:
            room_category = get_room_category(getattr(reservation, "room_name", ""))
            # ✅ 룸 카테고리 기반으로 해당 지갑 선택
            customer = CouponCustomer.objects.get(
                phone_number=reservation.phone_number,
                piano_category=room_category,
            )

            # ✅ 쿠폰 메타 정보 없으면 불가
            if not customer.coupon_type or not customer.piano_category or not customer.coupon_expires_at:
                return False, customer, "쿠폰 정보 미등록"

            # ✅ 만료 갱신
            customer.refresh_expiry_status(today=timezone.localdate())
            if customer.coupon_status == "만료":
                return False, customer, "쿠폰 유효기간 만료"

            # ✅ 룸 매칭 체크
            if room_category and customer.piano_category != room_category:
                return False, customer, "쿠폰 종류(수입/국산) 불일치"

            duration = reservation.get_duration_minutes()
            if customer.remaining_time >= duration:
                return True, customer, ""
            return False, customer, "잔여 시간 부족"

        except CouponCustomer.DoesNotExist:
            return False, None, "쿠폰 고객 정보 없음"
    
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
            # 1. 네이버 확정 버튼 클릭
            if not self.dry_run:
                scraper.confirm_in_pending_tab(reservation.naver_booking_id)
            else:
                print("   [DRY_RUN] 네이버 확정 시뮬레이션")
            
            # 2. 쿠폰 차감 (⭐ DB는 항상 업데이트)
            extra = reservation.extra_people_qty
            print(f"      🧪 인원추가 수량(DB): {extra}")
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
            reservation.save(update_fields=['reservation_status', 'complete_sms_status', 'updated_at'])
            
            print(f"   💾 예약 상태 업데이트 완료 (확정)")
            
            return True
            
        except Exception as e:
            print(f"❌ 쿠폰 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return False