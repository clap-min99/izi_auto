"""
예약 충돌 확인 및 처리
"""
import os
import sys
import django
from datetime import datetime

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from django.db import transaction
from django.db.models import Q
from pianos.models import Reservation, AccountTransaction
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.sms_sender import SMSSender


class ConflictChecker:
    """예약 충돌 확인 및 처리"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.scraper = NaverPlaceScraper(use_existing_chrome=True, dry_run=dry_run)
        self.sms_sender = SMSSender(dry_run=dry_run)
    
    def check_and_handle_conflicts(self, new_booking):
        """
        새 예약에 대해 충돌 확인 및 처리
        
        시나리오:
        1. 충돌 없음 → 정상 진행 (일반 예약: 계좌문자, 쿠폰: 즉시 확정)
        2. 쿠폰 예약 vs 일반 예약(신청) → 쿠폰 확정, 일반 취소
        3. 일반 예약 vs 일반 예약(신청) → 둘 다 계좌문자, 선입금자 확정
        
        Args:
            new_booking: {
                'naver_booking_id': str,
                'customer_name': str,
                'phone_number': str,
                'room_name': str,
                'reservation_date': date,
                'start_time': time,
                'end_time': time,
                'price': int,
                'is_coupon': bool
            }
        
        Returns:
            dict: {
                'has_conflict': bool,
                'action': 'proceed' | 'cancel' | 'wait_for_payment',
                'message': str
            }
        """
        print(f"\n   🔍 충돌 확인: {new_booking['customer_name']} | {new_booking['room_name']}")
        
        # 1. 같은 시간대 예약 찾기
        conflicting_reservations = self._find_conflicting_reservations(new_booking)
        
        if not conflicting_reservations:
            print(f"      ✅ 충돌 없음")
            return {
                'has_conflict': False,
                'action': 'proceed',
                'message': '정상 진행'
            }
        
        print(f"      ⚠️ 충돌 발견: {len(conflicting_reservations)}건")
        for conf_res in conflicting_reservations:
            print(f"         - {conf_res.customer_name} | {conf_res.reservation_status} | 쿠폰:{conf_res.is_coupon}")
        
        # 2. 새 예약이 쿠폰인 경우
        if new_booking['is_coupon']:
            return self._handle_coupon_conflict(new_booking, conflicting_reservations)
        
        # 3. 새 예약이 일반이고, 충돌 중 쿠폰이 있는 경우
        has_coupon_conflict = any(res.is_coupon for res in conflicting_reservations)
        if has_coupon_conflict:
            return self._handle_general_vs_coupon(new_booking)
        
        # 4. 일반 예약끼리 충돌
        return self._handle_general_vs_general(new_booking, conflicting_reservations)
    
    def _find_conflicting_reservations(self, booking):
        """
        같은 시간대 예약 찾기
        
        Returns:
            QuerySet: 충돌하는 예약들 (취소 제외)
        """
        return Reservation.objects.filter(
            room_name=booking['room_name'],
            reservation_date=booking['reservation_date'],
            reservation_status__in=['신청', '확정']  # 취소 제외
        ).filter(
            # 시간 겹침 확인
            Q(
                start_time__lt=booking['end_time'],
                end_time__gt=booking['start_time']
            )
        ).exclude(
            naver_booking_id=booking.get('naver_booking_id')
        )
    
    def _handle_coupon_conflict(self, new_booking, conflicting_reservations):
        """
        새 쿠폰 예약 vs 기존 일반 예약(신청)
        → 쿠폰 즉시 확정, 일반 취소
        """
        print(f"      🎫 쿠폰 예약 우선 처리")
        
        # 1. 충돌 일반 예약들 취소
        for conf_res in conflicting_reservations:
            if not conf_res.is_coupon:
                self._cancel_reservation(
                    conf_res,
                    reason="쿠폰 예약과 시간대 충돌"
                )
        
        # 2. 쿠폰 예약은 즉시 확정
        return {
            'has_conflict': True,
            'action': 'proceed',
            'message': '쿠폰 예약 우선 확정, 충돌 예약 취소'
        }
    
    def _handle_general_vs_coupon(self, new_booking):
        """
        새 일반 예약 vs 기존 쿠폰 예약
        → 일반 예약 취소
        """
        print(f"      ❌ 쿠폰 예약이 이미 확정됨")
        
        return {
            'has_conflict': True,
            'action': 'cancel',
            'message': '쿠폰 예약이 이미 있어 취소'
        }
    
    def _handle_general_vs_general(self, new_booking, conflicting_reservations):
        """
        일반 예약 vs 일반 예약(신청)
        → 둘 다 계좌문자 발송, 선입금자 확정
        """
        print(f"      ⏳ 일반 예약 충돌 - 선입금자 확정 방식")
        
        # 계좌문자는 둘 다 발송
        return {
            'has_conflict': True,
            'action': 'wait_for_payment',
            'message': '계좌문자 발송, 선입금자 우선'
        }
    
    def _cancel_reservation(self, reservation, reason):
        """
        예약 취소 처리
        
        1. 입금 전: 취소 문자만 발송
        2. 입금 후: 취소+환불 예정 문자 발송
        """
        print(f"      🚫 예약 취소: {reservation.customer_name} ({reason})")
        
        try:
            # 1. 입금 확인
            has_payment = self._check_payment(reservation)
            
            # 2. 네이버 취소
            if not self.dry_run:
                self.scraper.cancel_in_pending_tab(reservation.naver_booking_id)
            else:
                print(f"      [DRY_RUN] 네이버 취소 시뮬레이션")
            
            # 3. 문자 발송 & DB 업데이트
            with transaction.atomic():
                if has_payment:
                    # 입금 후: 취소+환불 예정 문자
                    self.sms_sender.send_cancel_with_refund_message(reservation, reason)
                    # ★ 거래 내역도 취소 상태로 변경
                    self._mark_transaction_as_cancelled(reservation)
                else:
                    # 입금 전: 취소 문자만
                    self.sms_sender.send_cancel_message(reservation, reason)
                
                # 예약 상태 업데이트
                reservation.reservation_status = '취소'
                reservation.save()
            
        except Exception as e:
            print(f"      ❌ 취소 처리 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _check_payment(self, reservation):
        """
        예약에 대한 입금이 있는지 확인
        
        Returns:
            bool: 입금 여부
        """
        # 계좌 내역에서 이 예약자의 입금 확인
        payment_exists = AccountTransaction.objects.filter(
            transaction_type='입금',
            depositor_name__icontains=reservation.customer_name,
            amount=reservation.price,
            transaction_date__gte=reservation.created_at.date(),
            match_status__in=['확정전', '확정완료']  # 확정전 or 확정완료
        ).exists()
        
        return payment_exists
    
    def _mark_transaction_as_cancelled(self, reservation):
        """
        예약 취소 시 거래 내역도 취소 상태로 변경
        """
        # 이 예약과 매칭된 거래 내역 찾기
        transactions = AccountTransaction.objects.filter(
            matched_reservations=reservation
        )
        
        for trans in transactions:
            trans.match_status = '취소'  # ★ 취소 상태로 변경
            trans.save()
            print(f"         - 거래 내역 취소 처리: {trans.transaction_id}")
        
        # 아직 매칭 안된 거래도 찾아서 취소 처리
        unmatched_transactions = AccountTransaction.objects.filter(
            transaction_type='입금',
            depositor_name__icontains=reservation.customer_name,
            amount=reservation.price,
            transaction_date__gte=reservation.created_at.date(),
            match_status='확정전'
        )
        
        for trans in unmatched_transactions:
            trans.match_status = '취소'
            trans.save()
            print(f"         - 미매칭 거래 취소 처리: {trans.transaction_id}")


def main():
    """메인 실행 함수 (테스트용)"""
    print("=" * 60)
    print("⚠️ 충돌 확인 시스템 (단독 실행)")
    print("=" * 60)
    
    # DRY_RUN 모드
    checker = ConflictChecker(dry_run=True)
    
    # 테스트 예약
    test_booking = {
        'naver_booking_id': 'TEST123',
        'customer_name': '테스트',
        'phone_number': '010-1234-5678',
        'room_name': 'Room1',
        'reservation_date': datetime.now().date(),
        'start_time': datetime.now().time(),
        'end_time': datetime.now().time(),
        'price': 20000,
        'is_coupon': False
    }
    
    result = checker.check_and_handle_conflicts(test_booking)
    print(f"\n결과: {result}")


if __name__ == "__main__":
    main()