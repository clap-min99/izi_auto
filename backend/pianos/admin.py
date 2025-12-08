from django.contrib import admin
from .models import CouponCustomer, Reservation, CouponHistory


@admin.register(CouponCustomer)
class CouponCustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'phone_number', 'remaining_time', 'created_at', 'updated_at']
    list_filter = ['created_at']
    search_fields = ['customer_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = [
        'customer_name', 
        'phone_number', 
        'room_name', 
        'reservation_date',
        'start_time',
        'end_time',
        'price',
        'is_coupon',
        'reservation_status',
        'account_sms_status',
        'complete_sms_status'
    ]
    list_filter = ['reservation_status', 'is_coupon', 'reservation_date', 'created_at']
    search_fields = ['customer_name', 'phone_number', 'room_name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'reservation_date'
    
    fieldsets = (
        ('예약 정보', {
            'fields': ('customer_name', 'phone_number', 'room_name')
        }),
        ('예약 시간', {
            'fields': ('reservation_date', 'start_time', 'end_time', 'price')
        }),
        ('쿠폰 & 상태', {
            'fields': ('is_coupon', 'reservation_status', 'account_sms_status', 'complete_sms_status')
        }),
        ('시스템 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CouponHistory)
class CouponHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'customer_name',
        'transaction_type',
        'room_name',
        'transaction_date',
        'used_or_charged_time',
        'remaining_time',
        'created_at'
    ]
    list_filter = ['transaction_type', 'transaction_date', 'created_at']
    search_fields = ['customer_name', 'room_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'transaction_date'
    
    fieldsets = (
        ('고객 정보', {
            'fields': ('customer', 'customer_name')
        }),
        ('거래 정보', {
            'fields': ('transaction_type', 'transaction_date', 'used_or_charged_time', 'remaining_time')
        }),
        ('예약 정보 (사용 시)', {
            'fields': ('reservation', 'room_name', 'start_time', 'end_time'),
            'classes': ('collapse',)
        }),
        ('시스템 정보', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )