# backend/pianos/views.py

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from dateutil.relativedelta import relativedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from datetime import datetime
from .automation.coupon_manager import get_room_category


from .models import Reservation, CouponCustomer, CouponHistory, AccountTransaction, MessageTemplate, StudioPolicy, AccountTransaction, RoomPassword, AutomationControl
from .serializers import (
    ReservationSerializer,
    CouponCustomerListSerializer,
    CouponCustomerDetailSerializer,
    CouponHistorySerializer,
    CouponCustomerRegisterOrChargeSerializer,
    MessageTemplateSerializer,
    StudioPolicySerializer,
    AccountTransactionSerializer,
    RoomPasswordSerializer,
    AutomationControlSerializer
)
from .message_templates import DEFAULT_TEMPLATES, render_template


class ReservationViewSet(viewsets.ModelViewSet):
    """예약 관리 ViewSet"""
    
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['customer_name', 'phone_number']

    # ✅ 기본 정렬(요청에 ordering 없을 때)
    ordering = ['-created_at']

    # ✅ 프론트에서 허용할 정렬 필드
    ordering_fields = ['created_at', 'reservation_date', 'start_time']

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

            coupon_type = serializer.validated_data['coupon_type']
            piano_category = serializer.validated_data['piano_category']
            today = timezone.localdate()
    
            # 전화번호, 룸 유형으로 기존 고객 찾기
            customer, created = CouponCustomer.objects.get_or_create(
                phone_number=phone_number,
                piano_category=piano_category,
                defaults={
                    'customer_name': customer_name,
                    'remaining_time': 0,
                }
            )
            
            # ✅ 쿠폰 타입별 유효기간(개월)
            months_map = {
                10: 1,
                20: 2,
                50: 2,
                100: 3,
            }
            expire_months = months_map.get(int(coupon_type), 0)
            expires_at = today + relativedelta(months=expire_months)

            # 이름 업데이트 (변경되었을 수 있으니)
            if customer.customer_name != customer_name:
                customer.customer_name = customer_name
            
            # ✅ 쿠폰 메타 정보 업데이트(등록/충전할 때 항상 최신 기준으로 덮어씀)
            customer.coupon_type = int(coupon_type)
            # 수입충전은 수입 쿠폰만, 국산 충전은 국산 쿠폰만 업데이트하기 위해 주석처리
            # customer.piano_category = piano_category
            customer.coupon_registered_at = today
            customer.coupon_expires_at = expires_at
            customer.coupon_status = "활성"

            # 시간 충전
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

                    # ✅ 응답에 표시
                    'coupon_type': customer.coupon_type,
                    'piano_category': customer.piano_category,
                    'coupon_status': customer.coupon_status,
                    'coupon_registered_at': customer.coupon_registered_at,
                    'coupon_expires_at': customer.coupon_expires_at,
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
        PATCH /api/coupon-customers/{id}/

        허용: customer_name, phone_number, coupon_expires_at, remaining_time(분)
        remaining_time 변경 시 CouponHistory에 transaction_type='수동' 이력 1건 생성
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # 수정 가능한 필드만 추출
        allowed_fields = ['customer_name', 'phone_number', 'coupon_expires_at', 'remaining_time', 'reason']
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        reason = (filtered_data.pop('reason', '') or '').strip() 

        before_remaining = instance.remaining_time
        before_name = instance.customer_name
        before_phone = instance.phone_number
        before_expires = instance.coupon_expires_at
        serializer = CouponCustomerListSerializer(
            instance, 
            data=filtered_data, 
            partial=partial
        )
        serializer.is_valid(raise_exception=True)            
        self.perform_update(serializer)

        # ✅ remaining_time 변경이면 '수동' 이력 남기기
        instance.refresh_from_db(fields=['remaining_time', 'customer_name', 'phone_number', 'coupon_expires_at'])
        after_remaining = instance.remaining_time

        if 'remaining_time' in filtered_data and after_remaining != before_remaining:
            delta = after_remaining - before_remaining  # +면 충전, -면 차감
            
            CouponHistory.objects.create(
                customer=instance,
                reservation=None,
                customer_name=instance.customer_name,
                room_name=None,
                transaction_date=timezone.localdate(),
                start_time=None,
                end_time=None,
                remaining_time=after_remaining,
                used_or_charged_time=delta,
                transaction_type='수동',
                reason=reason or None,   
            )
        other_changed = (
            ('customer_name' in filtered_data and instance.customer_name != before_name) or
            ('phone_number' in filtered_data and instance.phone_number != before_phone) or
            ('coupon_expires_at' in filtered_data and instance.coupon_expires_at != before_expires)
        )
        if other_changed and not ('remaining_time' in filtered_data and after_remaining != before_remaining):
            CouponHistory.objects.create(
                customer=instance,
                reservation=None,
                customer_name=instance.customer_name,
                room_name=None,
                transaction_date=timezone.localdate(),
                start_time=None,
                end_time=None,
                remaining_time=instance.remaining_time,
                used_or_charged_time=0,
                transaction_type='수정',
                reason=reason or None,
            )
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
                customer.histories.all().order_by('-created_at', 'id'),
                many=True
            ).data
        })


