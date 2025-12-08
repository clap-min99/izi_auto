"""
스크래퍼 실행 스크립트
"""
import os
import sys
import django

# Django 프로젝트 루트 경로 추가
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

# Django 설정 로드
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izipiano.settings')
django.setup()

# ⭐ 같은 폴더에서 직접 import
from naver_scraper import NaverPlaceScraper


def main():
    """메인 실행 함수"""
    # 네이버 스마트플레이스 예약 관리 URL (실제 URL로 변경 필요)
    NAVER_BOOKING_URL = "https://partner.booking.naver.com/bizes/686937/booking-list-view?bookingBusinessId=686937"
    
    scraper = NaverPlaceScraper()
    
    try:
        print("🚀 스크래핑 시작!")
        
        # 1. 예약 스크래핑
        bookings = scraper.scrape_bookings(NAVER_BOOKING_URL)
        
        print(f"\n📊 스크래핑 결과: {len(bookings)}개 예약")
        
        # 2. DB 저장
        if bookings:
            result = scraper.save_to_db(bookings)
            print(f"\n💾 DB 저장 결과:")
            print(f"  - 새로 생성: {result['created']}개")
            print(f"  - 업데이트: {result['updated']}개")
            print(f"  - 에러: {result['error']}개")
        else:
            print("\n⚠️ 스크래핑된 예약이 없습니다.")
        
    finally:
        print("🔚 스크래핑 완료 (Chrome 창은 유지됩니다)")


if __name__ == "__main__":
    main()