from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

import time
import os
import sys
import re

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
            self.driver = self._connect_existing_chrome(chrome_options)
        else:
            # 새 Chrome 실행
            print("🆕 새 Chrome 창을 실행합니다...")
            self.driver = self._start_new_chrome(chrome_options)

    def _connect_existing_chrome(self, chrome_options):
        """이미 실행 중인 Chrome에 연결"""
        try:
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ 기존 Chrome 연결 성공")
            return driver
        except Exception as e:
            print(f"❌ 기존 Chrome 연결 실패: {e}")
            raise

    def _start_new_chrome(self, chrome_options):
        """새 Chrome 브라우저 시작"""
        try:
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ 새 Chrome 실행 성공")
            return driver
        except Exception as e:
            print(f"❌ 새 Chrome 실행 실패: {e}")
            raise

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
            
            # print(f"📄 예약 행 {len(booking_rows)}개 발견")
            
            for row in booking_rows:
                booking = self._parse_booking_row(row)
                if booking:
                    bookings.append(booking)
            
            # print(f"✅ 예약 스크래핑 완료: {len(bookings)}건")
            return bookings
        
        except Exception as e:
            print(f"❌ 예약 스크래핑 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_booking_row(self, row):
        """예약 행 하나 파싱"""
        try:
            # 1) 상태 (확정 / 신청 등)
            status_el = row.find_element(
                By.CSS_SELECTOR,
                ".BookingListView__state__89OjA .label"
            )
            status = status_el.text.strip()

            # 2) 예약자 이름
            name_el = row.find_element(
                By.CLASS_NAME,
                "BookingListView__name-ellipsis__snplV"
            )
            customer_name = name_el.text.strip()

            # 3) 전화번호
            phone_el = row.find_element(
                By.CSS_SELECTOR,
                ".BookingListView__phone__i04wO span"
            )
            phone_number = phone_el.text.strip()

            # 4) 네이버 예약번호
            raw_booking_id = row.find_element(
                By.CLASS_NAME,
                "BookingListView__book-number__33dBa"
            ).text.strip()

            m = re.search(r"\d+", raw_booking_id)
            naver_booking_id = m.group(0) if m else raw_booking_id  # fallback

            # 5) 예약일시 "25. 12. 10.(수) 오전 11:00~12:00"
            datetime_str = row.find_element(
                By.CLASS_NAME,
                "BookingListView__book-date__F7BCG"
            ).text.strip()
            parsed_datetime = parse_reservation_datetime(datetime_str)

            # 파싱 실패 시 이 행은 스킵
            if not parsed_datetime:
                print(f"   ⚠️ 날짜/시간 파싱 실패: {datetime_str}")
                return None

            # utils.py 정의에 맞게 키 사용
            reservation_date = parsed_datetime["reservation_date"]
            start_time = parsed_datetime["start_time"]
            end_time = parsed_datetime["end_time"]

            # 6) 룸 이름 (title 속성에 들어 있음)
            room_el = row.find_element(
                By.CSS_SELECTOR,
                ".BookingListView__host__a\\+wPh"
            )
            room_name = room_el.get_attribute("title") or room_el.text.strip()

            # 7) 총 금액 "11,000원"
            price = 0
            try:
                price_el = row.find_element(
                    By.CLASS_NAME,
                    "BookingListView__total-price__Y2qoz"
                )
                price_str = (
                    price_el.get_attribute("innerText")
                    or price_el.get_attribute("textContent")
                    or price_el.text
                )
                price_str = price_str.replace("\n", "").strip()
                if price_str:
                    price = parse_price(price_str)
            except Exception as e:
                print(f"   ⚠️ 가격 파싱 실패: {e}")

            # 8) 쿠폰 여부: 옵션 칸에 "쿠폰사용"이 있으면 True
            is_coupon = False
            try:
                # 옵션 셀에서 "쿠폰사용" 텍스트가 포함된 div 찾기
                coupon_el = row.find_elements(
                    By.XPATH,
                    ".//div[contains(@class,'BookingListView__option') and (contains(., '쿠폰사용') or contains(@title, '쿠폰사용'))]"
                )
                is_coupon = len(coupon_el) > 0
            except Exception:
                is_coupon = False

            booking_data = {
                "naver_booking_id": naver_booking_id,
                "customer_name": customer_name,
                "phone_number": phone_number,
                "room_name": room_name,
                "reservation_date": reservation_date,
                "start_time": start_time,
                "end_time": end_time,
                "price": price,
                "reservation_status": status,
                "is_coupon": is_coupon,
            }

            # print(f"✅ 파싱 완료: {customer_name} ({naver_booking_id}) {status} {price:,}원")
            return booking_data

        except Exception as e:
            print(f"⚠️ 예약 행 파싱 에러: {e}")
            return None

    def _open_booking_sidebar(self, naver_booking_id):
        """
        기본 예약 리스트에서 특정 네이버 예약번호 행을 클릭해서
        오른쪽 '예약 상세정보' 사이드바를 연다.
        """
        try:
            # 예약 행들 로딩될 때까지 기다리기
            rows = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CLASS_NAME, "BookingListView__contents-user__xNWR6")
                )
            )

            for row in rows:
                try:
                    book_no_el = row.find_element(
                        By.CLASS_NAME,
                        "BookingListView__book-number__33dBa"
                    )
                    raw = (book_no_el.text or "").strip()

                    m = re.search(r"\d+", raw)
                    row_booking_id = m.group(0) if m else raw

                    if row_booking_id == str(naver_booking_id):
                        # 행 전체 클릭 (체크박스 말고)
                        self.driver.execute_script("arguments[0].click();", row)
                        WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.foot-btn-group"))
                        )
                        return True
                except Exception:
                    continue

            print(f"⚠️ 사이드바를 열 예약을 찾지 못했습니다: {naver_booking_id}")
            return False

        except Exception as e:
            print(f"❌ 사이드바 열기 실패: {e}")
            return False

    def save_to_db(self, bookings):
        """
        스크래핑한 예약들을 DB에 저장하거나 업데이트
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for booking in bookings:
            try:
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
                        'is_coupon': booking['is_coupon'],
                    }
                )
                
                if created:
                    created_count += 1
                    print(f"🆕 새 예약 저장: {booking['naver_booking_id']}")
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
    
    def confirm_in_pending_tab(self, naver_booking_id):
        """
        (이름 유지) 기본 예약 리스트에서 대상 클릭 → 사이드바에서 예약확정 2번 → 닫기 → 새로고침
        """
        try:
            # 1) 사이드바 오픈
            if not self._open_booking_sidebar(naver_booking_id):
                return False

            if self.dry_run:
                print(f"[DRY_RUN] 네이버 확정 시뮬레이션(2단계): {naver_booking_id}")
                print("[DRY_RUN] 1) 예약 클릭 → 2) 예약확정 클릭 → 3) 예약확정(최종) 클릭 → 4) 닫기 → 5) 새로고침")
                return True

            # 2) (1차) 사이드바에서 '예약확정' 버튼 클릭
            # - a/span 형태거나 button 형태 둘 다 대응
            first_confirm = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[contains(@class,'foot-btn-group')]"
                    "//*[self::a or self::button][.//span[contains(.,'예약확정')] or contains(.,'예약확정')]"
                ))
            )
            self.driver.execute_script("arguments[0].click();", first_confirm)

            # 3) (2차) 바뀐 화면(또는 확인 화면)에서 최종 '예약확정' 버튼 클릭
            # 사용자가 준 element:
            # <button ... data-tst_submit="0">예약확정</button>
            second_confirm = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "button[data-tst_submit='0']"
                ))
            )

            # 혹시 같은 data-tst_submit 이 다른 버튼일 가능성 방지: 텍스트도 한번 체크
            btn_text = (second_confirm.text or "").strip()
            if "예약확정" not in btn_text:
                # 텍스트가 예상과 다르면 XPath로 한 번 더 좁혀서 찾기
                second_confirm = WebDriverWait(self.driver, 8).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[@data-tst_submit='0' and contains(.,'예약확정')]"
                    ))
                )

            self.driver.execute_script("arguments[0].click();", second_confirm)

            # 4) 확정 완료 후 사이드바가 확정 상태로 바뀌는 시간 대기(너무 짧으면 닫기 실패 가능)
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.SideFrame__close__oKyEZ"))
            )

            # 5) 닫기 클릭
            close_btn = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.SideFrame__close__oKyEZ"))
            )
            self.driver.execute_script("arguments[0].click();", close_btn)

            # 6) 새로고침
            self.driver.refresh()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "BookingListView__contents-user__xNWR6"))
            )

            print(f"✅ 네이버 예약 확정 완료(2단계+닫기+새로고침): {naver_booking_id}")
            return True

        except Exception as e:
            print(f"❌ 확정 실패(2단계): {e}")
            return False


    def cancel_in_pending_tab(self, naver_booking_id, reason="쿠폰 조건 불일치로 자동 취소되었습니다."):
        """
        기본 예약 리스트에서 해당 예약 클릭 → 사이드바 '예약취소'(1차) →
        취소사유 입력 → 최종 '예약 취소'(2차, data-tst_submit='0') 클릭 → 닫기 → 새로고침
        """
        try:
            # 0) 사이드바 오픈
            if not self._open_booking_sidebar(naver_booking_id):
                return False

            if self.dry_run:
                print(f"[DRY_RUN] 네이버 취소 시뮬레이션(2단계): {naver_booking_id}")
                print(f"[DRY_RUN] 취소사유 입력: {reason}")
                print("[DRY_RUN] 1) 예약취소 클릭 → 2) 사유 입력 → 3) 최종 '예약 취소' 클릭")
                return True

            # 1) (1차) 사이드바 '예약취소' 클릭
            # <a ... data-tst_click_link="cancel"><span>예약취소</span></a>
            first_cancel = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-tst_click_link='cancel']"))
            )
            self.driver.execute_script("arguments[0].click();", first_cancel)

            # 2) 취소사유 입력칸(textarea) 대기 후 입력
            # 네이버 UI가 바뀔 수 있어 기본 textarea 우선, 없으면 placeholder/aria-label 기반으로 백업
            reason_el = None
            reason_candidates = [
                (By.CSS_SELECTOR, "textarea"),
                (By.XPATH, "//textarea[contains(@placeholder,'사유') or contains(@aria-label,'사유')]"),
            ]

            for by, sel in reason_candidates:
                try:
                    el = WebDriverWait(self.driver, 6).until(
                        EC.presence_of_element_located((by, sel))
                    )
                    if el.is_displayed():
                        reason_el = el
                        break
                except Exception:
                    continue

            if not reason_el:
                raise Exception("취소사유 입력칸(textarea)을 찾지 못했습니다.")

            try:
                reason_el.clear()
            except Exception:
                pass
            reason_el.send_keys(reason)

            # 3) (2차) 최종 '예약 취소' 버튼이 활성화될 때까지 기다렸다가 클릭
            # <button ... data-tst_submit="0">예약 취소</button>
            final_cancel = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-tst_submit='0']"))
            )

            # 혹시 다른 submit 버튼이 있을 수 있으니 텍스트도 확인
            btn_text = (final_cancel.text or "").strip().replace("\n", " ")
            if "예약" not in btn_text or "취소" not in btn_text:
                # 텍스트가 다르면 xpath로 한번 더 좁혀서 찾기
                final_cancel = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@data-tst_submit='0' and contains(.,'취소')]"))
                )

            self.driver.execute_script("arguments[0].click();", final_cancel)

            # 4) 취소 완료 후 닫기(있으면)
            try:
                close_btn = WebDriverWait(self.driver, 6).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.SideFrame__close__oKyEZ"))
                )
                self.driver.execute_script("arguments[0].click();", close_btn)
            except Exception:
                pass

            # 5) 새로고침
            self.driver.refresh()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "BookingListView__contents-user__xNWR6"))
            )

            print(f"✅ 네이버 예약 취소 완료(2단계+사유입력): {naver_booking_id}")
            return True

        except Exception as e:
            print(f"❌ 취소 실패(2단계): {e}")
            import traceback
            traceback.print_exc()
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
