# pianos/message_templates.py
from dataclasses import dataclass
from typing import Dict, Any

DEFAULT_TEMPLATES = {
    "PAYMENT_GUIDE": {
        "title": "입금 안내",
        "content": "[{studio}] {customer_name}님, 예약 요청 확인되었습니다.\n"
                   "{bank} {account}로 {price}원 입금 부탁드립니다.\n"
                   "(예약: {date} {start_time}~{end_time}, {room_name})"
    },
    "PAYMENT_GUIDE_EXAM": {
        "title": "입금 안내 - 입시기간",
        "content": "[{studio}] {customer_name}님, 예약 요청 확인되었습니다.\n"
                   "{bank} {account}로 {price}원 입금 부탁드립니다.\n"
                   "※ 입시기간 예약은 확정 후 환불이 어렵습니다.\n"
                   "(예약: {date} {start_time}~{end_time}, {room_name})"
    },
    "PAYMENT_GUIDE_ADD_PERSON": {
        "title": "입금 안내 - 인원 추가",
        "content": "[{studio}] {customer_name}님, 예약 요청 확인되었습니다.\n"
                   "{bank} {account}로 {price}원 입금 부탁드립니다.\n"
                   "※ 인원 추가 {add_person_count}명 포함\n"
                   "(예약: {date} {start_time}~{end_time}, {room_name})"},
    "PAYMENT_GUIDE_PROXY": {
        "title": "입금 안내 - 대리 예약",
        "content": "[{studio}] {customer_name}님, 예약 요청 확인되었습니다.\n"
                   "{bank} {account}로 {price}원 입금 부탁드립니다.\n"
                   "※ 대리 예약의 경우, 실제 이용자 성함/연락처를 회신 부탁드립니다.\n"
                   "(예약: {date} {start_time}~{end_time}, {room_name})"
    },
    "PAYMENT_GUIDE_ADD_PERSON_AND_PROXY": {
        "title": "입금 안내 - 인원 추가 & 대리 예약",
        "content": "[{studio}] {customer_name}님, 예약 요청 확인되었습니다.\n"
                   "{bank} {account}로 {price}원 입금 부탁드립니다.\n"
                   "※ 인원 추가 {add_person_count}명 포함\n"
                   "(예약: {date} {start_time}~{end_time}, {room_name})"},
    "CONFIRMATION": {
        "title": "확정 안내",
        "content": "[{studio}] {customer_name}님, 입금 확인되어 예약 확정되었습니다.\n"
                   "(예약: {date} {start_time}~{end_time}, {room_name}) 감사합니다."
    },
    "CONFIRMATION_EXAM": {
        "title": "확정 안내 - 입시기간",
        "content": "[{studio}] {customer_name}님, 입금 확인되어 예약 확정되었습니다.\n"
                   "※ 입시기간 예약은 환불 규정이 다르게 적용됩니다.\n"
                   "(예약: {date} {start_time}~{end_time}, {room_name}) 감사합니다."
    },
    "COUPON_CANCEL_TIME": {
        "title": "쿠폰 예약 취소 - 잔여시간 부족",
        "content": "[{studio}] {customer_name}님, 쿠폰 잔여시간이 부족하여 예약이 취소되었습니다.\n"
                   "잔여: {remaining_minutes}분 / 요청: {duration_minutes}분\n"
                   "충전 후 다시 예약 부탁드립니다."
    },
    "COUPON_CANCEL_TYPE": {
        "title": "쿠폰 예약 취소 - 유형 불일치(수입/국산)",
        "content": "[{studio}] {customer_name}님, 보유 쿠폰 유형({coupon_category})과 예약 룸 유형({room_category})이 달라 예약이 취소되었습니다.\n"
                   "확인 후 다시 예약 부탁드립니다."
    },
    "NORMAL_CANCEL_CONFLICT": {
        "title": "일반 예약 취소 - 동시간대 선입금 우선",
        "content": "[{studio}] {customer_name}님, 동일 시간대 예약 중 선입금 완료 고객이 있어 현재 예약은 취소되었습니다.\n"
                   "가능한 시간: {alt_times}"
    },
    "DAWN_CONFIRM": {
        "title": "새벽시간 예약 확인",
        "content": "[{studio}] {customer_name}님, 새벽 시간대 예약이 접수되어 확인차 연락드립니다.\n"
                   "이용 의사가 맞으시면 “확인”으로 회신 부탁드립니다.\n"
                   "(예약: {date} {start_time}~{end_time})"
    },
}


class SafeDict(dict):
    def __missing__(self, key):
        # 치환 값이 없으면 원문 토큰을 유지
        return "{" + key + "}"

def render_template(text: str, ctx: Dict[str, Any]) -> str:
    return text.format_map(SafeDict(ctx))
