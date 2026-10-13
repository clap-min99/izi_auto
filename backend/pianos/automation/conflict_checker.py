"""
예약 충돌 확인 및 처리
"""
import os
import sys
import django
from datetime import datetime
from django.conf import settings
from django.utils import timezone
# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from django.db import transaction
from django.db.models import Q
from pianos.models import Reservation, AccountTransaction, name_matches
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.sms_sender import SMSSender
from pianos.automation.utils import is_allowed_customer


class ConflictChecker:
    def __init__(self, dry_run=True, scraper=None, sms_sender=None, naver_url: str = ""):
        self.dry_run = dry_run
        self.naver_url = naver_url

        # ✅ 주입 우선, 없으면 단독 실행용으로만 생성
        self.scraper = scraper or NaverPlaceScraper(use_existing_chrome=True, dry_run=dry_run)
        self.sms_sender = sms_sender or SMSSender(dry_run=dry_run)
    
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
            return self._handle_general_vs_coupon(
                new_booking,
                conflicting_reservations
            )
        
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
        """새 쿠폰 예약은 기존 확정 예약 및 입금 고객을 보호한다."""
        conflicts = list(conflicting_reservations)

        # 기존 확정 예약은 쿠폰보다 우선 보호
        if any(r.reservation_status == '확정' for r in conflicts):
            print("      ⚠️ 기존 확정 예약 존재 → 새 쿠폰 예약 처리 보류")
            return {
                'has_conflict': True,
                'action': 'hold',
                'message': '기존 확정 예약과 충돌하여 수동 확인 필요'
            }

        # 다른 쿠폰 예약과 충돌하면 임의로 우선순위를 정하지 않음
        if any(r.is_coupon for r in conflicts):
            print("      ⚠️ 기존 쿠폰 예약 존재 → 새 쿠폰 예약 처리 보류")
            return {
                'has_conflict': True,
                'action': 'hold',
                'message': '쿠폰 예약 간 충돌로 수동 확인 필요'
            }

        # 신청 상태 일반 예약의 입금 흔적 보호
        for r in conflicts:
            if self._has_payment_evidence(r):
                print(
                    f"      ⚠️ 기존 일반 예약 입금 흔적 발견 "
                    f"→ 새 쿠폰 처리 보류: {r.naver_booking_id}"
                )
                return {
                    'has_conflict': True,
                    'action': 'hold',
                    'message': '기존 일반 예약 입금 확인 필요'
                }

        cancel_targets = [
            r for r in conflicts
            if not r.is_coupon and r.reservation_status == '신청'
        ]

        return {
            'has_conflict': True,
            'action': 'defer_cancel_until_coupon_confirmed',
            'message': '쿠폰 확정 성공 후 기존 신청 예약 취소 검토',
            'cancel_targets': cancel_targets,
        }

    def _handle_general_vs_coupon(
        self, new_booking, conflicting_reservations
    ):
        """기존 쿠폰이 실제 확정된 경우에만 새 일반 예약 취소 판단."""
        coupons = [
            r for r in conflicting_reservations if r.is_coupon
        ]

        if any(r.reservation_status == '확정' for r in coupons):
            return {
                'has_conflict': True,
                'action': 'cancel',
                'message': '동일 시간대 예약 충돌'
            }

        return {
            'has_conflict': True,
            'action': 'hold',
            'message': '기존 쿠폰 예약 확정 대기 중, 수동 확인 필요'
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
    
    
    def _has_payment_evidence(self, reservation):
        """기존 이름 매칭 규칙을 사용해 입금 흔적을 보수적으로 검사."""
        linked = AccountTransaction.objects.filter(
            matched_reservations=reservation,
            transaction_type='입금',
        ).exists()

        if linked:
            return True

        from_date = timezone.localtime(
            reservation.created_at
        ).date()

        candidates = AccountTransaction.objects.filter(
            transaction_type='입금',
            transaction_date__gte=from_date,
        ).only('depositor_name')

        return any(
            name_matches(reservation.customer_name, t.depositor_name)
            for t in candidates
        )

    def _cancel_reservation(self, reservation, reason):
        """미입금 일반 신청 예약만 취소 시도."""
        try:
            if not is_allowed_customer(reservation.customer_name):
                return False

            reservation.refresh_from_db()

            # 쿠폰 예약과 이미 확정된 예약 보호
            if (
                reservation.is_coupon
                or reservation.reservation_status != '신청'
            ):
                print(
                    f"      🛡️ 취소 대상 상태 아님 → 보호: "
                    f"{reservation.naver_booking_id}"
                )
                return False

            # 입금 기록이 있거나 불명확하면 취소 금지
            if self._has_payment_evidence(reservation):
                print(
                    f"      🛡️ 입금 흔적 발견 → 취소 보류: "
                    f"{reservation.naver_booking_id}"
                )
                return False

            if self.dry_run:
                print(
                    f"      [DRY_RUN] 취소 생략: "
                    f"{reservation.naver_booking_id}"
                )
                return False

            cancelled = self.scraper.cancel_in_pending_tab(
                reservation.naver_booking_id,
                reason=reason
            )

            if not cancelled:
                print(
                    f"      ⚠️ 네이버 취소 미확인 → DB/문자 보류: "
                    f"{reservation.naver_booking_id}"
                )
                return False

            # 네이버 취소 함수 성공 후 DB 변경
            with transaction.atomic():
                current = Reservation.objects.select_for_update().get(
                    pk=reservation.pk
                )

                if current.reservation_status != '신청':
                    print(
                        f"      ⚠️ 취소 중 DB 상태 변경 감지: "
                        f"{reservation.naver_booking_id}"
                    )
                    return False

                current.reservation_status = '취소'
                current.save(
                    update_fields=['reservation_status', 'updated_at']
                )

            sms_sent = self.sms_sender.send_cancel_message(
                current, reason
            )

            if not sms_sent:
                print(
                    f"      ⚠️ 예약 취소 완료, 취소 문자 확인 필요: "
                    f"{current.naver_booking_id}"
                )

            return True

        except Exception as e:
            print(
                f"      ❌ 충돌 예약 취소 처리 오류: "
                f"{reservation.naver_booking_id} | {e}"
            )
            return False

    
    def _check_payment(self, reservation):
        """
        예약에 대한 입금이 있는지 확인
        
        Returns:
            bool: 입금 여부
        """
        # 계좌 내역에서 이 예약자의 입금 확인
        candidates = AccountTransaction.objects.filter(
            transaction_type='입금',
            # depositor_name__icontains=reservation.customer_name,
            amount=reservation.price,
            transaction_date__gte=reservation.created_at.date(),
            match_status__in=['확정전', '확정완료']  # 확정전 or 확정완료
        )
        return any(name_matches(reservation.customer_name, t.depositor_name) for t in candidates)
        # ).exists()
        
        # return payment_exists
    
    def _mark_transaction_as_cancelled(self, reservation):
        """
        예약 취소 시 거래 내역도 취소 상태로 변경
        """
        # 이 예약과 매칭된 거래 내역 찾기
        transactions = AccountTransaction.objects.filter(
            matched_reservations=reservation
        )
        
        for trans in transactions:
            trans.match_status = '취소'  # 취소 상태로 변경
            trans.save()
            print(f"         - 거래 내역 취소 처리: {trans.transaction_id}")
        
        # 아직 매칭 안된 거래도 찾아서 취소 처리
        unmatched_candidates = AccountTransaction.objects.filter(
            transaction_type='입금',
            # depositor_name__icontains=reservation.customer_name,
            amount=reservation.price,
            transaction_date__gte=reservation.created_at.date(),
            match_status='확정전'
        )
        
        for trans in unmatched_candidates:
            if not name_matches(reservation.customer_name, trans.depositor_name):
                continue
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