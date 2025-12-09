"""
입금 확인 (팝빌 API)
"""
import os
import sys
import django
import time
from datetime import datetime, timedelta

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from pianos.models import Reservation
from pianos.scraper.naver_scraper import NaverPlaceScraper
from pianos.automation.sms_sender import SMSSender


class PaymentChecker:
    """입금 확인 (10분마다 체크)"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        # TODO: 팝빌 API 설정
        self.corp_num = ""  # 사업자번호
        self.api_key = ""   # API 키
        self.account_number = ""  # 계좌번호
        
        self.scraper = NaverPlaceScraper(use_existing_chrome=True, dry_run=dry_run)
        self.sms_sender = SMSSender(dry_run=dry_run)
    
    def run(self):
        """메인 루프 - 10초마다 입금 확인"""
        print("=" * 60)
        print("💰 입금 확인 시스템 시작 (10초 주기)")
        if self.dry_run:
            print("⚠️ DRY_RUN 모드: DB 업데이트는 하되, 버튼 클릭/문자 발송은 안함")
        print("=" * 60)
        
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💰 입금 확인 중...")
                
                # 입금 대기 중인 예약 확인
                self.check_pending_payments()
                
                # 10분 대기
                print(f"\n⏰ 다음 확인: {(datetime.now() + timedelta(minutes=10)).strftime('%H:%M:%S')}")
                time.sleep(10)  # 10초 = 10초
                
            except KeyboardInterrupt:
                print("\n\n⏹️ 사용자에 의해 중단됨")
                break
            except Exception as e:
                print(f"❌ 입금 확인 오류: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)  # 에러 시 1분 대기
        
        self.scraper.close()
        print("\n🔚 입금 확인 시스템 종료")
    
    def check_pending_payments(self):
        """입금 대기 중인 예약 확인"""
        # 신청 상태이면서 일반 예약(쿠폰X)인 것만
        pending = Reservation.objects.filter(
            reservation_status='신청',
            is_coupon=False
        ).order_by('created_at')
        
        if not pending.exists():
            print("   ℹ️ 입금 대기 중인 예약 없음")
            return
        
        print(f"   📋 입금 대기 중인 예약: {pending.count()}건")
        
        for reservation in pending:
            print(f"\n   🔍 예약 확인: {reservation.customer_name} ({reservation.naver_booking_id})")
            print(f"      - 예약 시간: {reservation.reservation_date} {reservation.start_time}")
            print(f"      - 요금: {reservation.price:,}원")
            
            # 실제 입금 여부 확인
            if self.is_paid(reservation):
                print(f"   ✅ 입금 확인됨!")
                self.handle_payment_confirmed(reservation)
            else:
                print(f"   ⏳ 아직 입금 안됨")
    
    def is_paid(self, reservation):
        """실제 입금 여부 확인 (팝빌 API)"""
        
        if self.dry_run:
            print(f"[DRY_RUN] 팝빌 API 호출 시뮬레이션")
            print(f"[DRY_RUN]    - 예금주명: {reservation.customer_name}")
            print(f"[DRY_RUN]    - 입금액: {reservation.price:,}원")
            # DRY_RUN에서는 랜덤으로 입금 확인 (테스트용)
            # return False  # 실제로는 항상 False 반환
            return False
        
        # TODO: 팝빌 API 실제 호출
        """
        팝빌 계좌조회 API 예시:
        
        from Popbill import PopbillException, BankAccountService
        
        bankAccountService = BankAccountService(self.corp_num, self.api_key)
        
        # 오늘 거래내역 조회
        today = datetime.now().strftime('%Y%m%d')
        
        try:
            result = bankAccountService.search(
                CorpNum=self.corp_num,
                BankCode='011',  # 농협: 011
                AccountNumber=self.account_number,
                SDate=today,
                EDate=today,
                TradeType='I'  # 입금만
            )
            
            # 거래내역에서 예약자명, 금액 매칭
            for transaction in result.list:
                # 입금자명에 예약자명이 포함되어 있고
                # 금액이 정확히 일치하면
                if (reservation.customer_name in transaction.Depositor and 
                    int(transaction.TradeBalance) == reservation.price):
                    return True
            
            return False
            
        except PopbillException as e:
            print(f"   ❌ 팝빌 API 오류: {e.message}")
            return False
        """
        
        return False
    
    def handle_payment_confirmed(self, reservation):
        """입금 확인 후 처리"""
        try:
            print(f"   🔄 예약 확정 처리 중...")
            
            # 1. 네이버 확정 버튼 클릭
            success = self.scraper.confirm_booking(reservation.naver_booking_id)
            
            if not success:
                print(f"   ❌ 네이버 확정 실패 - 수동 처리 필요")
                return
            
            # 2. 완료 문자 발송
            print(f"   📤 예약 확정 문자 발송 중...")
            self.sms_sender.send_confirm_message(reservation)
            
            # 3. DB 상태 업데이트
            reservation.reservation_status = '확정'
            reservation.complete_sms_status = '전송완료'
            reservation.save()
            
            print(f"   ✅ 입금 확인 처리 완료!")
            print(f"      - 예약 상태: 확정")
            print(f"      - 완료 문자: 전송완료")
            
        except Exception as e:
            print(f"   ❌ 입금 확인 처리 오류: {e}")
            import traceback
            traceback.print_exc()


def main():
    """메인 실행 함수"""
    # DRY_RUN 모드 (DB 업데이트 O, 버튼 클릭/문자 발송 X)
    checker = PaymentChecker(dry_run=True)
    checker.run()


if __name__ == "__main__":
    main()