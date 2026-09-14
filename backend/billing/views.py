from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.permissions import IsTreasurer, IsOrgMember, OrgQuerysetMixin
from .models import ChargeType, BillingPeriod, Charge, Payment
from .serializers import (
    ChargeTypeSerializer, BillingPeriodSerializer, ChargeSerializer,
    PaymentSerializer, BulkMembershipChargeSerializer, BulkTargetChargeSerializer,
)
from .services import create_membership_charges, create_target_charges, get_debt_summary


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
