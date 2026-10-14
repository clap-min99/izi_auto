
"""실제 네이버/팝빌/문자/운영 DB를 사용하지 않는 안전성 테스트."""

from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.utils import timezone

from pianos.automation.monitor import ReservationMonitor
from pianos.automation.payment_matcher import PaymentMatcher
from pianos.automation.conflict_checker import ConflictChecker


class SplitPaymentTests(TestCase):
    @patch('pianos.automation.payment_matcher.AccountTransaction')
    def test_multiple_reservations_confirm_from_split_payments(self, model):
        matcher = PaymentMatcher.__new__(PaymentMatcher)
        matcher._confirm_reservations = MagicMock(return_value=2)
        reservations = [
            SimpleNamespace(price=15000, created_at=timezone.now(),
                            room_name='A', reservation_date='2026-10-14',
                            start_time='10:00', end_time='11:00'),
            SimpleNamespace(price=25000, created_at=timezone.now(),
                            room_name='A', reservation_date='2026-10-14',
                            start_time='11:00', end_time='12:00'),
        ]
        deposits = [
            SimpleNamespace(depositor_name='홍길동', amount=10000,
                            transaction_date='2026-10-14', transaction_time='09:00'),
            SimpleNamespace(depositor_name='홍길동', amount=30000,
                            transaction_date='2026-10-14', transaction_time='09:01'),
            SimpleNamespace(depositor_name='다른사람', amount=40000,
                            transaction_date='2026-10-14', transaction_time='09:02'),
        ]
        # 총액 단일 입금은 없고, 서로 다른 금액의 입금 합계가 예약 총액과 일치.
        model.objects.filter.return_value.order_by.side_effect = [[], deposits]
        result = matcher.try_match_customer({
            'name': '홍길동', 'total_amount': 40000,
            'reservations': reservations,
        })
        self.assertEqual(result, 2)
        matcher._confirm_reservations.assert_called_once_with(
            reservations, deposits[:2]
        )


class CouponPriorityTests(TestCase):
    def setUp(self):
        self.checker = ConflictChecker.__new__(ConflictChecker)
        self.checker.dry_run = False
        self.checker.scraper = MagicMock()
        self.checker.sms_sender = MagicMock()

    def test_coupon_precedes_pending_and_confirmed_general(self):
        targets = [SimpleNamespace(is_coupon=False, reservation_status=status)
                   for status in ('신청', '확정')]
        result = self.checker._handle_coupon_conflict({}, targets)
        self.assertEqual(result['action'], 'defer_cancel_until_coupon_confirmed')
        self.assertEqual(result['cancel_targets'], targets)
        self.checker.scraper.cancel_in_pending_tab.assert_not_called()

    def test_coupon_collision_is_held(self):
        result = self.checker._handle_coupon_conflict(
            {}, [SimpleNamespace(is_coupon=True, reservation_status='확정')]
        )
        self.assertEqual(result['action'], 'hold')

    @patch('pianos.automation.conflict_checker.is_allowed_customer', return_value=True)
    @patch('pianos.automation.conflict_checker.Reservation')
    @patch('pianos.automation.conflict_checker.transaction.atomic')
    def test_confirmed_general_cancel_requires_naver_success(self, atomic, model, allowed):
        from contextlib import nullcontext
        atomic.side_effect = lambda: nullcontext()
        res = MagicMock(is_coupon=False, reservation_status='확정')
        model.objects.select_for_update.return_value.get.return_value = res
        self.checker._mark_transaction_as_cancelled = MagicMock()
        self.checker.scraper.cancel_in_pending_tab.return_value = False
        self.assertFalse(self.checker._cancel_reservation(res, '쿠폰 충돌'))
        res.save.assert_not_called()
        self.checker._mark_transaction_as_cancelled.assert_not_called()
        self.checker.sms_sender.send_cancel_message.assert_not_called()
        self.checker.scraper.cancel_in_pending_tab.return_value = True
        self.assertTrue(self.checker._cancel_reservation(res, '쿠폰 충돌'))
        self.assertEqual(res.reservation_status, '취소')
        self.checker._mark_transaction_as_cancelled.assert_called_once_with(res)

    @patch('pianos.automation.payment_matcher.Reservation')
    def test_first_payment_winner_cannot_bypass_coupon(self, model):
        matcher = PaymentMatcher.__new__(PaymentMatcher)
        matcher.scraper = MagicMock()
        overlaps = model.objects.filter.return_value.exclude.return_value
        overlaps.filter.return_value.exists.return_value = True
        self.assertEqual(matcher._confirm_reservations(
            [MagicMock()], [], conflict_winner=True
        ), 0)
        overlaps.filter.assert_called_once_with(is_coupon=True)
        matcher.scraper.confirm_in_pending_tab.assert_not_called()

    @patch('pianos.automation.monitor.is_allowed_customer', return_value=True)
    def test_general_cancel_runs_only_after_coupon_confirmation(self, allowed):
        for confirmed in (False, True):
            with self.subTest(confirmed=confirmed):
                monitor = ReservationMonitor.__new__(ReservationMonitor)
                monitor.dry_run = False
                monitor.conflict_checker = MagicMock()
                target = MagicMock()
                monitor.conflict_checker.check_and_handle_conflicts.return_value = {
                    'action': 'defer_cancel_until_coupon_confirmed',
                    'cancel_targets': [target],
                }
                monitor.conflict_checker._cancel_reservation.return_value = False
                res = MagicMock(reservation_status='신청')
                monitor.save_booking_to_db = MagicMock(return_value=res)
                monitor.send_owner_request_notification_if_needed = MagicMock()
                def confirm(*args):
                    res.reservation_status = '확정' if confirmed else '신청'
                    return confirmed
                monitor.handle_coupon_booking = MagicMock(side_effect=confirm)
                booking = dict(
                    reservation_status='신청', customer_name='테스트',
                    naver_booking_id='COUPON', room_name='테스트방',
                    reservation_date='2026-10-14', start_time='10:00',
                    end_time='11:00', price=10000, is_coupon=True,
                )
                monitor.handle_new_bookings([booking])
                if confirmed:
                    monitor.conflict_checker._cancel_reservation.assert_called_once()
                    monitor.conflict_checker.notify_owner_conflict.assert_called_once()
                else:
                    monitor.conflict_checker._cancel_reservation.assert_not_called()

    @patch('pianos.automation.conflict_checker.AccountTransaction')
    def test_cancelled_payment_is_preserved_for_refund_review(self, model):
        res = MagicMock(created_at=timezone.now(), naver_booking_id='GENERAL')
        trans = MagicMock(pk=1, memo='original', match_status='확정완료')
        model.objects.filter.side_effect = [[trans], []]
        self.checker.notify_owner_conflict = MagicMock()
        self.checker._mark_transaction_as_cancelled(res)
        self.assertEqual(trans.match_status, '취소')
        self.assertIn('original', trans.memo)
        self.assertIn('[환불 확인 필요] 예약 GENERAL', trans.memo)
        trans.delete.assert_not_called()
        trans.matched_reservations.add.assert_called_once_with(res)
        self.checker.notify_owner_conflict.assert_called_once()


