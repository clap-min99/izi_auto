from rest_framework import serializers
from .models import Reservation, CouponCustomer, CouponHistory


class ReservationSerializer(serializers.ModelSerializer):
    """예약 관리 Serializer"""
    
    class Meta:
        model = Reservation
        fields = [
            'id',
            'naver_booking_id',
            'customer_name',
            'phone_number',
            'room_name',
            'reservation_date',
            'start_time',
            'end_time',
            'price',
            'is_coupon',
            'account_sms_status',
            'complete_sms_status',
            'reservation_status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CouponCustomerListSerializer(serializers.ModelSerializer):
    """쿠폰 고객 목록 Serializer (선불 고객 탭)"""
    
    class Meta:
        model = CouponCustomer
        fields = [
            'id',
            'customer_name',
            'phone_number',
            'remaining_time',  # 분 단위
        ]
        read_only_fields = ['id']


class CouponHistorySerializer(serializers.ModelSerializer):
    """쿠폰 이력 Serializer"""
    
    booking_number = serializers.SerializerMethodField()
    usage_datetime = serializers.SerializerMethodField()
    charged_or_used_time = serializers.IntegerField(source='used_or_charged_time')
    
    class Meta:
        model = CouponHistory
        fields = [
            'id',
            'transaction_type',
            'booking_number',
            'usage_datetime',
            'remaining_time',  # 분 단위
            'charged_or_used_time',  # 분 단위
        ]
    
    def get_booking_number(self, obj):
        """예약방번호 (room_name)"""
        return obj.room_name if obj.room_name else '-'
    
    def get_usage_datetime(self, obj):
        """이용일시 포맷팅"""
        if obj.start_time and obj.end_time:
            start = f"{obj.transaction_date}T{obj.start_time}"
            end = f"{obj.transaction_date}T{obj.end_time}"
            return f"{start} ~ {end}"
        return '-'


class CouponCustomerDetailSerializer(serializers.ModelSerializer):
    """쿠폰 고객 상세 + 이력 Serializer (모달용)"""
    
    histories = CouponHistorySerializer(many=True, read_only=True)
    
    class Meta:
        model = CouponCustomer
        fields = [
            'id',
            'customer_name',
            'phone_number',
            'remaining_time',  # 분 단위
            'histories',
        ]
        read_only_fields = ['id']


# ⭐ 새로 추가: 쿠폰 고객 등록/충전 통합 Serializer
class CouponCustomerRegisterOrChargeSerializer(serializers.Serializer):
    """쿠폰 고객 등록/충전 통합 Serializer"""
    
    customer_name = serializers.CharField(max_length=100, help_text="예약자명")
    phone_number = serializers.CharField(max_length=20, help_text="전화번호")
    charged_time = serializers.IntegerField(min_value=0, help_text="충전할 시간 (분 단위)")
    
    def validate_charged_time(self, value):
        """충전 시간 검증"""
        if value < 0:
            raise serializers.ValidationError("충전 시간은 0분 이상이어야 합니다.")
        return value