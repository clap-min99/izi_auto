from django.db import models
from django.utils import timezone
from datetime import datetime


class CouponCustomer(models.Model):
    """쿠폰 고객 테이블"""
    COUPON_TYPE_CHOICES = [
        (10, '10시간'),
        (20, '20시간'),
        (50, '50시간'),
        (100, '100시간'),
    ]

    COUPON_STATUS_CHOICES = [
        ('활성', '활성'),
        ('만료', '만료'),
    ]

    PIANO_CATEGORY_CHOICES = [
        ('수입', '수입'),
        ('국산', '국산'),
    ]
    coupon_type = models.IntegerField(choices=COUPON_TYPE_CHOICES, null=True, blank=True)
    coupon_registered_at = models.DateField(null=True, blank=True)
    coupon_expires_at = models.DateField(null=True, blank=True)
    coupon_status = models.CharField(max_length=10, choices=COUPON_STATUS_CHOICES, default='활성')
    piano_category = models.CharField(max_length=10, choices=PIANO_CATEGORY_CHOICES, null=True, blank=True)

    customer_name = models.CharField(max_length=100, verbose_name="예약자명")
    phone_number = models.CharField(max_length=20, verbose_name="전화번호")
    remaining_time = models.IntegerField(default=0, verbose_name="잔여시간(분)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일시")

    class Meta:
        db_table = 'coupon_customers'
        constraints = [
            models.UniqueConstraint(
                fields=["phone_number", "piano_category"],
                name="uniq_coupon_wallet_per_phone_and_category",
            )
        ]
        verbose_name = '쿠폰 고객'
        verbose_name_plural = '쿠폰 고객 목록'

    def refresh_expiry_status(self, today=None):
        """쿠폰 만료 여부를 확인하고 상태를 갱신합니다."""
        from django.utils import timezone
        if today is None:
            today = timezone.now().date()
        if self.coupon_expires_at and today > self.coupon_expires_at:
            if self.coupon_status != '만료':
                self.coupon_status = '만료'
                self.save(update_fields=['coupon_status', 'updated_at'])
        return self.coupon_status

    @property
    def is_expired(self):
        from django.utils import timezone
        if self.coupon_status == '만료':
            return True
        if self.coupon_expires_at and timezone.now().date() > self.coupon_expires_at:
            return True
        return False

    def __str__(self):
        return f"{self.customer_name} ({self.phone_number})"
    
class AccountTransaction(models.Model):
    """계좌 거래 내역 테이블 (팝빌 API로부터 수집)"""
    
    # 거래 정보
    transaction_id = models.CharField(
        max_length=100, 
        unique=True,
        verbose_name="거래고유번호"
    )
    transaction_date = models.DateField(verbose_name="거래일자")
    transaction_time = models.TimeField(verbose_name="거래시간")
    
    # 입출금 구분
    TRANSACTION_TYPE_CHOICES = [
        ('입금', '입금'),
        ('출금', '출금'),
    ]
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        verbose_name="거래구분"
    )
    
    # 금액
    amount = models.IntegerField(verbose_name="거래금액")
    balance = models.IntegerField(verbose_name="거래후잔액")
    
    # 거래 상대방 정보
    depositor_name = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name="입금자명"
    )
    
    # 메모
    memo = models.TextField(blank=True, verbose_name="거래메모")
    
    # ★ 매칭 상태 (핵심)
    MATCH_STATUS_CHOICES = [
        ('확정전', '확정전'),      # 아직 매칭 안됨 (기본값)
        ('확정완료', '확정완료'),  # 예약 확정 완료
        ('취소', '취소'),          # 예약 취소 (환불 대상)
    ]
    match_status = models.CharField(
        max_length=10,
        choices=MATCH_STATUS_CHOICES,
        default='확정전',
        verbose_name="매칭상태"
    )
    
    # 매칭된 예약들 (ManyToMany)
    matched_reservations = models.ManyToManyField(
        'Reservation',
        blank=True,
        related_name='matched_transactions',
        verbose_name="매칭된예약들"
    )
    
    # 시스템 정보
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="수집일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일시")
    
    class Meta:
        db_table = 'account_transactions'
        verbose_name = '계좌 거래 내역'
        verbose_name_plural = '계좌 거래 내역 목록'
        ordering = ['-transaction_date', '-transaction_time']
        indexes = [
            models.Index(fields=['-transaction_date', '-transaction_time']),
            models.Index(fields=['match_status']),
            models.Index(fields=['depositor_name']),
        ]

