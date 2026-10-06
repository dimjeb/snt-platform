import datetime as dt

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import record_access
from core.models import AccessLog
from core.permissions import IsChairman, IsTreasurer, OrgQuerysetMixin, require_org

from . import documents
from .models import Budget, BudgetItem, Expense
from .serializers import (
    ApproveSerializer, BudgetItemSerializer, BudgetSerializer,
    ChargeMembershipSerializer, ExpenseSerializer,
)
from .services import as_json, copy_items, execution, fee_calc

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def xlsx_response(content, filename):
    from urllib.parse import quote

    resp = HttpResponse(content, content_type=XLSX)
    resp["Content-Disposition"] = (
        f"attachment; filename=document.xlsx; filename*=UTF-8''{quote(filename)}")
    return resp


class BudgetViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Budget.objects.prefetch_related("items")
    serializer_class = BudgetSerializer
    filterset_fields = ["year"]
    CHAIRMAN_ONLY = ("approve", "unapprove")

    def get_permissions(self):
        # Утверждение — решение собрания; отмечает его председатель.
        if self.action in self.CHAIRMAN_ONLY:
            return [IsChairman()]
        return [IsTreasurer()]

    @transaction.atomic
    def perform_create(self, serializer):
        org = require_org(self.request)
        copy_from = serializer.validated_data.pop("copy_from", None)
        budget = serializer.save(organization=org)
        if copy_from:
            source = Budget.objects.filter(organization=org, year=copy_from).first()
            if source is not None:
                copy_items(source, budget)

    def perform_destroy(self, instance):
        if instance.is_approved:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Утверждённую смету не удаляют.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        budget = self.get_object()
        s = ApproveSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not budget.items.exists():
            return Response({"detail": "В смете нет ни одной статьи."},
                            status=status.HTTP_400_BAD_REQUEST)
        budget.status = Budget.STATUS_APPROVED
        budget.approved_at = s.validated_data["approved_at"]
        budget.protocol_number = s.validated_data.get("protocol_number", "")
        budget.save(update_fields=["status", "approved_at", "protocol_number", "updated_at"])
        return Response(BudgetSerializer(budget, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def unapprove(self, request, pk=None):
        budget = self.get_object()
        budget.status = Budget.STATUS_DRAFT
        budget.save(update_fields=["status", "updated_at"])
        return Response(BudgetSerializer(budget, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def execution(self, request, pk=None):
        return Response(as_json(execution(self.get_object())))

    @action(detail=True, methods=["get"], url_path="document/(?P<kind>smeta|feo|execution)")
    def document(self, request, pk=None, kind=None):
        budget = self.get_object()
        if kind == "smeta":
            content = documents.smeta_xlsx(budget, fee_calc(budget))
            name = f"Смета {budget.year}.xlsx"
        elif kind == "feo":
            content = documents.feo_xlsx(budget, fee_calc(budget))
            name = f"ФЭО взносов {budget.year}.xlsx"
        else:
            content = documents.execution_xlsx(budget, execution(budget))
            name = f"Исполнение сметы {budget.year}.xlsx"
        return xlsx_response(content, name)

    @action(detail=True, methods=["post"], url_path="charge-membership")
    def charge_membership(self, request, pk=None):
        """Начислить членский взнос всем участкам по утверждённой смете."""
        from billing.models import BillingPeriod
        from billing.services import BASIS_FLAT, BASIS_PER_SOTKA, create_membership_charges

        budget = self.get_object()
        if not budget.is_approved:
            return Response(
                {"detail": "Смета ещё не утверждена. Размер взноса по закону "
                           "определяет смета, утверждённая общим собранием."},
                status=status.HTTP_400_BAD_REQUEST)
        s = ChargeMembershipSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        calc = fee_calc(budget)
        if calc["rate"] is None or calc["rate"] <= 0:
            return Response({"detail": "Размер взноса не посчитан: " +
                             (" ".join(calc["warnings"]) or "нет статей за счёт членских взносов.")},
                            status=status.HTTP_400_BAD_REQUEST)
        org = budget.organization
        with transaction.atomic():
            period = (BillingPeriod.objects
                      .filter(organization=org, year=budget.year, month__isnull=True)
                      .order_by("pk").first())
            if period is None:
                period = BillingPeriod.objects.create(organization=org,
                                                      year=budget.year, month=None)
            proto = f", протокол № {budget.protocol_number}" if budget.protocol_number else ""
            description = (f"Членский взнос на {budget.year} год (смета утверждена "
                           f"{budget.approved_at:%d.%m.%Y}{proto})")
            per_sotka = budget.basis == Budget.BASIS_PER_SOTKA
            result = create_membership_charges(
                period,
                amount=None if per_sotka else calc["rate"],
                rate=calc["rate"] if per_sotka else None,
                basis=BASIS_PER_SOTKA if per_sotka else BASIS_FLAT,
                description=description,
                due_date=s.validated_data.get("due_date"),
                penalty_percent=s.validated_data.get("penalty_percent"),
            )
        return Response(as_json({**result, "rate": calc["rate"], "period": str(period)}))


class BudgetItemViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = BudgetItem.objects.select_related("budget")
    serializer_class = BudgetItemSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["budget"]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))

    def perform_destroy(self, instance):
        if instance.budget.is_approved:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Смета утверждена — статьи не удаляются.")
        instance.delete()


class ExpenseViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Expense.objects.select_related("item", "recorded_by")
    serializer_class = ExpenseSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["item"]

    def get_queryset(self):
        qs = super().get_queryset()
        year = self.request.query_params.get("year")
        if year and year.isdigit():
            qs = qs.filter(date__year=int(year))
        return qs

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request),
                        recorded_by=self.request.user)


def _parse_date(value, name):
    from rest_framework.exceptions import ValidationError
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({name: "Нужна дата в формате ГГГГ-ММ-ДД."})


class RevisionReportView(APIView):
    """Ведомость расчётов с членами за год — для ревизионной комиссии."""
    permission_classes = [IsTreasurer]

    def get(self, request):
        org = require_org(request)
        year = request.query_params.get("year", "")
        if not year.isdigit():
            return Response({"detail": "Укажите год."}, status=400)
        record_access(request, "ведомость для ревизионной комиссии",
                      AccessLog.ACTION_EXPORT)
        return xlsx_response(documents.revision_xlsx(org, int(year)),
                             f"Ведомость расчётов {year}.xlsx")


class AccountingExportView(APIView):
    """Выгрузка для бухгалтера: поступления, начисления, расходы, сальдо."""
    permission_classes = [IsTreasurer]

    def get(self, request):
        org = require_org(request)
        date_from = _parse_date(request.query_params.get("date_from"), "date_from")
        date_to = _parse_date(request.query_params.get("date_to"), "date_to")
        if date_from > date_to:
            return Response({"detail": "Начало периода позже конца."}, status=400)
        record_access(request, "выгрузка для бухгалтера", AccessLog.ACTION_EXPORT)
        return xlsx_response(
            documents.accounting_xlsx(org, date_from, date_to),
            f"Для бухгалтера {date_from:%d.%m.%Y}-{date_to:%d.%m.%Y}.xlsx")
