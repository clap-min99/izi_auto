from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReservationViewSet, CouponCustomerViewSet

router = DefaultRouter()
router.register(r'reservations', ReservationViewSet, basename='reservation')
router.register(r'coupon-customers', CouponCustomerViewSet, basename='coupon-customer')

urlpatterns = [
    path('', include(router.urls)),
]