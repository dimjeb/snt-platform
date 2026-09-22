from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.permissions import IsTreasurer, IsOrgMember, OrgQuerysetMixin
from .models import ChargeType, BillingPeriod, Charge, Payment
from .serializers import (
    ChargeTypeSerializer, BillingPeriodSerializer, ChargeSerializer,
    PaymentSerializer, BulkMembershipChargeSerializer, BulkTargetChargeSerializer,
)
from django.db.models import Count

from .models import BankStatement, BankTransaction
from .serializers import (
    BankStatementListSerializer,
    BankStatementSerializer,
    BankTransactionSerializer,
)
from .services import create_membership_charges, create_target_charges, get_debt_summary
from .statement import StatementError
from .statement_service import (
    StatementImportError,
    apply_statement,
    import_statement,
    statement_summary,
)


class ChargeTypeViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = ChargeType.objects.all()
    serializer_class = ChargeTypeSerializer
    permission_classes = [IsTreasurer]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class BillingPeriodViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = BillingPeriod.objects.all()
    serializer_class = BillingPeriodSerializer
    permission_classes = [IsTreasurer]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)

    # Все три операции относятся к конкретному расчётному периоду, поэтому
    # маршруты detail: период берётся из URL, а не из тела запроса. Раньше
    # они были объявлены detail=False, и фронт, зовущий
    # /billing/periods/<id>/debt_summary/, получал 404 — страница начислений
    # не работала целиком.
    @action(detail=True, methods=["get"])
    def debt_summary(self, request, pk=None):
        """Сводка долгов по участкам за этот расчётный период."""
        period = self.get_object()
        return Response(get_debt_summary(request.org, period=period))

    @action(detail=True, methods=["post"])
    def create_membership_charges(self, request, pk=None):
        """Массовое создание членских взносов за этот период."""
        period = self.get_object()
        s = BulkMembershipChargeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        count = create_membership_charges(
            period, s.validated_data["amount"], s.validated_data["description"]
        )
        return Response({"created": count})

    @action(detail=True, methods=["post"])
    def create_target_charges(self, request, pk=None):
        """Создание целевых взносов за этот период."""
        period = self.get_object()
        s = BulkTargetChargeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        charge_type = ChargeType.objects.get(
            pk=s.validated_data["charge_type_id"], organization=request.org
        )
        count = create_target_charges(
            period, charge_type,
            s.validated_data["amount"],
            s.validated_data.get("plot_ids"),
            s.validated_data["description"],
        )
        return Response({"created": count})


class ChargeViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Charge.objects.select_related(
        "period", "plot", "charge_type"
    ).prefetch_related("payments")
    serializer_class = ChargeSerializer
    filterset_fields = ["period", "plot", "charge_type"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsOrgMember()]
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class PaymentViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("charge__plot", "recorded_by")
    serializer_class = PaymentSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["charge", "method", "is_cancelled"]

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.org,
            recorded_by=self.request.user,
        )


class BankStatementViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    """
    Банковские выписки: загрузка, разбор, проведение.

    Только казначею и председателю: здесь создаются платежи, то есть
    закрываются чужие долги.
    """

    queryset = BankStatement.objects.prefetch_related(
        "transactions__plot", "transactions__member"
    )
    permission_classes = [IsTreasurer]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return BankStatementListSerializer
        return BankStatementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list":
            return qs.annotate(rows_count=Count("transactions"))
        return qs

    def create(self, request, *args, **kwargs):
        """Загрузить файл выписки. Разбирает и сопоставляет, но не проводит."""
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Файл не передан."},
                            status=status.HTTP_400_BAD_REQUEST)
        if upload.size > 10 * 1024 * 1024:
            return Response({"detail": "Файл больше 10 МБ — это не выписка."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            statement, stats = import_statement(
                request.org, raw=upload.read(), file_name=upload.name,
                user=request.user,
            )
        except (StatementError, StatementImportError) as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        data = BankStatementSerializer(statement).data
        data["stats"] = stats
        data["summary"] = statement_summary(statement)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Провести выписку: создать платежи по опознанным строкам."""
        statement = self.get_object()
        if statement.status == BankStatement.STATUS_APPLIED:
            return Response({"detail": "Эта выписка уже проведена."},
                            status=status.HTTP_400_BAD_REQUEST)
        result = apply_statement(statement, user=request.user)
        return Response({
            **result,
            "statement": BankStatementSerializer(statement).data,
        })

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        return Response(statement_summary(self.get_object()))


class BankTransactionViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    """
    Строки выписки. Правится только привязка к участку.

    Суммы и даты приходят из банка: правка их создала бы расхождение с
    выпиской, которое потом никто не объяснит.
    """

    queryset = BankTransaction.objects.select_related("plot", "member")
    serializer_class = BankTransactionSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["statement", "status", "match_kind"]
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        # Ручная привязка помечается отдельно: по журналу должно быть
        # видно, где сработал автомат, а где решил человек.
        instance = serializer.save()
        if "plot" in serializer.validated_data:
            instance.match_kind = BankTransaction.MATCH_MANUAL
            instance.save(update_fields=["match_kind", "updated_at"])
