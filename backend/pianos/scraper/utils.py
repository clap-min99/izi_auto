from datetime import date, time
import re


def parse_reservation_datetime(datetime_str):
    """
    네이버 플레이스 날짜/시간 파싱
    - 신규 포맷(2026-09~): '26.9.5.토 12:00~14:00'          (24시간제, 오전/오후 표기 없음)
    - 구 포맷:             '25. 12. 8.(월) 오전 12:00~1:00'  (12시간제 + 오전/오후)
    ⚠️ 네이버가 리스트 화면 표기를 12시간제(오전/오후)에서 24시간제로 바꾼 적이 있어
       두 포맷 다 지원하도록 함 — 문자열에 '오전'/'오후'가 있으면 구 포맷으로, 없으면 24시간제로 처리.
    """
    try:
        # 날짜 파싱: '25. 12. 8.' / '26.9.5.' 둘 다 매치 (공백·괄호 유무 무관)
        date_pattern = r'(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.'
        date_match = re.search(date_pattern, datetime_str)

        if not date_match:
            raise ValueError(f"날짜 형식을 찾을 수 없습니다: {datetime_str}")

        year = int('20' + date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        reservation_date = date(year, month, day)

        # 시간 파싱 1) 구 포맷: '오전/오후 H:MM~H:MM' (끝시간엔 오전/오후 없음)
        time_pattern_ampm = r'(오전|오후)\s*(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})'
        time_match = re.search(time_pattern_ampm, datetime_str)

        if time_match:
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

        else:
            # 시간 파싱 2) 신규 포맷: 이미 24시간제라 오전/오후 변환이 필요없음
            time_pattern_24h = r'(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})'
            time_match_24h = re.search(time_pattern_24h, datetime_str)

            if not time_match_24h:
                raise ValueError(f"시간 형식을 찾을 수 없습니다: {datetime_str}")

            sh = int(time_match_24h.group(1))
            sm = int(time_match_24h.group(2))
            eh = int(time_match_24h.group(3))
            em = int(time_match_24h.group(4))

            # 혹시 '24:00' 표기가 나오는 경우 대비(자정 시작을 24시로 표기하는 케이스 방어)
            sh = 0 if sh == 24 else sh
            eh = 0 if eh == 24 else eh

            start_time = time(sh, sm)
            end_time = time(eh, em)

            # 정책상 자정 넘어가는 예약은 없다고 했으니, end<=start면 비정상 데이터로 처리
            if (end_time.hour, end_time.minute) <= (start_time.hour, start_time.minute):
                raise ValueError(f"끝시간이 시작시간보다 빠르거나 같음(비정상 범위): {datetime_str}")

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