class PaymentConflictSafetyTests(TestCase):

    def setUp(self):
        # __init__ 우회: Selenium 브라우저 실행 방지
        self.matcher = PaymentMatcher.__new__(PaymentMatcher)

        self.matcher._get_earliest_payment = MagicMock()
        self.matcher._confirm_reservations = MagicMock()
        self.matcher._cancel_loser = MagicMock(return_value=True)

        self.winner = MagicMock()
        self.winner.id = 1
        self.winner.customer_name = "선입금자"
        self.winner.naver_booking_id = "TEST-WINNER"
        self.winner.reservation_status = "확정"

        self.loser = MagicMock()
        self.loser.id = 2
        self.loser.customer_name = "후순위예약자"
        self.loser.naver_booking_id = "TEST-LOSER"

        self.tx = SimpleNamespace(
            transaction_date=timezone.localdate(),
            transaction_time=timezone.localtime().time(),
        )

        self.matcher._get_earliest_payment.side_effect = [
            self.tx, None
        ]

        self.group = {
            "room_name": "테스트방",
            "time_range": ("10:00", "11:00"),
            "reservations": [self.winner, self.loser],
        }

    def test_winner_confirmation_failure_never_cancels_loser(self):
        """선입금자 확정 실패 → 다른 예약 취소 금지."""
        self.matcher._confirm_reservations.return_value = 0

        result = self.matcher._process_conflicting_group(self.group)

        self.assertFalse(result)
        self.matcher._cancel_loser.assert_not_called()

    def test_winner_confirmation_success_allows_loser_cancellation(self):
        """선입금자 확정 성공 → 후순위 예약 취소 호출."""
        self.matcher._confirm_reservations.return_value = 1

        result = self.matcher._process_conflicting_group(self.group)

        self.assertTrue(result)
        self.matcher._cancel_loser.assert_called_once()

    def test_winner_db_state_not_confirmed_never_cancels_loser(self):
        """확정 함수 성공 반환 후에도 DB가 신청이면 취소 금지."""
        self.matcher._confirm_reservations.return_value = 1
        self.winner.reservation_status = "신청"

        result = self.matcher._process_conflicting_group(self.group)

        self.assertFalse(result)
        self.matcher._cancel_loser.assert_not_called()


    @patch("pianos.automation.payment_matcher.Reservation")
    def test_general_matching_does_not_bypass_conflict(
        self, reservation_model
    ):
        """충돌 예약을 일반 입금 매칭으로 우회 확정하지 않음."""
        from contextlib import nullcontext

        self.matcher.dry_run = False
        self.matcher.scraper = MagicMock()
        self.matcher.sms_sender = MagicMock()
        self.matcher.scraper.confirm_in_pending_tab.return_value = True

        res = MagicMock()
        res.pk = 10
        res.room_name = "테스트방"
        res.reservation_date = timezone.localdate()
        res.start_time = "10:00"
        res.end_time = "11:00"
        res.naver_booking_id = "TEST-MATCH"
        res.customer_name = "일반예약자"

        reservation_model.objects.filter.return_value \
            .exclude.return_value.exists.return_value = True

        # 실 DB 트랜잭션 및 안전모드 영향을 제거
        with (
            patch(
                "pianos.automation.payment_matcher.is_allowed_customer",
                return_value=True
            ),
            patch(
                "pianos.automation.payment_matcher.transaction.atomic",
                side_effect=lambda: nullcontext()
            )
        ):
            result = PaymentMatcher._confirm_reservations(
                self.matcher, [res], []
            )

        self.assertEqual(result, 0)
        reservation_model.objects.filter.assert_called_once()
        self.matcher.scraper.confirm_in_pending_tab.assert_not_called()



