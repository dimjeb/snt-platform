from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountingExportView, BudgetItemViewSet, BudgetViewSet, ExpenseViewSet,
    RevisionReportView,
)

router = DefaultRouter()
router.register("budgets", BudgetViewSet, basename="budget")
router.register("budget-items", BudgetItemViewSet, basename="budget-item")
router.register("expenses", ExpenseViewSet, basename="expense")

urlpatterns = router.urls + [
    path("reports/revision/", RevisionReportView.as_view(), name="report-revision"),
    path("reports/accounting/", AccountingExportView.as_view(), name="report-accounting"),
]
