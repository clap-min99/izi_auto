"""
SMS 문자 발송 (네이버 클라우드 SENS)
"""


class SMSSender:
    """문자 발송"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run  # ⭐ DRY_RUN 모드
        
        # TODO: 네이버 클라우드 SENS API 설정
        self.service_id = ""  # 서비스 ID (예: ncp:sms:kr:123456789:my-service)
        self.access_key = ""  # Access Key ID
        self.secret_key = ""  # Secret Key
        self.from_number = "010-0000-0000"  # 발신번호 (실제 번호로 변경)
        self.api_url = f"https://sens.apigw.ntruss.com/sms/v2/services/{self.service_id}/messages"
    
    def send_sms(self, to_number, message):
        """
        실제 SMS 발송 (네이버 클라우드 SENS API)
        """
        if self.dry_run:
            return True
        
        # TODO: 실제 SENS API 호출
        """
        네이버 클라우드 SENS API 예시:
        
        import requests
        import time
        import hmac
        import hashlib
        import base64
        
        timestamp = str(int(time.time() * 1000))
        access_key = self.access_key
        secret_key = self.secret_key
        
        # 서명 생성
        method = "POST"
        uri = f"/sms/v2/services/{self.service_id}/messages"
        message_bytes = method + " " + uri + "\n" + timestamp + "\n" + access_key
        message_bytes = bytes(message_bytes, 'UTF-8')
        signing_key = base64.b64encode(
            hmac.new(
                bytes(secret_key, 'UTF-8'), 
                message_bytes, 
                digestmod=hashlib.sha256
            ).digest()
        )
        
        # 헤더
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'x-ncp-apigw-timestamp': timestamp,
            'x-ncp-iam-access-key': access_key,
            'x-ncp-apigw-signature-v2': signing_key
        }
        
        # 요청 바디
        body = {
            "type": "SMS",
            "contentType": "COMM",
            "countryCode": "82",
            "from": self.from_number,
            "content": message,
            "messages": [
                {
                    "to": to_number
                }
            ]
        }
        
        try:
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=body
            )
            
            if response.status_code == 202:
                print(f"   ✅ 문자 발송 성공")
                return True
            else:
                print(f"   ❌ 문자 발송 실패: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ 문자 발송 오류: {e}")
            return False
        """
        
        return True
    
    def send_account_message(self, reservation):
        """계좌번호 안내 문자"""
        message = f"""[이지피아노스튜디오]
{reservation.customer_name}님, 예약이 접수되었습니다.

예약정보:
- 룸: {reservation.room_name}
- 시간: {reservation.reservation_date} {reservation.start_time}~{reservation.end_time}
- 요금: {reservation.price:,}원

입금계좌: 농협 XXX-XXXX-XXXX-XX (예금주: XXX)

입금 확인 후 예약이 확정됩니다.
감사합니다."""
        
        if self.dry_run:
            print(f"[DRY_RUN] 📤 문자 발송 시뮬레이션 (계좌번호)")
            print(f"[DRY_RUN]    수신: {reservation.phone_number}")
            print(f"[DRY_RUN]    내용:")
            for line in message.split('\n')[:5]:  # 처음 5줄만
                print(f"[DRY_RUN]       {line}")
            print(f"[DRY_RUN]       ...")
            return True
        
        return self.send_sms(reservation.phone_number, message)
    
    def send_conflict_message(self, reservation):
        """시간 충돌 안내 문자"""
        message = f"""[이지피아노스튜디오]
{reservation.customer_name}님, 죄송합니다.

요청하신 시간대({reservation.reservation_date} {reservation.start_time})는 이미 예약이 완료되었습니다.

다른 시간대로 예약 부탁드립니다.
감사합니다."""
        
        if self.dry_run:
            print(f"[DRY_RUN] 📤 문자 발송 시뮬레이션 (충돌 안내)")
            print(f"[DRY_RUN]    수신: {reservation.phone_number}")
            print(f"[DRY_RUN]    사유: 시간대 충돌")
            return True
        
        return self.send_sms(reservation.phone_number, message)
    
    def send_insufficient_message(self, reservation, customer):
        """쿠폰 잔여시간 부족 안내"""
        if customer:
            remaining = customer.remaining_time
            required = reservation.get_duration_minutes()
            message = f"""[이지피아노스튜디오]
{reservation.customer_name}님,

쿠폰 잔여시간이 부족합니다.
- 잔여시간: {remaining}분
- 요청시간: {required}분

충전 후 다시 예약해주세요.
감사합니다."""
        else:
            message = f"""[이지피아노스튜디오]
{reservation.customer_name}님,

쿠폰 고객 정보가 없습니다.
고객센터로 문의해주세요."""
        
        if self.dry_run:
            print(f"[DRY_RUN] 📤 문자 발송 시뮬레이션 (쿠폰 부족)")
            print(f"[DRY_RUN]    수신: {reservation.phone_number}")
            if customer:
                print(f"[DRY_RUN]    잔여: {customer.remaining_time}분")
                print(f"[DRY_RUN]    필요: {reservation.get_duration_minutes()}분")
            else:
                print(f"[DRY_RUN]    사유: 쿠폰 고객 정보 없음")
            return True
        
        return self.send_sms(reservation.phone_number, message)
    
    def send_confirm_message(self, reservation):
        """예약 확정 안내 문자"""
        message = f"""[이지피아노스튜디오]
{reservation.customer_name}님, 예약이 확정되었습니다!

예약정보:
- 룸: {reservation.room_name}
- 시간: {reservation.reservation_date} {reservation.start_time}~{reservation.end_time}

이용해주셔서 감사합니다."""
        
        if self.dry_run:
            print(f"[DRY_RUN] 📤 문자 발송 시뮬레이션 (예약 확정)")
            print(f"[DRY_RUN]    수신: {reservation.phone_number}")
            print(f"[DRY_RUN]    사유: 입금 확인 완료")
            return True
        
        return self.send_sms(reservation.phone_number, message)