# ============================================================
# ★ 테스트용 API (DRY_RUN 환경에서만 사용)
# ============================================================

@api_view(['POST', 'GET', 'DELETE'])
def test_transactions(request):
    """
    테스트용 계좌 내역 API (통합)
    
    POST: 계좌 내역 생성
    GET: 계좌 내역 조회
    DELETE: 테스트 데이터 삭제
    """
    
    if request.method == 'POST':
        return create_test_transaction(request)
    elif request.method == 'GET':
        return get_test_transactions(request)
    elif request.method == 'DELETE':
        return delete_test_transactions(request)


def create_test_transaction(request):
    """
    테스트용 계좌 내역 생성
    
    POST /api/test/transactions/
    
    Request Body:
    {
        "depositor_name": "박수민",
        "amount": 20000
    }
    """
    try:
        # 요청 데이터 추출
        depositor_name = request.data.get('depositor_name')
        amount = request.data.get('amount')
        
        # 유효성 검증
        if not depositor_name or not amount:
            return Response(
                {
                    'error': '필수 파라미터 누락',
                    'detail': 'depositor_name과 amount는 필수입니다.',
                    'example': {
                        'depositor_name': '박수민',
                        'amount': 20000
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 현재 시간
        now = datetime.now()
        
        # transaction_id 생성 (날짜+시간+밀리초로 고유성 보장)
        transaction_id = f"TEST_{now.strftime('%Y%m%d%H%M%S')}_{now.microsecond}"
        
        # 계좌 내역 생성
        trans = AccountTransaction.objects.create(
            transaction_id=transaction_id,
            transaction_date=now.date(),
            transaction_time=now.time(),
            transaction_type='입금',
            amount=int(amount),
            balance=1000000,  # 더미 잔액
            depositor_name=depositor_name,
            memo='테스트 입금 (POSTMAN)',
            match_status='확정전'  # 기본값
        )
        
        return Response({
            'message': '✅ 테스트 계좌 내역 생성 완료',
            'transaction': {
                'id': trans.id,
                'transaction_id': trans.transaction_id,
                'depositor_name': trans.depositor_name,
                'amount': trans.amount,
                'transaction_date': str(trans.transaction_date),
                'transaction_time': trans.transaction_time.strftime('%H:%M:%S'),
                'match_status': trans.match_status
            },
            'next_step': '이제 monitor.py에서 자동으로 입금 확인이 진행됩니다.'
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response(
            {
                'error': '잘못된 값',
                'detail': 'amount는 숫자여야 합니다.',
                'received': request.data
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {
                'error': '서버 오류',
                'detail': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def get_test_transactions(request):
    """
    테스트용 계좌 내역 조회
    
    GET /api/test/transactions/
    
    Query Parameters:
        - match_status: 확정전 | 확정완료 | 취소
    """
    try:
        match_status_param = request.query_params.get('match_status')
        
        # 필터링
        queryset = AccountTransaction.objects.filter(
            transaction_id__startswith='TEST_'  # 테스트 거래만
        )
        
        if match_status_param:
            queryset = queryset.filter(match_status=match_status_param)
        
        # 최신순 정렬
        transactions = queryset.order_by('-created_at')[:20]
        
        # 결과 변환
        results = []
        for trans in transactions:
            results.append({
                'id': trans.id,
                'transaction_id': trans.transaction_id,
                'depositor_name': trans.depositor_name,
                'amount': trans.amount,
                'transaction_date': str(trans.transaction_date),
                'transaction_time': trans.transaction_time.strftime('%H:%M:%S'),
                'match_status': trans.match_status,
                'matched_reservations_count': trans.matched_reservations.count(),
                'created_at': trans.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return Response({
            'count': len(results),
            'transactions': results
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {
                'error': '조회 오류',
                'detail': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def delete_test_transactions(request):
    """
    테스트용 계좌 내역 전체 삭제
    
    DELETE /api/test/transactions/
    
    주의: TEST_로 시작하는 거래만 삭제됩니다.
    """
    try:
        # TEST_로 시작하는 거래만 삭제
        deleted_count, _ = AccountTransaction.objects.filter(
            transaction_id__startswith='TEST_'
        ).delete()
        
        return Response({
            'message': '✅ 테스트 계좌 내역 삭제 완료',
            'deleted_count': deleted_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {
                'error': '삭제 오류',
                'detail': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class MessageTemplateViewSet(viewsets.ModelViewSet):
    queryset = MessageTemplate.objects.all().order_by("id")
    serializer_class = MessageTemplateSerializer

    # PATCH로 content/is_active 수정 가능
    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        # code는 수정 불가
        data = request.data.copy()
        data.pop("code", None)
        serializer = self.get_serializer(obj, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="seed")
    def seed(self, request):
        """
        코드가 없으면 기본 템플릿을 생성합니다.
        (이미 있으면 content는 건드리지 않는 방식)
        """
        created = 0
        with transaction.atomic():
            for code, meta in DEFAULT_TEMPLATES.items():
                _, was_created = MessageTemplate.objects.get_or_create(
                    code=code,
                    defaults={
                        "title": meta["title"],
                        "content": meta["content"],
                        "is_active": True,
                    },
                )
                if was_created:
                    created += 1
        return Response({"created": created}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        """
        code + reservation_id(선택)로 실제 치환된 문구를 반환합니다.
        """
        code = request.data.get("code")
        reservation_id = request.data.get("reservation_id")
        extra_ctx = request.data.get("context") or {}

        if not code:
            return Response({"detail": "code is required"}, status=400)

        tpl = MessageTemplate.objects.filter(code=code, is_active=True).first()
        # DB에 없거나 비활성일 때는 기본값 fallback
        base = DEFAULT_TEMPLATES.get(code, {})
        content = (tpl.content if tpl else base.get("content", ""))

        ctx = {
            "studio": "이지피아노스튜디오",
        }

        if reservation_id:
            r = Reservation.objects.filter(id=reservation_id).first()
            if r:
                duration_minutes = r.get_duration_minutes()
                room_name = (r.room_name or "").strip()
                rp = RoomPassword.objects.filter(room_name=room_name).first()
                room_pw = rp.room_pw if rp else ""
                ctx.update({
                    "customer_name": r.customer_name,
                     "room_name": room_name,
                    "room_pw": room_pw, 
                    "date": str(r.reservation_date),
                    "start_time": str(r.start_time)[:5],
                    "end_time": str(r.end_time)[:5],
                    "price": getattr(r, "price", ""),
                    "duration_minutes": duration_minutes,  # ✅ 추가
                })

                # ✅ 쿠폰 고객(전화번호로 찾는 게 제일 안정적)
                room_category = get_room_category(getattr(r, "room_name", ""))
                customer = CouponCustomer.objects.filter(
                    phone_number=r.phone_number,
                    piano_category=room_category,
                ).first()
                if customer:
                    ctx.update({
                        "remaining_minutes": customer.remaining_time,        # ✅ 추가
                        "piano_category": customer.piano_category or "",     # ✅ 추가 (수입/국산)
                    })

        if isinstance(extra_ctx, dict):
            ctx.update(extra_ctx)

        rendered = render_template(content, ctx)
        return Response({"rendered": rendered}, status=200)
    

class AccountTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    계좌 입금 내역 조회용 ViewSet
    - 팝빌에서 동기화되어 DB에 저장된 데이터 조회만 수행
    """
    queryset = AccountTransaction.objects.all()
    serializer_class = AccountTransactionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    filter_backends = [SearchFilter]
    search_fields = [
        "depositor_name",
        "memo",
        "transaction_id",
    ]

    ordering = ["-transaction_date", "-transaction_time", "-id"]



class StudioPolicyViewSet(viewsets.ViewSet):
    def get_object(self):
        obj, _ = StudioPolicy.objects.get_or_create(id=1)
        return obj

    def list(self, request):
        obj = self.get_object()
        return Response(StudioPolicySerializer(obj).data)

    def partial_update(self, request, pk=None):
        obj = self.get_object()
        serializer = StudioPolicySerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class RoomPasswordViewSet(viewsets.ModelViewSet):
    queryset = RoomPassword.objects.all().order_by("room_name")
    serializer_class = RoomPasswordSerializer

class AutomationControlViewSet(viewsets.ViewSet):
    def get_object(self):
        obj, _ = AutomationControl.objects.get_or_create(id=1)
        return obj

    def list(self, request):
        obj = self.get_object()
        return Response(AutomationControlSerializer(obj).data)

    def partial_update(self, request, pk=None):
        obj = self.get_object()
        serializer = AutomationControlSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)