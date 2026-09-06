from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.permissions import IsTreasurer, IsOrgMember, OrgQuerysetMixin
from billing.models import BillingPeriod
from .models import EnergyTariff, Meter, MeterReading
from .serializers import (
    EnergyTariffSerializer, MeterSerializer, MeterReadingSerializer,
    CalculateElectricitySerializer,
)
from .services import calculate_electricity
import dataclasses


class EnergyTariffViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = EnergyTariff.objects.all()
    serializer_class = EnergyTariffSerializer
    permission_classes = [IsTreasurer]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class MeterViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Meter.objects.select_related("plot")
    serializer_class = MeterSerializer
    filterset_fields = ["is_main", "plot"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsOrgMember()]
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)

    @action(detail=False, methods=["post"], permission_classes=[IsTreasurer])
    def calculate(self, request):
        """
        Рассчитать электроэнергию за период и создать начисления.
        """
        s = CalculateElectricitySerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            billing_period = BillingPeriod.objects.get(
                pk=s.validated_data["billing_period_id"],
                organization=request.org,
            )
        except BillingPeriod.DoesNotExist:
            return Response({"detail": "Расчётный период не найден."}, status=404)

        results = calculate_electricity(
            request.org,
            s.validated_data["period_date"],
            billing_period,
        )
        return Response({
            "calculated": len(results),
            "details": [dataclasses.asdict(r) for r in results],
        })


class MeterReadingViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = MeterReading.objects.select_related("meter__plot", "submitted_by")
    serializer_class = MeterReadingSerializer
    filterset_fields = ["meter", "date"]
    ordering_fields = ["date"]

    def get_permissions(self):
        # Члены СНТ могут вводить свои показания
        if self.action in ("create", "list", "retrieve"):
            return [IsOrgMember()]
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.org,
            submitted_by=self.request.user,
        )
