# pianos/management/commands/send_coupon_usage_sms.py

from datetime import timedelta, datetime

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db import transaction
from django.utils import timezone

from pianos.models import CouponCustomer, CouponHistory, NotificationLog
from pianos.automation.sms_sender import SMSSender  # 프로젝트 실제 경로에 맞게 조정


def _fmt_minutes(m: int) -> str:
    m = max(int(m or 0), 0)
    h = m // 60
    mm = m % 60
    if h and mm:
        return f"{h}시간 {mm}분"
    if h:
        return f"{h}시간"
    return f"{mm}분"


class Command(BaseCommand):
    help = "전날(또는 지정일) 쿠폰 사용 고객에게: 사용시간(합산) + 잔여시간 + 유효기간 문자 발송"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="",
            help="기준일(YYYY-MM-DD). 미지정이면 어제",
        )
        parser.add_argument(
            "--send",
            action="store_true",
            help="실제 발송(기본은 DRY_RUN)",
        )
        parser.add_argument(
            "--broadcast",
            action="store_true",
            help="테스트용: 해당 일자 사용이 없어도 모든 쿠폰고객에게 발송(사용시간 0으로 표시)",
        )

    def handle(self, *args, **options):
        # 1) 날짜 결정
        if options["date"]:
            target_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
        else:
            target_date = timezone.localdate() - timedelta(days=1)

        # 2) 발송 모드
        dry_run = not options["send"]
        sender = SMSSender(dry_run=dry_run)

        # 3) 해당 날짜 "사용" 이력 합산 (같은 고객 여러번 사용 → 합쳐서 1번 안내)
        usage_qs = (
            CouponHistory.objects
            .filter(transaction_type="사용", transaction_date=target_date)
            .values("customer_id")
            .annotate(total_used=Sum("used_or_charged_time"))  # 보통 사용은 -분으로 저장됨
        )

        usage_map = {row["customer_id"]: abs(int(row["total_used"] or 0)) for row in usage_qs}

        # 4) 발송 대상
        if options["broadcast"]:
            customers = CouponCustomer.objects.all()
        else:
            customer_ids = list(usage_map.keys())
            customers = CouponCustomer.objects.filter(id__in=customer_ids)

        sent = skipped = 0

        for c in customers:
            used_min = usage_map.get(c.id, 0)

            with transaction.atomic():
                log, created = NotificationLog.objects.get_or_create(
                    noti_type="COUPON_USAGE_DAILY_SMS",
                    target_date=target_date,
                    customer=c,
                    defaults={"status": "PENDING"},
                )
                if not created and log.status == "SENT":
                    skipped += 1
                    continue

            # broadcast가 아니면 "사용 0분" 고객은 건너뜀(= 해당 날짜 이용자만)
            if not options["broadcast"] and used_min <= 0:
                skipped += 1
                continue

            used_str = _fmt_minutes(used_min)
            remain_str = _fmt_minutes(getattr(c, "remaining_time", 0))

            exp = getattr(c, "coupon_expires_at", None)
            exp_str = exp.strftime("%Y-%m-%d") if exp else "미설정"

            content = (
                f"{c.customer_name}님, {target_date.strftime('%m')}월 {target_date.strftime('%d')}일에 "
                f"{used_str} 이용하셨습니다.\n"
                f"잔여시간은 {remain_str}, 쿠폰 유효기간은 {exp_str} 입니다."
            )

            ok = sender.send_plain_message(
                to=c.phone_number,
                content=content,
                msg_type="쿠폰 이용 안내(일일)"
            )

            if ok:
                NotificationLog.objects.filter(pk=log.pk).update(
                    status="SENT",
                    sent_at=timezone.now(),
                    error="",
                )
                sent += 1
            else:
                NotificationLog.objects.filter(pk=log.pk).update(
                    status="FAILED",
                    error="send returned False",
                )

        mode = "REAL_SEND" if options["send"] else "DRY_RUN"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] target_date={target_date} sent={sent} skipped={skipped} broadcast={options['broadcast']}"
        ))
