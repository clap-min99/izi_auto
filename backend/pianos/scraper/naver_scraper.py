from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

from datetime import datetime

import time
import os
import sys
import re
import subprocess

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
        self.use_existing_chrome = use_existing_chrome
        
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

        
    def restart_driver(self):
        def launch_debug_chrome():
            print("🚀 디버깅 크롬 새로 실행")

            subprocess.Popen([
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--remote-debugging-port=9222",
                r"--user-data-dir=C:\selenium\ChromeProfile"
            ])    
        print("♻️ driver 재생성 시작")

        try:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    print(f"   ⚠️ 기존 driver quit 실패(무시): {e}")
        finally:
            self.driver = None

        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        # ⭐ 핵심: 항상 "기존 → 실패 시 새로" 구조
        try:
            print("   🔗 기존 Chrome 연결 시도...")
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = self._connect_existing_chrome(chrome_options)

        except Exception as e:
            print(f"   ❌ 기존 Chrome 없음 → 새로 실행: {e}")

            launch_debug_chrome()

            # ⭐ 크롬 뜰 때까지 대기
            time.sleep(3)

            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

            self.driver = self._connect_existing_chrome(chrome_options)

        print("✅ driver 재생성 완료")
    
    def get_total_booking_count(self) -> int:
        """
        상단의 '예약 N건'에서 N을 읽어온다.
        실패하면 -1 반환.
        """
        try:
            # '예약' 라벨 옆 숫자 em (클래스는 바뀔 수 있어 contains로 잡음)
            el = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//span[contains(.,'예약')]/em[contains(@class,'BookingListView__number')]"
                ))
            )
            txt = (el.text or "").strip()
            return int(re.sub(r"[^\d]", "", txt)) if txt else -1
        except Exception:
            return -1

    def scroll_booking_list_to_bottom(self, max_wait_sec: int = 20, pause: float = 0.6):
        """
        예약 리스트 컨테이너(무한스크롤) 끝까지 내려서 모든 예약 로드
        - 컨테이너: div.BookingListView__booking-list-table-wrap__IbvCi
        """
        container_sel = "div.BookingListView__booking-list-table-wrap__IbvCi"
        container = self.driver.find_element(By.CSS_SELECTOR, container_sel)

        # ✅ 항상 맨 위에서 시작 (중간 위치 시작 방지)
        try:
            self.driver.execute_script("arguments[0].scrollTop = 0;", container)
            time.sleep(0.2)
        except Exception:
            pass

        start = time.time()
        last_scroll_top = -1
        last_scroll_height = 0
        stable_count = 0  # 더 이상 변화 없을 때 카운트

        while True:
            # scrollHeight/scrollTop/clientHeight로 상태 확인
            scroll_height = self.driver.execute_script("return arguments[0].scrollHeight;", container)
            client_height = self.driver.execute_script("return arguments[0].clientHeight;", container)
            scroll_top = self.driver.execute_script("return arguments[0].scrollTop;", container)

            # 맨 아래로 스크롤 (컨테이너 자체)
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
            time.sleep(pause)

            new_scroll_top = self.driver.execute_script("return arguments[0].scrollTop;", container)
            new_scroll_height = self.driver.execute_script("return arguments[0].scrollHeight;", container)

            # 변화 감지: 높이/스크롤탑이 더 이상 안 변하면 종료 준비
            if new_scroll_height == last_scroll_height and new_scroll_top == last_scroll_top:
                stable_count += 1
            else:
                stable_count = 0

            last_scroll_top = new_scroll_top
            last_scroll_height = new_scroll_height

            # 2~3번 연속 변화 없으면 끝까지 로드된 것으로 간주
            if stable_count >= 2:
                break

            # 안전 타임아웃
            if time.time() - start > max_wait_sec:
                print("⚠️ 예약 리스트 스크롤 로드 타임아웃 (일단 진행)")
                break

        # 끝까지 내린 뒤 약간 위로 올려서 DOM 안정화(선택)
        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight - arguments[0].clientHeight;", container)
        time.sleep(0.2)

    def scrape_all_bookings(self):
        """
        현재 페이지의 모든 예약 스크래핑
        - 상단 '예약 N건'과 실제 row 수가 다르면 스크롤 재시도
        """
        try:
            expected = self.get_total_booking_count()
            if expected > 0:
                print(f"📌 화면 표시 총 예약: {expected}건")
            else:
                print("⚠️ 총 예약 건수(예약 N건) 읽기 실패. row 기준으로만 진행")

            max_retry = 3
            last_count = -1

            for attempt in range(1, max_retry + 1):
                # 스크롤 끝까지 로드
                self.scroll_booking_list_to_bottom(max_wait_sec=25, pause=0.7)

                booking_rows = self.driver.find_elements(
                    By.CLASS_NAME,
                    "BookingListView__contents-user__xNWR6"
                )
                current = len(booking_rows)

                print(f"📋 초기 예약 리스트: {current}건 (시도 {attempt}/{max_retry})")

                # expected를 못 읽었으면 그냥 파싱
                if expected <= 0:
                    break

                # 다 읽었으면 종료
                if current >= expected:
                    break

                # 변화가 없으면(계속 50 등) 한번 더 강하게 스크롤 유도
                if current == last_count:
                    print("⚠️ 스크롤 후 row 수 변화 없음 → 추가 스크롤/대기 후 재시도")
                    try:
                        container_sel = "div.BookingListView__booking-list-table-wrap__IbvCi"
                        container = self.driver.find_element(By.CSS_SELECTOR, container_sel)
                        # 아래로 더 여러 번 쭉 밀기
                        for _ in range(3):
                            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
                            time.sleep(0.8)
                    except Exception:
                        pass

                last_count = current

            # 여기서 실제 파싱 진행
            booking_rows = self.driver.find_elements(By.CLASS_NAME, "BookingListView__contents-user__xNWR6")
            bookings = []
            for row in booking_rows:
                booking = self._parse_booking_row(row)
                if booking:
                    bookings.append(booking)

            # 마지막 검증 로그
            if expected > 0 and len(bookings) < expected:
                print(f"⚠️ 스크래핑 결과 {len(bookings)}건 < 화면 표시 {expected}건 (추가 로드 실패 가능)")
            else:
                print(f"✅ 예약 스크래핑 완료: {len(bookings)}건")

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

            is_proxy = False
            try:
                # 라벨이 있으면 보통 "대리예약" 텍스트가 들어감
                label_els = row.find_elements(By.CSS_SELECTOR, "span.BookingListView__label__BzZL5")
                is_proxy = any(("대리예약" in (el.text or "").strip()) for el in label_els)
            except Exception:
                is_proxy = False

            # 3) 전화번호
            phone_el = row.find_element(
                By.CSS_SELECTOR,
                ".BookingListView__phone__i04wO span"
            )
            phone_number = phone_el.text.strip()

            # 4) 네이버 예약번호
            book_id_el = row.find_element(
                By.CLASS_NAME,
                "BookingListView__book-number__33dBa"
            )
            raw_booking_id = (book_id_el.text or "").strip()
            is_change_badge = ("변경" in raw_booking_id)

            m = re.search(r"\d+", raw_booking_id)
            # naver_booking_id = m.group(0) if m else raw_booking_id  # fallback
            if not m:
                print(f"   ⚠️ 예약번호 파싱 실패(스킵): raw={raw_booking_id!r}")
                return None
            naver_booking_id = m.group(0)

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
            
            # 8.5) ✅ 요청사항 파싱
            request_comment = ""
            try:
                comment_el = row.find_elements(
                    By.XPATH,
                    ".//div[contains(@class,'BookingListView__comment__')]"  # 클래스 suffix 변동 대응
                )
                if comment_el:
                    el = comment_el[0]
                    txt = (el.get_attribute("title") or el.text or "").strip()
                    # 줄바꿈/여백 정리
                    txt = re.sub(r"\s+", " ", txt).strip()
                    request_comment = txt
            except Exception:
                request_comment = ""
                
             # ✅ [추가] 인원 추가 옵션(국산/수입) 파싱 → base_amount 역산 → 실청구금액 계산
            extra_qty = 0
            try:
                extra_qty = 0
                kind = None  # "국산" | "수입"

                # 옵션 셀들 중 "인원 추가"만 추출
                option_els = row.find_elements(
                    By.XPATH,
                    ".//div[contains(@class,'BookingListView__option') and (contains(., '인원 추가') or contains(@title, '인원 추가'))]"
                )

                for el in option_els:
                    txt = (el.get_attribute("title") or el.text or "").strip()

                    m_qty = re.search(r"인원\s*추가.*?\((\d+)\)", txt)
                    if not m_qty:
                        continue

                    extra_qty = int(m_qty.group(1))

                    if "국산" in txt:
                        kind = "국산"
                    elif "수입" in txt:
                        kind = "수입"

                    # 인원 추가 옵션은 보통 1개라서 찾으면 종료
                    break

                gross_amount = price  # 네이버가 보여주는 총 금액(옵션 포함)

                if extra_qty > 0 and kind in ("국산", "수입"):
                    unit = 4500 if kind == "국산" else 6000
                    base_amount = gross_amount - (unit * extra_qty)

                    # 이상치 방어: base가 0 이하이면 파싱 실패로 보고 옵션 무시
                    if base_amount <= 0:
                        base_amount = gross_amount
                        extra_qty = 0

                    # ✅ 실청구금액 = base + base*0.5*extra_qty (반올림 고려 X)
                    final_amount = base_amount + (base_amount * extra_qty // 2)
                    # print(
                    #     f"   💰 인원추가 요금 재계산 | "
                    #     f"gross={gross_amount:,}원 → "
                    #     f"base={base_amount:,}원 | "
                    #     f"추가인원={extra_qty}명({kind}) | "
                    #     f"final={final_amount:,}원"
                    # )
                    price = final_amount  # ⭐ booking_data["price"]에 들어갈 값 덮어쓰기

            except Exception as e:
                print(f"   ⚠️ 인원추가 요금 계산 실패: {e}")
                # 실패 시 price(gross) 그대로 유지

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
                "extra_people_qty": extra_qty,
                "is_proxy": is_proxy,
                "request_comment": request_comment,
                "is_change_badge": is_change_badge,
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
        self.scroll_booking_list_to_bottom()  # ✅ 추가
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
                        "extra_people_qty": booking.get("extra_people_qty", 0),
                        "is_proxy": booking.get("is_proxy", False),
                        "request_comment": booking.get("request_comment", ""),
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
            self.refresh_page()
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
            self.refresh_page()
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
        self.scroll_booking_list_to_bottom() 

    def close(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            print("🔚 브라우저 종료")
    
    def _log_session_recover(self, before_handles, after_handles, new_handle):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cwd = os.getcwd()
        path = os.path.join(cwd, "session_recover.log")
        with open("session_recover.log", "a", encoding="utf-8") as f:
            f.write(
                f"[{ts}] SESSION RECOVER\n"
                f"  before_handles={before_handles}\n"
                f"  after_handles={after_handles}\n"
                f"  new_handle={new_handle}\n\n"
            )


    def _looks_like_logged_out(self) -> bool:
        """
        네이버 예약 관리 페이지 세션이 풀렸는지 대충 판별.
        - 로그인 페이지로 튕김 (nid.naver.com)
        - 예약 리스트 핵심 DOM이 안 잡힘
        """
        try:
            url = (self.driver.current_url or "").lower()
            if "nid.naver.com" in url:
                return True

            # 예약 리스트 row 클래스가 안 보이면 (로그인/권한/에러 화면일 가능성)
            rows = self.driver.find_elements(By.CLASS_NAME, "BookingListView__contents-user__xNWR6")
            if rows:
                return False

            # 혹시 로딩/다른 화면이면 짧게라도 기다려보고 재확인
            try:
                WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "BookingListView__contents-user__xNWR6"))
                )
                return False
            except Exception:
                return True

        except Exception:
            return True

    def reopen_reservation_tab(self, url: str, close_old: bool = False, as_window: bool = True):
        """
        세션 만료/로그아웃 등으로 예약 페이지가 깨졌을 때 새 탭/새 창으로 다시 연다.
        - as_window=True면 새 '창'으로 열어서 눈으로 확인 가능 (추천)
        - close_old=True면 기존 탭 닫아서 더 확실히 확인 가능
        """
        driver = self.driver

        old_handle = driver.current_window_handle
        old_handles = list(driver.window_handles)
        print(f"   🔎 before reopen: handles={len(old_handles)} current={old_handle}")

        # ✅ 새 창/탭 열기
        if as_window:
            driver.switch_to.new_window("window")   # 👈 새 창 (눈에 확 띔)
        else:
            driver.switch_to.new_window("tab")      # 👈 새 탭

        new_handle = driver.current_window_handle
        new_handles = list(driver.window_handles)
        print(f"   🔎 after new_window: handles={len(new_handles)} new={new_handle}")

        self._log_session_recover(old_handles, new_handles, new_handle)

        # ✅ 새 창(또는 탭)에서 URL 오픈
        driver.get(url)

        # (선택) 창 크기 키워서 눈으로 보기 쉽게
        try:
            driver.maximize_window()
        except Exception:
            pass

        print(f"   ✅ reopened url={driver.current_url}")

        # ✅ 기존 탭 닫고 싶으면 (테스트 때는 True 추천)
        if close_old:
            try:
                driver.switch_to.window(old_handle)
                driver.close()
            finally:
                driver.switch_to.window(new_handle)

        print("🆕 세션 복구: 새 탭/창으로 예약 페이지 재오픈 완료")
    def is_logged_out(self) -> bool:
        """
        네이버 로그아웃/세션만료 감지.
        - URL에 login/nidlogin 포함
        - 로그인 폼 요소가 보임
        - 예약 리스트 핵심 요소가 안 보임
        """
        d = self.driver
        try:
            url = (d.current_url or "").lower()

            # 1) URL 기반 빠른 판정
            if "nidlogin" in url or "login" in url:
                return True

            # 2) 로그인 페이지에서 흔히 보이는 input들
            #    (네이버가 DOM을 바꾸면 이 부분만 조정)
            login_inputs = d.find_elements("css selector", "input#id, input#pw, input[name='id'], input[name='pw']")
            if login_inputs:
                return True

            # 3) 예약 페이지 핵심 요소 존재 여부(너희 페이지에 맞게 1개만 잡아도 됨)
            # 예: 예약 리스트가 반드시 존재하는 영역 selector
            anchors = d.find_elements("css selector", "[data-testid='booking-list'], .booking_list, .ReservationList")
            # 위 셀렉터는 예시라서, 네가 실제로 쓰는 예약 리스트 셀렉터 1개로 바꾸는 걸 추천
            # anchors가 0이면 바로 로그아웃이라고 단정하면 오탐이 있을 수 있으니 URL/login_inputs로 1차 필터 후 보조로만 써.
            return False

        except WebDriverException:
            # 드라이버 통신/창 죽음이면 '로그아웃'이 아니라 다른 복구 루트가 맞음
            return False