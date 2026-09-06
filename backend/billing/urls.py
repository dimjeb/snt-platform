from rest_framework.routers import DefaultRouter
from .views import ChargeTypeViewSet, BillingPeriodViewSet, ChargeViewSet, PaymentViewSet

router = DefaultRouter()
router.register("charge-types", ChargeTypeViewSet, basename="charge-type")
router.register("periods", BillingPeriodViewSet, basename="period")
router.register("charges", ChargeViewSet, basename="charge")
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = router.urls
