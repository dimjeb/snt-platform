from django.http import HttpResponse
from django.core.mail import EmailMessage
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import IsTreasurer, OrgQuerysetMixin
from billing.models import BillingPeriod
from .models import Report
from .generators import (
    generate_debt_excel, generate_receipts_excel, generate_members_excel
)
import logging

logger = logging.getLogger(__name__)


class ReportViewSet(OrgQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    from rest_framework import serializers

    class ReportSerializer(serializers.ModelSerializer):
        class Meta:
            from reports.models import Report
            model = Report
            exclude = ("organization",)

    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsTreasurer]


class DebtReportView(APIView):
    permission_classes = [IsTreasurer]

    def get(self, request):
        """Скачать ведомость задолженностей (Excel)."""
        content = generate_debt_excel(request.org)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="debt_report.xlsx"'
        return response

    def post(self, request):
        """Отправить ведомость на email."""
        email = request.data.get("email")
        if not email:
            return Response({"detail": "email обязателен."}, status=400)

        content = generate_debt_excel(request.org)
        msg = EmailMessage(
            subject=f"Ведомость задолженностей — {request.org.name}",
            body="Во вложении ведомость задолженностей.",
            to=[email],
        )
        msg.attach("debt_report.xlsx", content,
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        try:
            msg.send()
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return Response({"detail": f"Ошибка отправки: {e}"}, status=500)

        return Response({"detail": f"Отчёт отправлен на {email}."})


class ReceiptsReportView(APIView):
    permission_classes = [IsTreasurer]

    def get(self, request):
        period_id = request.query_params.get("period_id")
        if not period_id:
            return Response({"detail": "period_id обязателен."}, status=400)
        try:
            period = BillingPeriod.objects.get(pk=period_id, organization=request.org)
        except BillingPeriod.DoesNotExist:
            return Response({"detail": "Период не найден."}, status=404)

        content = generate_receipts_excel(request.org, period)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="receipts_{period}.xlsx"'
        return response


class MembersReportView(APIView):
    permission_classes = [IsTreasurer]

    def get(self, request):
        content = generate_members_excel(request.org)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="members.xlsx"'
        return response
