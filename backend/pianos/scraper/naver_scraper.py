from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import os
import sys

# ⭐ 현재 파일의 상위 디렉토리들을 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, parent_dir)

from pianos.models import Reservation
# ⭐ 같은 폴더에 있는 utils를 직접 import
from pianos.scraper.utils import parse_reservation_datetime, parse_price


class NaverPlaceScraper:
    """네이버 스마트플레이스 예약 스크래퍼"""
    
    def __init__(self, use_existing_chrome=True, dry_run=True):
        """
        Selenium WebDriver 초기화
        Args:
            use_existing_chrome: True면 이미 열린 Chrome 사용, False면 새 창
            dry_run: True면 실제 버튼 클릭 안함 (로그만)
        """
        self.dry_run = dry_run  # ⭐ DRY_RUN 모드 추가

        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        if use_existing_chrome:
            # ⭐ 이미 실행 중인 Chrome에 연결
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            print("🔗 이미 실행 중인 Chrome에 연결합니다...")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print("✅ Chrome 연결 성공!")
            if self.dry_run:
                print("⚠️ DRY_RUN 모드: 확정/취소 버튼을 실제로 누르지 않습니다")
        except Exception as e:
            print(f"❌ Chrome 연결 실패: {e}")
            if use_existing_chrome:
                print("\n📝 해결 방법:")
                print("   1. Chrome을 완전히 종료")
                print('   2. 다음 명령으로 Chrome 실행:')
                print('      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\\selenium\\ChromeProfile"')
                print("   3. Chrome에서 네이버 스마트플레이스 로그인")
                print("   4. 다시 스크립트 실행")
            raise
        
        self.wait = WebDriverWait(self.driver, 10)
        
        # # 이미 로그인된 크롬 프로필 사용 (선택사항)
        # # chrome_options.add_argument(r'--user-data-dir=C:\Users\YourName\AppData\Local\Google\Chrome\User Data')
        
        # self.driver = webdriver.Chrome(options=chrome_options)
    
    def scrape_all_bookings(self):
        """
        현재 페이지의 모든 예약 스크래핑
        
        Returns:
            list: 예약 데이터 리스트
        """
        try:
            # 예약 행들 찾기
            booking_rows = self.driver.find_elements(
                By.CLASS_NAME, 
                "BookingListView__contents-user__xNWR6"
            )
            
            bookings = []
            
            for row in booking_rows:
                try:
                    booking_data = self._parse_booking_row(row)
                    if booking_data:
                        bookings.append(booking_data)
                except Exception as e:
                    continue
            
            return bookings
            
        except Exception as e:
            print(f"❌ 스크래핑 실패: {e}")
            return []
    
    def _parse_booking_row(self, row):
        """예약 행 하나 파싱"""
        try:
            # 예약 상태
            status = row.find_element(By.CSS_SELECTOR, ".BookingListView__state__89OjA .label").text.strip()
            
            # 예약자명
            customer_name = row.find_element(By.CLASS_NAME, "BookingListView__name-ellipsis__snplV").text.strip()
            
            # 전화번호
            phone_number = row.find_element(By.CSS_SELECTOR, ".BookingListView__phone__i04wO span").text.strip()
            
            # 예약번호
            naver_booking_id = row.find_element(By.CLASS_NAME, "BookingListView__book-number__33dBa").text.strip()
            
            # 예약일시
            datetime_str = row.find_element(By.CLASS_NAME, "BookingListView__book-date__F7BCG").text.strip()
            parsed_datetime = parse_reservation_datetime(datetime_str)
            
            # 룸명
            room_name = row.find_element(By.CSS_SELECTOR, ".BookingListView__host__a\\+wPh").get_attribute('title')
            
            # 총금액
            price = 0
            try:
                price_element = row.find_element(By.CLASS_NAME, "BookingListView__total-price__Y2qoz")
                
                # innerText 또는 textContent 사용
                price_str = price_element.get_attribute('innerText') or price_element.get_attribute('textContent') or price_element.text
                
                # 줄바꿈 제거하고 합치기
                price_str = price_str.replace('\n', '').strip()
                
                print(f"   [DEBUG] 가격 텍스트: '{price_str}'")
                
                if price_str:
                    price = parse_price(price_str)
                else:
                    print(f"   ⚠️ 가격 정보 없음")
                    
            except Exception as e:
                print(f"   ⚠️ 가격 파싱 실패: {e}")
                price = 0
            
            # ⭐ 쿠폰 여부 판단 - 옵션 컬럼만 확인!
            is_coupon = False
            try:
                option_element = row.find_element(By.CSS_SELECTOR, ".BookingListView__option__i\\+0Ta")
                option_text = option_element.get_attribute('title') or option_element.text.strip()
                
                print(f"   [DEBUG] 옵션 텍스트: '{option_text}'")
                
                # ⭐ 옵션이 비어있지 않고 "쿠폰" 키워드가 있으면 쿠폰 사용
                if option_text and option_text != '-' and '쿠폰' in option_text:
                    is_coupon = True
                    print(f"   ✅ 쿠폰 사용 예약!")
                else:
                    print(f"   ℹ️ 일반 예약")
                    
            except Exception as e:
                print(f"   ⚠️ 옵션 확인 중 에러: {e}")
                # 옵션 컬럼을 못 찾으면 일반 예약으로 간주
                is_coupon = False
            
            if not parsed_datetime:
                print(f"⚠️ 날짜 파싱 실패: {datetime_str}")
                return None
            
            booking_data = {
                'naver_booking_id': naver_booking_id,
                'customer_name': customer_name,
                'phone_number': phone_number,
                'room_name': room_name,
                'reservation_date': parsed_datetime['reservation_date'],
                'start_time': parsed_datetime['start_time'],
                'end_time': parsed_datetime['end_time'],
                'price': price,
                'reservation_status': status,
                'is_coupon': is_coupon,
            }
            
            coupon_mark = "🎫" if is_coupon else "💳"
            print(f"✅ 파싱 완료: {customer_name} - {naver_booking_id} {coupon_mark} {price:,}원")
            return booking_data
            
        except Exception as e:
            print(f"⚠️ 예약 행 파싱 에러: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_to_db(self, bookings):
        """
        스크래핑한 예약 데이터를 DB에 저장
        
        Args:
            bookings: 예약 데이터 리스트
        
        Returns:
            dict: 저장/업데이트 결과
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for booking in bookings:
            try:
                # 네이버 예약번호로 기존 예약 찾기
                reservation, created = Reservation.objects.update_or_create(
                    naver_booking_id=booking['naver_booking_id'],
                    defaults={
                        'customer_name': booking['customer_name'],
                        'phone_number': booking['phone_number'],
                        'room_name': booking['room_name'],
                        'reservation_date': booking['reservation_date'],
                        'start_time': booking['start_time'],
                        'end_time': booking['end_time'],
                        'price': booking['price'],
                        'reservation_status': booking['reservation_status'],
                    }
                )
                
                if created:
                    created_count += 1
                    print(f"✅ 새 예약 저장: {booking['naver_booking_id']}")
                else:
                    updated_count += 1
                    print(f"🔄 예약 업데이트: {booking['naver_booking_id']}")
                    
            except Exception as e:
                error_count += 1
                print(f"❌ DB 저장 에러: {e}")
        
        return {
            'created': created_count,
            'updated': updated_count,
            'error': error_count,
        }
    
    def click_pending_button(self):
        """확정대기 버튼 클릭"""
        try:
            pending_btn = self.driver.find_element(
                By.CSS_SELECTOR, 
                'input[data-tst_confirm_pending]'
            )
            
            pending_btn.click()
            time.sleep(2)
            
            print("✅ 확정대기 탭 이동")
            return True
            
        except Exception as e:
            print(f"❌ 확정대기 버튼 클릭 실패: {e}")
            return False
    
    def confirm_in_pending_tab(self, naver_booking_id):
        """확정대기 탭에서 확정 처리"""
        try:
            if self.dry_run:
                print(f"[DRY_RUN] ✅ 확정 시뮬레이션: {naver_booking_id}")
                return True
            
            # 체크박스 찾아서 클릭
            booking_rows = self.driver.find_elements(
                By.CLASS_NAME, 
                "BookingListView__contents-user__xNWR6"
            )
            
            for row in booking_rows:
                try:
                    booking_num = row.find_element(
                        By.CLASS_NAME, 
                        "BookingListView__book-number__33dBa"
                    ).text.strip()
                    
                    if booking_num == naver_booking_id:
                        checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        checkbox.click()
                        time.sleep(0.5)
                        break
                        
                except:
                    continue
            
            # 확정 버튼 클릭
            confirm_btn = self.driver.find_element(
                By.XPATH, 
                "//button[contains(text(), '확정')]"
            )
            confirm_btn.click()
            time.sleep(1)
            
            print(f"✅ 확정 완료: {naver_booking_id}")
            return True
            
        except Exception as e:
            print(f"❌ 확정 실패: {e}")
            return False

    def cancel_in_pending_tab(self, naver_booking_id):
        """확정대기 탭에서 취소 처리"""
        try:
            if self.dry_run:
                print(f"[DRY_RUN] 🚫 취소 시뮬레이션: {naver_booking_id}")
                return True
            
            # 체크박스 찾아서 클릭
            booking_rows = self.driver.find_elements(
                By.CLASS_NAME, 
                "BookingListView__contents-user__xNWR6"
            )
            
            for row in booking_rows:
                try:
                    booking_num = row.find_element(
                        By.CLASS_NAME, 
                        "BookingListView__book-number__33dBa"
                    ).text.strip()
                    
                    if booking_num == naver_booking_id:
                        checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        checkbox.click()
                        time.sleep(0.5)
                        break
                        
                except:
                    continue
            
            # 취소 버튼 클릭
            cancel_btn = self.driver.find_element(
                By.XPATH, 
                "//button[contains(text(), '취소')]"
            )
            cancel_btn.click()
            time.sleep(1)
            
            # 확인 팝업
            try:
                confirm_popup = self.driver.find_element(By.XPATH, "//button[contains(text(), '확인')]")
                confirm_popup.click()
                time.sleep(1)
            except:
                pass
            
            print(f"✅ 취소 완료: {naver_booking_id}")
            return True
            
        except Exception as e:
            print(f"❌ 취소 실패: {e}")
            return False

    def refresh_page(self):
        """페이지 새로고침"""
        self.driver.refresh()
        time.sleep(2)

    def close(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            print("🔚 브라우저 종료")