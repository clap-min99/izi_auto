from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pianos.automation.alimtalk_sender import AlimTalkSender
from pianos.models import CouponHistory, CouponCustomer, NotificationLog


def _format_remaining(minutes: int) -> str:
    if minutes <= 0:
        return "0분"
    h = minutes // 60
    m = minutes % 60
    if h and m:
        return f"{h}시간 {m}분"
    if h:
        return f"{h}시간"
    return f"{m}분"


class Command(BaseCommand):
    help = "전날 스튜디오 이용(쿠폰 사용)한 쿠폰 고객에게 다음날 08:00 잔여시간 알림톡 발송"

    def handle(self, *args, **options):
        today = timezone.localdate()
        target_date = today - timedelta(days=1)  # 전날 이용자

        sender = AlimTalkSender()

        # 전날 '사용' 이력 기준으로 고객 추출 (중복 제거)
        customer_ids = (
            CouponHistory.objects
            .filter(transaction_type="사용", transaction_date=target_date)
            .values_list("customer_id", flat=True)
            .distinct()
        )

        customers = CouponCustomer.objects.filter(id__in=customer_ids)

        sent = failed = skipped = 0

        for customer in customers:
            # ✅ 중복 방지 로그: UniqueConstraint 덕분에 동시에 실행돼도 1번만 통과
            with transaction.atomic():
                log, created = NotificationLog.objects.get_or_create(
                    noti_type=NotificationLog.TYPE_COUPON_BALANCE_NEXTDAY,
                    target_date=target_date,
                    customer=customer,
                    defaults={"status": "PENDING"},
                )

                if not created and log.status == "SENT":
                    skipped += 1
                    continue

            phone = customer.phone_number
            remain_str = _format_remaining(customer.remaining_time)

            # ⚠️ 여기 content는 “승인된 템플릿 내용과 동일”하게 구성해야 함
            # 예: 템플릿이 아래 형태로 승인돼있다고 가정:
            # "안녕하세요 #{name}님\n전일 이용 후 현재 잔여시간은 #{remain} 입니다."
            content = f"안녕하세요 {customer.customer_name}님\n전일 이용 후 현재 잔여시간은 {remain_str} 입니다."

            try:
                resp = sender.send_alimtalk(
                    to_phone=phone,
                    template_code="COUPON_BALANCE_NEXTDAY",  # 너가 콘솔에서 만든 템플릿 코드로 교체
                    content=content,
                    use_sms_failover=False,
                )

                # 응답 처리
                if 200 <= resp.status_code < 300:
                    # 보통 requestId가 json에 들어오는 경우가 많음(없을 수도 있어서 안전 처리)
                    try:
                        data = resp.json()
                        request_id = str(data.get("requestId", ""))
                    except Exception:
                        request_id = ""

                    NotificationLog.objects.filter(pk=log.pk).update(
                        status="SENT",
                        request_id=request_id,
                        error="",
                        sent_at=timezone.now(),
                    )
                    sent += 1
                else:
                    NotificationLog.objects.filter(pk=log.pk).update(
                        status="FAILED",
                        error=f"HTTP {resp.status_code}: {resp.text[:1000]}",
                    )
                    failed += 1

            except Exception as e:
                NotificationLog.objects.filter(pk=log.pk).update(
                    status="FAILED",
                    error=str(e)[:2000],
                )
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f"[{today}] target_date={target_date} sent={sent} failed={failed} skipped={skipped}"
        ))
