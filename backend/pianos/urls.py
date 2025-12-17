# backend/pianos/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router 설정
router = DefaultRouter()
router.register(r'reservations', views.ReservationViewSet, basename='reservation')
router.register(r'coupon-customers', views.CouponCustomerViewSet, basename='coupon-customer')
router.register(r"message-templates", views.MessageTemplateViewSet, basename="message-templates")
router.register(r"studio-policy", views.StudioPolicyViewSet, basename="studio-policy")
router.register(r'account-transactions', views.AccountTransactionViewSet, basename='account-transactions')
router.register(r"room-passwords", views.RoomPasswordViewSet)
router.register(r"automation-control", views.AutomationControlViewSet, basename="automation-control")



urlpatterns = [
    # ViewSet URLs (자동 생성)
    path('', include(router.urls)),
    
    # ★ 테스트용 API (DRY_RUN 환경에서만 사용)
    path('test/transactions/', views.test_transactions, name='test_transactions'),
]

"""
생성되는 URL 목록:

기존 API:
- GET    /api/reservations/                    # 예약 목록 조회
- POST   /api/reservations/                    # 예약 생성
- GET    /api/reservations/{id}/               # 예약 상세 조회
- PATCH  /api/reservations/{id}/               # 예약 수정
- DELETE /api/reservations/{id}/               # 예약 삭제

- GET    /api/coupon-customers/                # 쿠폰 고객 목록 조회
- POST   /api/coupon-customers/                # 쿠폰 고객 등록/충전
- GET    /api/coupon-customers/{id}/           # 쿠폰 고객 상세 조회
- PATCH  /api/coupon-customers/{id}/           # 쿠폰 고객 수정
- DELETE /api/coupon-customers/{id}/           # 쿠폰 고객 삭제
- GET    /api/coupon-customers/{id}/history/   # 쿠폰 사용 이력 조회

테스트 API:
- POST   /api/test/transactions/               # 테스트 계좌 내역 생성
- GET    /api/test/transactions/               # 테스트 계좌 내역 조회
- DELETE /api/test/transactions/               # 테스트 계좌 내역 삭제

입시기간 API:
- GET /api/studio-policy/
- PATCH /api/studio-policy/1/


"""

