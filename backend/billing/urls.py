from rest_framework.routers import DefaultRouter
from .views import (
    BankStatementViewSet,
    BankTransactionViewSet,
    BillingPeriodViewSet,
    ChargeTypeViewSet,
    ChargeViewSet,
    PaymentViewSet,
)

router = DefaultRouter()
router.register("billing/charge-types", ChargeTypeViewSet, basename="charge-type")
router.register("billing/periods", BillingPeriodViewSet, basename="period")
router.register("billing/charges", ChargeViewSet, basename="charge")
router.register("billing/payments", PaymentViewSet, basename="payment")
router.register("billing/statements", BankStatementViewSet, basename="bank-statement")
router.register("billing/transactions", BankTransactionViewSet,
                basename="bank-transaction")

urlpatterns = router.urls
