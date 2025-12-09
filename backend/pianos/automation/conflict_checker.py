"""
예약 시간 충돌 감지
"""
from datetime import datetime, timedelta
from pianos.models import Reservation


class ConflictChecker:
    """예약 시간 충돌 확인"""
    
    def check(self, new_reservation):
        """
        시간대 충돌 확인
        
        Args:
            new_reservation: Reservation 객체
            
        Returns:
            (has_conflict, conflicted_reservation)
        """
        new_start = datetime.combine(
            new_reservation.reservation_date, 
            new_reservation.start_time
        )
        new_end = datetime.combine(
            new_reservation.reservation_date, 
            new_reservation.end_time
        )
        
        # 종료시간이 시작시간보다 이른 경우 (자정 넘김)
        if new_end < new_start:
            new_end += timedelta(days=1)
        
        # DB에서 같은 날짜, 같은 룸, 확정/신청 상태인 예약 조회
        existing_reservations = Reservation.objects.filter(
            room_name=new_reservation.room_name,
            reservation_date=new_reservation.reservation_date,
            reservation_status__in=['신청', '확정']
        ).exclude(
            naver_booking_id=new_reservation.naver_booking_id
        )
        
        for existing in existing_reservations:
            existing_start = datetime.combine(
                existing.reservation_date, 
                existing.start_time
            )
            existing_end = datetime.combine(
                existing.reservation_date, 
                existing.end_time
            )
            
            # 종료시간이 시작시간보다 이른 경우 (자정 넘김)
            if existing_end < existing_start:
                existing_end += timedelta(days=1)
            
            # 시간 겹침 확인
            # (새 예약 시작 < 기존 예약 끝) AND (새 예약 끝 > 기존 예약 시작)
            if (new_start < existing_end and new_end > existing_start):
                return True, existing  # 충돌 발생
        
        return False, None  # 충돌 없음