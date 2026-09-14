from rest_framework.routers import DefaultRouter
from .views import ChargeTypeViewSet, BillingPeriodViewSet, ChargeViewSet, PaymentViewSet

router = DefaultRouter()
router.register("billing/charge-types", ChargeTypeViewSet, basename="charge-type")
router.register("billing/periods", BillingPeriodViewSet, basename="period")
router.register("billing/charges", ChargeViewSet, basename="charge")
router.register("billing/payments", PaymentViewSet, basename="payment")

urlpatterns = router.urls
