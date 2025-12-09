from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from .models import Reservation, CouponCustomer, CouponHistory
from .serializers import (
    ReservationSerializer,
    CouponCustomerListSerializer,
    CouponCustomerDetailSerializer,
    CouponHistorySerializer,
    CouponCustomerRegisterOrChargeSerializer,
)


class ReservationViewSet(viewsets.ModelViewSet):
    """예약 관리 ViewSet"""
    
    queryset = Reservation.objects.all().order_by('-reservation_date', '-start_time')
    serializer_class = ReservationSerializer
    filter_backends = [SearchFilter]
    search_fields = ['customer_name', 'phone_number']


class CouponCustomerViewSet(viewsets.ModelViewSet):
    """쿠폰 고객 관리 ViewSet"""
    
    queryset = CouponCustomer.objects.all().order_by('-updated_at')
    filter_backends = [SearchFilter]
    search_fields = ['customer_name', 'phone_number']
    
    def get_serializer_class(self):
        """액션에 따라 다른 Serializer 사용"""
        if self.action == 'history':
            return CouponCustomerDetailSerializer
        elif self.action == 'create':
            return CouponCustomerRegisterOrChargeSerializer
        return CouponCustomerListSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        쿠폰 고객 등록/충전 통합
        POST /api/coupon-customers/
        
        - 신규 고객: 생성 + 시간 충전
        - 기존 고객: 시간만 충전
        """
        serializer = CouponCustomerRegisterOrChargeSerializer(data=request.data)
        
        if serializer.is_valid():
            customer_name = serializer.validated_data['customer_name']
            phone_number = serializer.validated_data['phone_number']
            charged_time = serializer.validated_data['charged_time']
            
            # 전화번호로 기존 고객 찾기
            customer, created = CouponCustomer.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'customer_name': customer_name,
                    'remaining_time': 0,
                }
            )
            
            # 이름 업데이트 (변경되었을 수 있으니)
            if customer.customer_name != customer_name:
                customer.customer_name = customer_name
            
            # 시간 충전
            old_remaining_time = customer.remaining_time
            customer.remaining_time += charged_time
            customer.save()
            
            # 충전 이력 생성 (charged_time > 0 일 때만)
            history = None
            if charged_time > 0:
                history = CouponHistory.objects.create(
                    customer=customer,
                    customer_name=customer.customer_name,
                    transaction_date=timezone.now().date(),
                    remaining_time=customer.remaining_time,
                    used_or_charged_time=charged_time,
                    transaction_type='충전'
                )
            
            response_data = {
                'message': '신규 등록 및 충전 완료' if created else '충전 완료',
                'is_new_customer': created,
                'customer': {
                    'id': customer.id,
                    'customer_name': customer.customer_name,
                    'phone_number': customer.phone_number,
                    'remaining_time': customer.remaining_time,
                }
            }
            
            if history:
                response_data['history'] = {
                    'id': history.id,
                    'transaction_type': history.transaction_type,
                    'charged_or_used_time': history.used_or_charged_time,
                    'remaining_time': history.remaining_time,
                }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """
        쿠폰 고객 정보 수정 (이름, 전화번호만)
        PATCH /api/coupon-customers/{id}/
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # 수정 가능한 필드만 추출
        allowed_fields = ['customer_name', 'phone_number']
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = CouponCustomerListSerializer(
            instance, 
            data=filtered_data, 
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """
        쿠폰 고객 상세 + 사용 이력 조회 (모달용)
        GET /api/coupon-customers/{id}/history/
        """
        customer = self.get_object()
        
        return Response({
            'customer': {
                'id': customer.id,
                'customer_name': customer.customer_name,
                'phone_number': customer.phone_number,
                'remaining_time': customer.remaining_time,
            },
            'histories': CouponHistorySerializer(
                customer.histories.all().order_by('-transaction_date', '-created_at'),
                many=True
            ).data
        })
    
    # ⭐ charge 액션은 이제 필요 없음 (create에 통합)
    # 하지만 호환성을 위해 남겨둘 수도 있음