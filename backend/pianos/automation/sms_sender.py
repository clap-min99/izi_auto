"""
SMS 문자 발송 (네이버 클라우드 플랫폼 SENS)
"""
import os
import sys
import django
import time
from datetime import time as dt_time

import requests

import hmac
import hashlib
import base64
from typing import Optional, Dict

from pianos.models import RoomPassword

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from pianos.models import MessageTemplate, StudioPolicy  # noqa
from pianos.message_templates import DEFAULT_TEMPLATES, render_template  # noqa


class SMSSender:
    """SMS 문자 발송 (템플릿 기반)"""

    # 새벽 시간대(원하는대로 조정)
    DAWN_START = dt_time(0, 0)
    DAWN_END = dt_time(6, 0)

    def __init__(self, dry_run=True):
        self.dry_run = dry_run

        # SENS 설정 (환경변수로 받는 걸 추천)
        self.access_key = os.getenv("NCP_ACCESS_KEY", "")
        self.secret_key = os.getenv("NCP_SECRET_KEY", "")
        self.service_id = os.getenv("NCP_SENS_SERVICE_ID", "")
        self.from_number = os.getenv("NCP_SENS_FROM", "")

    # -----------------------------
    # 1) 공통: 템플릿 로드/렌더/컨텍스트
    # -----------------------------
    def _get_template_text(self, code: str) -> str:
        """
        DB 템플릿(활성) 우선, 없으면 DEFAULT_TEMPLATES fallback
        """
        try:
            tpl = MessageTemplate.objects.filter(code=code, is_active=True).first()
            if tpl and tpl.content:
                return tpl.content
        except Exception:
            # Django 초기화/DB 문제 시에도 DEFAULT로 fallback
            pass

        default = DEFAULT_TEMPLATES.get(code)
        if not default:
            # 최후 fallback
            return "[{studio}] 메시지 템플릿이 설정되지 않았습니다."
        return default["content"]

    def _is_exam_period(self, reservation_date) -> bool:
        policy = StudioPolicy.objects.first()
        if not policy or not policy.exam_start_date or not policy.exam_end_date:
            return False
        return policy.exam_start_date <= reservation_date <= policy.exam_end_date

    def _is_dawn_time(self, start_time) -> bool:
        if not start_time:
            return False
        return self.DAWN_START <= start_time <= self.DAWN_END

    def _build_ctx(self, reservation, extra: Optional[Dict] = None) -> dict:
        # 템플릿 키들(DEFAULT_TEMPLATES 기준)에 맞춰 컨텍스트 구성
        room_name = getattr(reservation, "room_name", "")
        pw = ""
        if room_name:
            rp = RoomPassword.objects.filter(room_name=room_name).first()
            pw = rp.room_pw if rp else ""
        ctx = {
            "customer_name": getattr(reservation, "customer_name", ""),
            "room_name": room_name,
            "room_pw": pw,
            
            "date": str(getattr(reservation, "reservation_date", "")),
            "start_time": str(getattr(reservation, "start_time", ""))[:5],
            "end_time": str(getattr(reservation, "end_time", ""))[:5],

            "price": f"{getattr(reservation, 'price', 0):,}",
            "add_person_count": str(getattr(reservation, "extra_people_qty", 0)),

            # 취소/쿠폰 관련(없으면 기본값)
            "remaining_minutes": str(extra.get("remaining_minutes", "")) if extra else "",
            "duration_minutes": str(extra.get("duration_minutes", "")) if extra else "",
            "coupon_category": str(extra.get("coupon_category", "")) if extra else "",
            "room_category": str(extra.get("room_category", "")) if extra else "",
        }
        # if extra:
        #     ctx.update(extra)
        return ctx

    def _send_by_template(self, to_number: str, template_code: str, reservation=None, extra_ctx=None, msg_type=""):
        text = self._get_template_text(template_code)
        ctx = self._build_ctx(reservation, extra_ctx or {})
        message = render_template(text, ctx)
        
        print(f"      🧩 TEMPLATE = {template_code}  (msg_type={msg_type or template_code})")
        if extra_ctx:
            print(f"         + extra_ctx keys = {list(extra_ctx.keys())}")
        
        return self._send_sms(to_number, message, msg_type or template_code)

    # -----------------------------
    # 2) 상황별: 템플릿 선택 규칙
    # -----------------------------
    def send_account_message(self, reservation):
        """
        [일반 예약] 입금 안내 문자:
        - 기본 1통은 (대리/인원추가/둘다/기본) 중 택1
        - 입시기간이면 PAYMENT_GUIDE_EXAM 1통 추가 발송
        - 새벽시간이면 DAWN_CONFIRM 1통 추가 발송
        """
        to_number = reservation.phone_number

        is_proxy = bool(getattr(reservation, "is_proxy", False))
        add_qty = int(getattr(reservation, "extra_people_qty", 0) or 0)

        # 기본 1통
        if is_proxy and add_qty > 0:
            base_code = "PAYMENT_GUIDE_ADD_PERSON_AND_PROXY"
        elif is_proxy:
            base_code = "PAYMENT_GUIDE_PROXY"
        elif add_qty > 0:
            base_code = "PAYMENT_GUIDE_ADD_PERSON"
        else:
            base_code = "PAYMENT_GUIDE"

        ok = self._send_by_template(to_number, base_code, reservation, msg_type="계좌 안내(기본)")

        # 입시기간이면 1통 더
        if self._is_exam_period(reservation.reservation_date):
            ok2 = self._send_by_template(to_number, "PAYMENT_GUIDE_EXAM", reservation, msg_type="계좌 안내(입시기간)")
            ok = ok and ok2

        # 새벽이면 1통 더
        if self._is_dawn_time(reservation.start_time):
            ok3 = self._send_by_template(to_number, "DAWN_CONFIRM", reservation, msg_type="새벽 예약 확인")
            ok = ok and ok3

        return ok

    def send_confirm_message(self, reservation):
        """
        예약 확정 문자:
        - 입시기간이면 CONFIRMATION_EXAM
        - 아니면 CONFIRMATION
        """
        to_number = reservation.phone_number
        if self._is_exam_period(reservation.reservation_date):
            code = "CONFIRMATION_EXAM"
            msg_type = "예약 확정(입시기간)"
        else:
            code = "CONFIRMATION"
            msg_type = "예약 확정"

        return self._send_by_template(to_number, code, reservation, msg_type=msg_type)

    def send_cancel_message(self, reservation, reason: str, customer=None):
        """
        취소는 reason 문자열 → 템플릿 코드 매핑.
        매칭 안 되면 문자 발송하지 않고 False 반환(요청사항).
        """
        to_number = reservation.phone_number
        reason = reason or ""

        if "잔여" in reason and "부족" in reason:
            remaining = ""
            if customer is not None and hasattr(customer, "remaining_time"):
                remaining = customer.remaining_time  # minutes

            extra_ctx = {
                "remaining_minutes": str(remaining),
                "duration_minutes": reservation.get_duration_minutes() if hasattr(reservation, "get_duration_minutes") else "",
            }
            return self._send_by_template(
                to_number,
                "COUPON_CANCEL_TIME",
                reservation,
                extra_ctx,
                msg_type="쿠폰 취소(잔여시간 부족)"
            )
        if "불일치" in reason or "유형" in reason:
            return self._send_by_template(to_number, "COUPON_CANCEL_TYPE", reservation, {}, msg_type="쿠폰 취소(유형 불일치)")

        if "선입금" in reason or "동시간대" in reason:
            return self._send_by_template(to_number, "NORMAL_CANCEL_CONFLICT", reservation, {}, msg_type="일반 취소(선입금 우선)")
        
        if ("입금" in reason and ("기한" in reason or "30분" in reason)) or ("자동 취소" in reason and "입금" in reason):
            return self._send_by_template(to_number, "NORMAL_CANCEL_TIMEOUT", reservation, {}, msg_type="일반 취소(입금기한 초과)")

        print(f"      ⚠️ 취소 템플릿 매칭 실패 → 문자 미발송 (reason='{reason}')")
        return False



    
    def _send_sms(self, to_number, message, msg_type):
        if self.dry_run:
            print(f"      [DRY_RUN] 📤 {msg_type} 문자 시뮬레이션")
            print(f"         - 수신: {to_number}")
            print(f"         - 내용: {message}")
            return True

        try:
            timestamp = str(int(time.time() * 1000))

            uri = f"/sms/v2/services/{self.service_id}/messages"
            url = f"https://sens.apigw.ntruss.com{uri}"

            # Signature 생성
            message_to_sign = f"POST {uri}\n{timestamp}\n{self.access_key}"
            signing_key = self.secret_key.encode("utf-8")
            signature = base64.b64encode(
                hmac.new(
                    signing_key,
                    message_to_sign.encode("utf-8"),
                    hashlib.sha256
                ).digest()
            ).decode("utf-8")

            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "x-ncp-apigw-timestamp": timestamp,
                "x-ncp-iam-access-key": self.access_key,
                "x-ncp-apigw-signature-v2": signature,
            }

            data = {
                "type": "LMS",          # 단문 SMS
                "contentType": "COMM",
                "countryCode": "82",
                "from": self.from_number,
                "content": message,
                "messages": [
                    {
                        "to": to_number.replace("-", "")
                    }
                ],
            }

            response = requests.post(url, headers=headers, json=data, timeout=5)

            if response.status_code == 202:
                print(f"      ✅ {msg_type} 문자 발송 성공")
                return True

            print(f"      ❌ {msg_type} 문자 발송 실패")
            print(f"         - status: {response.status_code}")
            print(f"         - body: {response.text}")
            return False

        except Exception as e:
            print(f"      ❌ {msg_type} 문자 발송 예외 발생: {e}")
            return False



def main():
    """메인 실행 함수 (테스트용)"""
    print("=" * 60)
    print("📤 SMS 발송 시스템 (단독 실행)")
    print("=" * 60)
    
    # DRY_RUN 모드
    sender = SMSSender(dry_run=True)
    
    # 테스트 예약 객체 생성
    class TestReservation:
        def __init__(self):
            self.customer_name = "테스트"
            self.phone_number = "010-1234-5678"
            self.reservation_date = "2025-12-10"
            self.start_time = "14:00"
            self.end_time = "16:00"
            self.room_name = "Room1"
            self.price = 20000
    
    test_res = TestReservation()
    
    # 1. 계좌 안내 문자
    print("\n1. 계좌 안내 문자")
    sender.send_account_message(test_res)
    
    # 2. 예약 확정 문자
    print("\n2. 예약 확정 문자")
    sender.send_confirm_message(test_res)
    
    # 3. 예약 취소 문자 (통합: 환불 안내 포함)
    print("\n3. 예약 취소 문자 (환불 안내 포함)")
    sender.send_cancel_message(test_res, "쿠폰 예약과 시간대 충돌")


if __name__ == "__main__":
    main()