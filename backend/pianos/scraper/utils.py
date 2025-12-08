from datetime import date, time
import re


def parse_reservation_datetime(datetime_str):
    """
    네이버 플레이스 날짜/시간 파싱
    입력: '25. 12. 8.(월) 오전 12:00~1:00'
    출력: {
        'reservation_date': date(2025, 12, 8),
        'start_time': time(0, 0),
        'end_time': time(1, 0)
    }
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
        
        # 시간 파싱: '오전 12:00~1:00'
        time_pattern = r'(오전|오후)\s*(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})'
        time_match = re.search(time_pattern, datetime_str)
        
        if not time_match:
            raise ValueError(f"시간 형식을 찾을 수 없습니다: {datetime_str}")
        
        meridiem = time_match.group(1)
        start_hour = int(time_match.group(2))
        start_minute = int(time_match.group(3))
        end_hour = int(time_match.group(4))
        end_minute = int(time_match.group(5))
        
        # 24시간 형식으로 변환
        if meridiem == '오후':
            if start_hour != 12:
                start_hour += 12
            if end_hour != 12:
                end_hour += 12
        elif meridiem == '오전':
            if start_hour == 12:
                start_hour = 0
            if end_hour == 12:
                end_hour = 0
        
        start_time = time(start_hour, start_minute)
        end_time = time(end_hour, end_minute)
        
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