class Reservation(models.Model):
    """예약 테이블"""
    
    # 예약 상태 선택지
    STATUS_CHOICES = [
        ('신청', '신청'),
        ('확정', '확정'),
        ('취소', '취소'),
    ]
    
    # SMS 전송 상태 선택지
    SMS_STATUS_CHOICES = [
        ('전송전', '전송전'),
        ('전송완료', '전송완료'),
        ('전송실패', '전송실패'),
        ('입금확인전', '입금확인전'),
    ]
    
    # 네이버 예약 고유 ID (중복 방지 & 업데이트용)
    naver_booking_id = models.CharField(
        max_length=100, 
        unique=True,
        default='',
        verbose_name="예약번호"
    )

    customer_name = models.CharField(max_length=100, verbose_name="예약자명")
    phone_number = models.CharField(max_length=20, verbose_name="전화번호")
    room_name = models.CharField(max_length=100, verbose_name="예약룸명")
    reservation_date = models.DateField(verbose_name="예약일자")
    start_time = models.TimeField(verbose_name="시작시간")
    end_time = models.TimeField(verbose_name="종료시간")
    price = models.IntegerField(verbose_name="요금")
    is_coupon = models.BooleanField(default=False, verbose_name="쿠폰여부")
    request_comment = models.TextField(blank=True, default="", verbose_name="요청사항")
    extra_people_qty = models.PositiveIntegerField(default=0, verbose_name="인원추가수량")
    is_proxy = models.BooleanField(default=False, verbose_name="대리예약여부")

    # 문자 발송 상태
    account_sms_status = models.CharField(
        max_length=20, 
        choices=SMS_STATUS_CHOICES, 
        default='전송전',
        verbose_name="계좌문자"
    )
    complete_sms_status = models.CharField(
        max_length=20, 
        choices=SMS_STATUS_CHOICES, 
        default='입금확인전',
        verbose_name="완료문자"
    )
    
    # 예약 상태
    reservation_status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='신청',
        verbose_name="예약상태"
    )

    # 사장님 알림톡 상태
    owner_request_noti_status = models.CharField(
    max_length=20,
    default="전송전",
    choices=[
        ("전송전", "전송전"),
        ("전송완료", "전송완료"),
        ("전송실패", "전송실패"),
    ],
)
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일시")

    class Meta:
        db_table = 'reservations'
        verbose_name = '예약'
        verbose_name_plural = '예약 목록'
        ordering = ['-created_at', '-reservation_date', '-start_time']

    def __str__(self):
        return f"{self.customer_name} - {self.room_name} ({self.reservation_date})"
    
    def get_duration_minutes(self):
        if not self.start_time or not self.end_time:
            return 0

        start_dt = datetime.combine(self.reservation_date, self.start_time)
        end_dt = datetime.combine(self.reservation_date, self.end_time)
        base = int((end_dt - start_dt).total_seconds() / 60)

        extra = int(getattr(self, "extra_people_qty", 0) or 0)

        # 쿠폰 예약일 때만 인원추가 가산: n시간 예약이면, 인원추가 1명당 0.5*n시간 추가 차감
        if getattr(self, "is_coupon", False) and extra > 0:
            return base + (base * extra // 2)  # 반올림 고려 X (요청대로)

        return base


class CouponHistory(models.Model):
    """쿠폰 사용 이력 테이블"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('충전', '충전'),
        ('사용', '사용'),
        ('환불', '환불'),
        ('수동', '수동'),
    ]
    
    customer = models.ForeignKey(
        CouponCustomer, 
        on_delete=models.CASCADE, 
        related_name='histories',
        verbose_name="고객"
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupon_histories',
        verbose_name="예약"
    )
    
    customer_name = models.CharField(max_length=100, verbose_name="예약자명")
    room_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="예약룸명")
    transaction_date = models.DateField(verbose_name="거래일자")
    start_time = models.TimeField(blank=True, null=True, verbose_name="시작시간")
    end_time = models.TimeField(blank=True, null=True, verbose_name="종료시간")
    remaining_time = models.IntegerField(verbose_name="잔여시간(분)")
    used_or_charged_time = models.IntegerField(verbose_name="사용/충전시간(분)")
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        verbose_name="거래유형"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    reason = models.CharField(max_length=255, null=True, blank=True, verbose_name="수정 사유")

    class Meta:
        db_table = 'coupon_history'
        verbose_name = '쿠폰 사용 이력'
        verbose_name_plural = '쿠폰 사용 이력 목록'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.customer_name} - {self.transaction_type} ({self.transaction_date})"
    

class MessageTemplate(models.Model):
    class Code(models.TextChoices):
        PAYMENT_GUIDE = "PAYMENT_GUIDE", "입금 안내 - 기본"
        PAYMENT_GUIDE_EXAM = "PAYMENT_GUIDE_EXAM", "입금 안내 - 입시기간"
        PAYMENT_GUIDE_PROXY = "PAYMENT_GUIDE_PROXY", "입금 안내 - 대리 예약"
        PAYMENT_GUIDE_ADD_PERSON = "PAYMENT_GUIDE_ADD_PERSON", "입금 안내 - 인원 추가"
        PAYMENT_GUIDE_ADD_PERSON_AND_PROXY = "PAYMENT_GUIDE_ADD_PERSON_AND_PROXY", "입금 안내 - 대리 예약 & 인원 추가"
        CONFIRMATION = "CONFIRMATION", "확정 안내"
        CONFIRMATION_EXAM = "CONFIRMATION_EXAM", "확정 안내 - 입시기간"
        CONFIRMATION_COUPON = "CONFIRMATION_COUPON", "확정 안내 - 입시기간(쿠폰)"
        COUPON_CANCEL_TIME = "COUPON_CANCEL_TIME", "쿠폰 취소(잔여시간 부족)"
        COUPON_CANCEL_TYPE = "COUPON_CANCEL_TYPE", "쿠폰 취소(유형 불일치)"
        NORMAL_CANCEL_CONFLICT = "NORMAL_CANCEL_CONFLICT", "일반 취소(동시간대 선입금 우선)"
        NORMAL_CANCEL_TIMEOUT = "NORMAL_CANCEL_TIMEOUT", "일반 취소(입금기한 초과)"
        DAWN_CONFIRM = "DAWN_CONFIRM", "새벽 예약 확인"


    code = models.CharField(max_length=64, unique=True, choices=Code.choices)
    title = models.CharField(max_length=100)
    content = models.TextField(default="")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "message_templates"
    
    def __str__(self):
        return f"{self.code} ({'ON' if self.is_active else 'OFF'})"
    

class StudioPolicy(models.Model):
    exam_start_date = models.DateField(null=True, blank=True)
    exam_end_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # models.py (StudioPolicy)
    exam_daily_start_time = models.TimeField(null=True, blank=True)
    exam_daily_end_time = models.TimeField(null=True, blank=True)


    class Meta:
        db_table = "studio_policies"
        verbose_name = "스튜디오 정책"
        verbose_name_plural = "스튜디오 정책"



class RoomPassword(models.Model):
    room_name = models.CharField(max_length=100, unique=True, verbose_name="룸명")
    room_pw = models.CharField(max_length=50, blank=True, default="", verbose_name="비밀번호")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.room_name}"
    
class AutomationControl(models.Model):
    """
    자동화 전체 ON/OFF(킬 스위치)
    - enabled=True: monitor 자동화 전부 실행
    - enabled=False: monitor 아무 것도 안 함(완전 정지)
    """
    enabled = models.BooleanField(default=False)  # 안전하게 기본 OFF 추천
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "automation_control"
        verbose_name = "자동화 제어"
        verbose_name_plural = "자동화 제어"


class NotificationLog(models.Model):
    TYPE_COUPON_USAGE_YESTERDAY_SMS = "COUPON_USAGE_YESTERDAY_SMS"

    noti_type = models.CharField(max_length=64)
    target_date = models.DateField()
    customer = models.ForeignKey("CouponCustomer", on_delete=models.CASCADE, related_name="notification_logs")

    status = models.CharField(
        max_length=16,
        choices=[("PENDING","PENDING"), ("SENT","SENT"), ("FAILED","FAILED"), ("SKIPPED","SKIPPED")],
        default="PENDING",
    )
    request_id = models.CharField(max_length=128, blank=True, default="")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["noti_type", "target_date", "customer"], name="uniq_noti_once_per_day"),
        ]