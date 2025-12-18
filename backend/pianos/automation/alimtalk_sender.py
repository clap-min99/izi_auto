# alimtalk_sender.py

import base64
import hashlib
import hmac
import time
import requests
from django.conf import settings


class AlimTalkSender:
    """
    NCP SENS 알림톡 v2 발송
    - POST https://sens.apigw.ntruss.com/alimtalk/v2/services/{serviceId}/messages
    - headers: x-ncp-apigw-timestamp, x-ncp-iam-access-key, x-ncp-apigw-signature-v2
    """

    def __init__(self):
        self.access_key = settings.NCP_ACCESS_KEY
        self.secret_key = settings.NCP_SECRET_KEY
        self.service_id = settings.NCP_ALIMTALK_SERVICE_ID
        self.plus_friend_id = settings.NCP_ALIMTALK_PLUS_FRIEND_ID  # 예: "@채널명"
        self.base_url = "https://sens.apigw.ntruss.com"

    def _make_signature(self, method: str, url_path: str, timestamp_ms: str) -> str:
        message = f"{method} {url_path}\n{timestamp_ms}\n{self.access_key}"
        signing_key = self.secret_key.encode("utf-8")
        signature = hmac.new(signing_key, message.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(signature).decode("utf-8")

    def send_alimtalk(self, to_phone: str, template_code: str, content: str, *, use_sms_failover=False, failover=None):
        """
        content는 '템플릿과 정확히 일치'해야 하고(변수 부분은 실제 값으로 치환해서 보냄),
        template_code는 승인된 템플릿 코드.
        """
        url_path = f"/alimtalk/v2/services/{self.service_id}/messages"
        url = self.base_url + url_path

        timestamp_ms = str(int(time.time() * 1000))
        signature = self._make_signature("POST", url_path, timestamp_ms)

        payload = {
            "plusFriendId": self.plus_friend_id,
            "templateCode": template_code,
            "messages": [
                {
                    "to": to_phone,
                    "content": content,
                }
            ],
        }

        if use_sms_failover:
            payload["messages"][0]["useSmsFailover"] = True
            payload["messages"][0]["failoverConfig"] = failover or {
                "type": "LMS",
                "from": settings.NCP_SMS_FROM,
                "subject": "알림",
                "content": content,
            }

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "x-ncp-apigw-timestamp": timestamp_ms,
            "x-ncp-iam-access-key": self.access_key,
            "x-ncp-apigw-signature-v2": signature,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        # 성공/실패 모두 응답을 그대로 리턴해서 호출부에서 로깅
        return resp
