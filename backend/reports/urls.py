from django.urls import path
from .views import DebtReportView, ReceiptsReportView, MembersReportView

urlpatterns = [
    path("reports/debt/", DebtReportView.as_view(), name="report-debt"),
    path("reports/receipts/", ReceiptsReportView.as_view(), name="report-receipts"),
    path("reports/members/", MembersReportView.as_view(), name="report-members"),
]
