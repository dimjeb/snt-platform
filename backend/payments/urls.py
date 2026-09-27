from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MyDebtView,
    MyIntentViewSet,
    MyPaymentQRImageView,
    MyPaymentQRView,
    ObligatoryPaymentViewSet,
    PayView,
    WebhookView,
)

router = DefaultRouter()
router.register("payments/intents", MyIntentViewSet, basename="payment-intent")
router.register("payments/obligatory", ObligatoryPaymentViewSet,
                basename="obligatory-payment")

urlpatterns = [
    path("payments/my-debt/", MyDebtView.as_view(), name="my-debt"),
    path("payments/pay/", PayView.as_view(), name="pay"),
    # Оплата переводом по QR — работает без эквайринга
    path("payments/qr/", MyPaymentQRView.as_view(), name="payment-qr"),
    path("payments/qr.png", MyPaymentQRImageView.as_view(), name="payment-qr-image"),
    # Адрес вебхука настраивается в личном кабинете провайдера:
    # https://<домен>/api/payments/webhook/<id провайдера>/
    path("payments/webhook/<int:provider_id>/", WebhookView.as_view(),
         name="payment-webhook"),
] + router.urls
