"""
계좌 내역 동기화 (팝빌 API)
5분 주기로 최신 거래 내역을 DB에 저장
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Django 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

from pianos.models import AccountTransaction


class AccountSyncManager:
    """계좌 내역 동기화 매니저 (5분 주기)"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        
        # TODO: 팝빌 API 설정
        self.corp_num = ""  # 사업자번호
        self.api_key = ""   # API 키
        self.bank_code = "011"  # 은행코드 (농협: 011)
        self.account_number = ""  # 계좌번호
        
    def sync_transactions(self):
        """
        팝빌 API로부터 최근 거래 내역 가져와서 DB 동기화
        """
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💳 계좌 내역 동기화 시작...")
        
        try:
            # 1. 팝빌 API 호출 (최근 24시간 내역)
            transactions = self.fetch_from_popbill()
            
            if not transactions:
                print("   ℹ️ 새로운 거래 내역 없음")
                return 0
            
            # 2. DB에 저장 (중복 제거)
            new_count = self.save_transactions(transactions)
            
            print(f"   ✅ 신규 거래 내역: {new_count}건")
            
            return new_count
            
        except Exception as e:
            print(f"   ❌ 계좌 내역 동기화 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def fetch_from_popbill(self):
        """
        팝빌 API 호출하여 거래 내역 조회
        
        Returns:
            list: [
                {
                    'transaction_id': '거래고유번호',
                    'date': date,
                    'time': time,
                    'type': '입금' | '출금',
                    'amount': int,
                    'balance': int,
                    'depositor': '입금자명',
                    'memo': '거래메모'
                },
                ...
            ]
        """
        if self.dry_run:
            print("   [DRY_RUN] 팝빌 API 호출 시뮬레이션")
            return []
        
        # TODO: 실제 팝빌 API 호출
        """
        팝빌 계좌조회 API 구현 예시:
        
        from Popbill import PopbillException, BankAccountService
        
        try:
            # 팝빌 서비스 초기화
            bankAccountService = BankAccountService(self.corp_num, self.api_key)
            
            # 조회 기간 설정 (최근 24시간)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            
            sdate = start_date.strftime('%Y%m%d')
            edate = end_date.strftime('%Y%m%d')
            
            # 거래내역 조회
            result = bankAccountService.search(
                CorpNum=self.corp_num,
                BankCode=self.bank_code,
                AccountNumber=self.account_number,
                SDate=sdate,
                EDate=edate,
                TradeType='I',  # 'I': 입금만, 'O': 출금만, '': 전체
                Order='D'  # 'D': 내림차순(최신순), 'A': 오름차순
            )
            
            # 결과 변환
            transactions = []
            for item in result.list:
                # 거래고유번호 생성 (날짜+시간+일련번호로 고유성 보장)
                transaction_id = f"{item.TranDate}{item.TranTime}{item.SerialNum}"
                
                # 거래 시간 파싱
                tran_date = datetime.strptime(item.TranDate, '%Y%m%d').date()
                tran_time = datetime.strptime(item.TranTime, '%H%M%S').time()
                
                transactions.append({
                    'transaction_id': transaction_id,
                    'date': tran_date,
                    'time': tran_time,
                    'type': '입금' if item.TranType == 'I' else '출금',
                    'amount': int(item.TradeBalance),  # 거래금액
                    'balance': int(item.Balance),  # 거래후잔액
                    'depositor': item.Depositor or '',  # 입금자명
                    'memo': item.Memo or ''  # 거래메모
                })
            
            return transactions
            
        except PopbillException as e:
            print(f"   ❌ 팝빌 API 오류 [{e.code}]: {e.message}")
            return []
        except Exception as e:
            print(f"   ❌ 팝빌 API 호출 실패: {e}")
            return []
        """
        
        return []
    
    def save_transactions(self, transactions):
        """
        거래 내역을 DB에 저장 (중복 제거)
        
        Args:
            transactions: fetch_from_popbill()에서 반환된 리스트
        
        Returns:
            int: 신규 저장된 거래 개수
        """
        new_count = 0
        
        for trans in transactions:
            try:
                # transaction_id로 중복 체크
                obj, created = AccountTransaction.objects.get_or_create(
                    transaction_id=trans['transaction_id'],
                    defaults={
                        'transaction_date': trans['date'],
                        'transaction_time': trans['time'],
                        'transaction_type': trans['type'],
                        'amount': trans['amount'],
                        'balance': trans['balance'],
                        'depositor_name': trans['depositor'],
                        'memo': trans['memo'],
                        'match_status': '확정전'  # 기본값
                    }
                )
                
                if created:
                    new_count += 1
                    print(f"      ➕ {trans['type']} | {trans['depositor']} | {trans['amount']:,}원")
                    
            except Exception as e:
                print(f"      ❌ 저장 실패: {e}")
                continue
        
        return new_count


def main():
    """메인 실행 함수 (단독 테스트용)"""
    print("=" * 60)
    print("💳 계좌 내역 동기화 시스템 (단독 실행)")
    print("=" * 60)
    
    # DRY_RUN 모드
    sync_manager = AccountSyncManager(dry_run=True)
    
    # 동기화 실행
    sync_manager.sync_transactions()


if __name__ == "__main__":
    main()