from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from pianos.automation.alimtalk_sender import AlimTalkSender
from pianos.models import Reservation


def _fmt_dt(r: Reservation) -> str:
    # 2025-12-18(목) 14:00~15:00 형태로 보이게
    d = r.reservation_date
    dow = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
    return f"{d.strftime('%Y-%m-%d')}({dow}) {r.start_time.strftime('%H:%M')}~{r.end_time.strftime('%H:%M')}"


class Command(BaseCommand):
    help = "사장님에게 예약자명/전화번호/예약일시/요청사항 알림톡 발송"

    def handle(self, *args, **options):
        sender = AlimTalkSender()

        owner_phone = getattr(settings, "OWNER_PHONE", "")
        if not owner_phone:
            self.stdout.write(self.style.ERROR("settings.OWNER_PHONE 이 설정되어 있지 않습니다."))
            return

        # ✅ 발송 대상: 신청 + 사장님 알림톡 전송전 + 요청사항 有
        qs = Reservation.objects.filter(
            reservation_status="신청",
            owner_request_noti_status="전송전",
        ).exclude(
            Q(request_comment__isnull=True) | Q(request_comment__exact="")
        )

        sent = failed = 0

        for r in qs:
            request_comment = (r.request_comment or "").strip()
            request_line = request_comment if request_comment else "없음"

            content = (
                "예약자가 요청사항을 남겼습니다.\n"
                f"예약자명: {r.customer_name}\n"
                f"전화번호: {r.phone_number}\n"
                f"예약일시: {_fmt_dt(r)}\n"
                f"요청사항: {request_comment}"
            )

            try:
                resp = sender.send_alimtalk(
                    to_phone=owner_phone,
                    template_code="OWNER_RESERVATION_NOTICE",  # 콘솔에서 만든 템플릿 코드로 교체
                    content=content,
                    use_sms_failover=False,
                )

                if 200 <= resp.status_code < 300:
                    r.owner_request_noti_status = "전송완료"
                    r.save(update_fields=["owner_request_noti_status", "updated_at"])
                    sent += 1
                else:
                    r.owner_request_noti_status = "전송실패"
                    r.save(update_fields=["owner_request_noti_status", "updated_at"])
                    failed += 1

            except Exception:
                r.owner_request_noti_status = "전송실패"
                r.save(update_fields=["owner_request_noti_status", "updated_at"])
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f"[{timezone.localdate()}] sent={sent} failed={failed} total={qs.count()}"
        ))
