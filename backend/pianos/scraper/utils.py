from datetime import date, time
import re


def parse_reservation_datetime(datetime_str):
    """
    네이버 플레이스 날짜/시간 파싱
    입력: '25. 12. 8.(월) 오전 12:00~1:00'
    """
    try:
        # 날짜 파싱: '25. 12. 8.'
        date_pattern = r'(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.'
        date_match = re.search(date_pattern, datetime_str)

        if not date_match:
            raise ValueError(f"날짜 형식을 찾을 수 없습니다: {datetime_str}")

        year = int('20' + date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        reservation_date = date(year, month, day)

        # 시간 파싱: '오전 12:00~1:00'  (끝시간엔 오전/오후 없음)
        time_pattern = r'(오전|오후)\s*(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})'
        time_match = re.search(time_pattern, datetime_str)

        if not time_match:
            raise ValueError(f"시간 형식을 찾을 수 없습니다: {datetime_str}")

        meridiem = time_match.group(1)        # 시작의 오전/오후
        sh = int(time_match.group(2))
        sm = int(time_match.group(3))
        eh = int(time_match.group(4))
        em = int(time_match.group(5))

        def to_24h(ampm: str, hh: int, mm: int) -> time:
            # 오전/오후 + 12시간제 -> time(24h)
            if ampm == "오전":
                hh = 0 if hh == 12 else hh
            else:  # "오후"
                hh = 12 if hh == 12 else hh + 12
            return time(hh, mm)

        # ✅ start는 meridiem 그대로
        start_time = to_24h(meridiem, sh, sm)

        # ✅ end는 "일단 meridiem으로 가정" -> end <= start면 반대로 토글
        end_time = to_24h(meridiem, eh, em)

        # end가 start보다 이르면(또는 같으면) 정오 넘어가는 케이스로 보고 토글
        if (end_time.hour, end_time.minute) <= (start_time.hour, start_time.minute):
            toggled = "오후" if meridiem == "오전" else "오전"
            end_time2 = to_24h(toggled, eh, em)

            # 정책상 자정 넘어가는 예약은 없다고 했으니,
            # 토글했는데도 여전히 start보다 이르면 비정상 데이터로 처리
            if (end_time2.hour, end_time2.minute) <= (start_time.hour, start_time.minute):
                raise ValueError(f"끝시간 보정 실패(비정상 범위): {datetime_str}")

            end_time = end_time2

        return {
            'reservation_date': reservation_date,
            'start_time': start_time,
            'end_time': end_time
        }

    except Exception as e:
        print(f"⚠️ 파싱 에러: {e}")
        return None


def parse_price(price_str):
    """
    가격 문자열 파싱
    입력: '7,000원'
    출력: 7000
    """
    try:
        return int(price_str.replace('원', '').replace(',', '').strip())
    except:
        return 0