class TimeoutCancellationSafetyTests(TestCase):

    def setUp(self):
        # __init__ 우회: 실제 서비스 연결 방지
        self.monitor = ReservationMonitor.__new__(
            ReservationMonitor
        )

        self.monitor.dry_run = False
        self.monitor.scraper = MagicMock()
        self.monitor.sms_sender = MagicMock()

        self.reservation = MagicMock()
        self.reservation.naver_booking_id = "TEST-TIMEOUT"
        self.reservation.customer_name = "홍길동"
        self.reservation.reservation_status = "신청"
        self.reservation.is_coupon = False
        self.reservation.account_sms_status = "전송완료"
        self.reservation.created_at = (
            timezone.now() - timedelta(minutes=60)
        )

    def _reservation_queryset(self, reservation_model):
        qs = MagicMock()
        qs.exists.return_value = True
        qs.count.return_value = 1
        qs.__iter__.return_value = iter([self.reservation])

        reservation_model.objects.filter.return_value \
            .order_by.return_value = qs

    @patch("pianos.automation.monitor.Reservation")
    def test_bank_sync_failure_skips_cancellation(
        self, reservation_model
    ):
        """팝빌 동기화 실패 → 취소 시도 자체 금지."""
        result = self.monitor.cancel_expired_pending_deposits(
            bank_sync_ok=False
        )

        self.assertFalse(result)
        reservation_model.objects.filter.assert_not_called()
        self.monitor.scraper.cancel_in_pending_tab.assert_not_called()

    @patch("pianos.models.AccountTransaction")
    @patch("pianos.automation.monitor.Reservation")
    def test_linked_payment_skips_cancellation(
        self, reservation_model, transaction_model
    ):
        """예약에 연결된 입금이 있으면 취소 금지."""
        self._reservation_queryset(reservation_model)

        transaction_model.objects.filter.return_value \
            .exists.return_value = True

        result = self.monitor.cancel_expired_pending_deposits(
            bank_sync_ok=True
        )

        self.assertFalse(result)
        self.monitor.scraper.cancel_in_pending_tab.assert_not_called()
        self.reservation.save.assert_not_called()
        self.monitor.sms_sender.send_cancel_message.assert_not_called()

    @patch("pianos.models.AccountTransaction")
    @patch("pianos.automation.monitor.Reservation")
    def test_unlinked_payment_skips_cancellation(
        self, reservation_model, transaction_model
    ):
        """미매칭 입금 후보가 있으면 취소 금지."""
        self._reservation_queryset(reservation_model)

        linked = MagicMock()
        linked.exists.return_value = False

        candidates = MagicMock()
        candidates.only.return_value = [
            SimpleNamespace(
                depositor_name="홍길동",
                amount=15000
            )
        ]

        transaction_model.objects.filter.side_effect = [
            linked, candidates
        ]

        result = self.monitor.cancel_expired_pending_deposits(
            bank_sync_ok=True
        )

        self.assertFalse(result)
        self.monitor.scraper.cancel_in_pending_tab.assert_not_called()
        self.reservation.save.assert_not_called()
        self.monitor.sms_sender.send_cancel_message.assert_not_called()

    @patch("pianos.models.AccountTransaction")
    @patch("pianos.automation.monitor.Reservation")
    def test_naver_cancel_failure_keeps_db_unchanged(
        self, reservation_model, transaction_model
    ):
        """네이버 취소 실패 → DB 변경 및 문자 발송 금지."""
        self._reservation_queryset(reservation_model)

        linked = MagicMock()
        linked.exists.return_value = False

        candidates = MagicMock()
        candidates.only.return_value = []

        transaction_model.objects.filter.side_effect = [
            linked, candidates
        ]

        self.monitor.scraper.cancel_in_pending_tab.return_value = False

        result = self.monitor.cancel_expired_pending_deposits(
            bank_sync_ok=True
        )

        self.assertFalse(result)
        self.monitor.scraper.cancel_in_pending_tab.assert_called_once()
        self.reservation.save.assert_not_called()
        self.monitor.sms_sender.send_cancel_message.assert_not_called()
