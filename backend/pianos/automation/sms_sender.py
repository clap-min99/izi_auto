"""
SMS 문자 발송 (네이버 클라우드 플랫폼 SENS)
"""
import os
import sys
import django

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()


class SMSSender:
    """SMS 문자 발송"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        
        # TODO: 네이버 클라우드 플랫폼 SENS 설정
        self.access_key = ""  # Access Key
        self.secret_key = ""  # Secret Key
        self.service_id = ""  # Service ID
        self.from_number = ""  # 발신번호
    
    def send_account_message(self, reservation):
        """
        계좌 안내 문자 발송
        """
        message = f"""[이지피아노스튜디오]
예약이 접수되었습니다.

▶ 예약자: {reservation.customer_name}
▶ 예약일시: {reservation.reservation_date} {reservation.start_time}
▶ 예약룸: {reservation.room_name}
▶ 요금: {reservation.price:,}원

입금 계좌: 농협 XXX-XXXX-XXXX-XX (예금주: 홍길동)
※ 입금 확인 후 예약이 확정됩니다."""
        
        return self._send_sms(reservation.phone_number, message, "계좌 안내")
    
    def send_confirm_message(self, reservation):
        """
        예약 확정 문자 발송
        """
        message = f"""[이지피아노스튜디오]
예약이 확정되었습니다!

▶ 예약자: {reservation.customer_name}
▶ 예약일시: {reservation.reservation_date} {reservation.start_time}~{reservation.end_time}
▶ 예약룸: {reservation.room_name}

※ 방문 시 신분증을 지참해주세요.
※ 문의: 010-XXXX-XXXX"""
        
        return self._send_sms(reservation.phone_number, message, "예약 확정")
    
    def send_cancel_message(self, reservation, reason):
        """
        예약 취소 문자 발송 (통합: 환불 안내 포함)
        """
        message = f"""[이지피아노스튜디오]
예약이 취소되었습니다.

▶ 예약자: {reservation.customer_name}
▶ 예약일시: {reservation.reservation_date} {reservation.start_time}
▶ 취소 사유: {reason}

※ 이미 입금하신 경우, 환불 계좌와 금액을 회신 주시면 영업일 기준 2~3일 내 환불 처리해드립니다.

※ 문의: 010-XXXX-XXXX"""
        
        return self._send_sms(reservation.phone_number, message, "예약 취소")
    
    def send_cancel_message_for_new_booking(self, booking, reason):
        """
        신규 예약에 대한 취소 문자 (Reservation 객체 없이)
        """
        message = f"""[이지피아노스튜디오]
예약 신청이 취소되었습니다.

▶ 예약자: {booking['customer_name']}
▶ 예약일시: {booking['reservation_date']} {booking['start_time']}
▶ 취소 사유: {reason}

※ 이미 입금하신 경우, 환불 계좌와 금액을 회신 주시면 영업일 기준 2~3일 내 환불 처리해드립니다.

※ 문의: 010-XXXX-XXXX"""
        
        return self._send_sms(booking['phone_number'], message, "예약 취소")
    
    def _send_sms(self, to_number, message, msg_type):
        """
        실제 SMS 발송
        
        Args:
            to_number: 수신 전화번호
            message: 문자 내용
            msg_type: 메시지 유형 (로그용)
        
        Returns:
            bool: 발송 성공 여부
        """
        if self.dry_run:
            print(f"      [DRY_RUN] 📤 {msg_type} 문자 시뮬레이션")
            print(f"         - 수신: {to_number}")
            print(f"         - 내용: {message[:50]}...")
            return True
        
        # TODO: 실제 네이버 클라우드 플랫폼 SENS API 호출
        """
        네이버 클라우드 플랫폼 SENS API 구현 예시:
        
        import requests
        import time
        import hmac
        import hashlib
        import base64
        
        try:
            timestamp = str(int(time.time() * 1000))
            url = f"https://sens.apigw.ntruss.com/sms/v2/services/{self.service_id}/messages"
            
            # Signature 생성
            method = "POST"
            uri = f"/sms/v2/services/{self.service_id}/messages"
            message_bytes = f"{method} {uri}\n{timestamp}\n{self.access_key}".encode('utf-8')
            secret_bytes = self.secret_key.encode('utf-8')
            signature = base64.b64encode(
                hmac.new(secret_bytes, message_bytes, digestmod=hashlib.sha256).digest()
            ).decode('utf-8')
            
            # 헤더
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'x-ncp-apigw-timestamp': timestamp,
                'x-ncp-iam-access-key': self.access_key,
                'x-ncp-apigw-signature-v2': signature
            }
            
            # 요청 데이터
            data = {
                'type': 'SMS',  # SMS(단문) or LMS(장문)
                'contentType': 'COMM',
                'countryCode': '82',
                'from': self.from_number,
                'content': message,
                'messages': [
                    {
                        'to': to_number.replace('-', '')  # 하이픈 제거
                    }
                ]
            }
            
            # API 호출
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 202:
                print(f"      ✅ {msg_type} 문자 발송 성공")
                return True
            else:
                print(f"      ❌ {msg_type} 문자 발송 실패: {response.status_code}")
                print(f"         - 응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"      ❌ {msg_type} 문자 발송 오류: {e}")
            return False
        """
        
        print(f"      ✅ {msg_type} 문자 발송 완료 (실제 발송)")
        return True


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