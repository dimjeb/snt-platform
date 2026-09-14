from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MyDebtView,
    MyIntentViewSet,
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
    # Адрес вебхука настраивается в личном кабинете провайдера:
    # https://<домен>/api/payments/webhook/<id провайдера>/
    path("payments/webhook/<int:provider_id>/", WebhookView.as_view(),
         name="payment-webhook"),
] + router.urls
