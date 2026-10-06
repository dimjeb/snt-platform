from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.permissions import (
    IsTreasurer, IsOrgMember, OrgQuerysetMixin, require_org,
)
from billing.models import BillingPeriod
from .models import EnergyTariff, Meter, MeterReading
from .serializers import (
    EnergyTariffSerializer, MeterSerializer, MeterReadingSerializer,
    CalculateElectricitySerializer, MeterOpeningSerializer, apply_opening,
)
from .services import calculate_electricity
from core.xlsx import import_response, template_response
from . import importing
import dataclasses


def own_meters_only(user):
    """
    Рядовой член видит и трогает только счётчики своих участков.

    Председатель и казначей ведут всё СНТ. Раньше член получал список всех
    показаний товарищества и мог сдать показание по чужому счётчику.
    """
    return not (user.is_superuser or user.is_treasurer)


def own_meter_q(user, prefix=""):
    from django.db.models import Q

    if not user.member_id:
        return Q(pk__in=[])
    return Q(**{f"{prefix}plot__ownerships__member_id": user.member_id,
                f"{prefix}plot__ownerships__date_to__isnull": True})


class EnergyTariffViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = EnergyTariff.objects.all()
    serializer_class = EnergyTariffSerializer
    permission_classes = [IsTreasurer]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))


class MeterViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Meter.objects.select_related("plot")
    serializer_class = MeterSerializer
    filterset_fields = ["is_main", "plot"]

    def get_queryset(self):
        qs = super().get_queryset()
        if own_meters_only(self.request.user):
            qs = qs.filter(own_meter_q(self.request.user)).distinct()
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsOrgMember()]
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))

    @action(detail=True, methods=["post"], permission_classes=[IsTreasurer])
    def opening(self, request, pk=None):
        """
        Показание и долг за свет для счётчика, заведённого без них.

        То же, что поля «Что на счётчике сейчас» при добавлении. Долг
        можно внести и отдельно, без показания.
        """
        from django.utils import timezone

        meter = self.get_object()
        s = MeterOpeningSerializer(data=request.data,
                                   context={"request": request, "meter": meter})
        s.is_valid(raise_exception=True)
        d = s.validated_data
        apply_opening(meter, user=request.user,
                      reading=d.get("initial_reading"),
                      night=d.get("initial_reading_night"),
                      on_date=d.get("initial_date") or timezone.localdate(),
                      debt=d.get("opening_debt"))
        return Response(MeterSerializer(meter).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="import",
            permission_classes=[IsTreasurer])
    def import_xlsx(self, request):
        """
        Загрузить счётчики и показания из Excel. dry_run=true (по
        умолчанию) — только проверить и показать отчёт.
        """
        org = require_org(request)
        return import_response(
            request, importing.COLUMNS, importing.REQUIRED,
            lambda rows: importing.import_meters(org, rows, request.user))

    @action(detail=False, methods=["get"], url_path="import-template",
            permission_classes=[IsTreasurer])
    def import_template(self, request):
        """Шаблон Excel для загрузки счётчиков и показаний."""
        return template_response("Шаблон — счётчики и показания.xlsx",
                                 importing.TEMPLATE_HEADER,
                                 importing.template_examples(),
                                 importing.TEMPLATE_NOTES)

    @action(detail=False, methods=["post"], permission_classes=[IsTreasurer])
    def calculate(self, request):
        """
        Рассчитать электроэнергию за период и создать начисления.
        """
        s = CalculateElectricitySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        org = require_org(request)

        try:
            billing_period = BillingPeriod.objects.get(
                pk=s.validated_data["billing_period_id"],
                organization=org,
            )
        except BillingPeriod.DoesNotExist:
            return Response({"detail": "Расчётный период не найден."}, status=404)

        try:
            results = calculate_electricity(
                org,
                s.validated_data["period_date"],
                billing_period,
            )
        except ValueError as exc:
            # Нет тарифа, период без месяца и т.п. — это сообщение
            # казначею, а не пятисотка с трейсбеком.
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
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
        if self.action in ("create", "list", "retrieve", "photo"):
            return [IsOrgMember()]
        return [IsTreasurer()]

    def get_queryset(self):
        qs = super().get_queryset()
        if own_meters_only(self.request.user):
            qs = qs.filter(own_meter_q(self.request.user, "meter__")).distinct()
        return qs

    def perform_create(self, serializer):
        serializer.save(
            organization=require_org(self.request),
            submitted_by=self.request.user,
        )

    @action(detail=True, methods=["get"], permission_classes=[IsOrgMember])
    def photo(self, request, pk=None):
        """
        Фото показания — только тем, кто видит само показание: казначею и
        владельцу участка. В открытую /media/ фото больше не попадают.
        """
        import mimetypes

        from django.http import FileResponse, Http404

        reading = self.get_object()
        if not reading.photo:
            raise Http404
        ctype = mimetypes.guess_type(reading.photo.name)[0] or "application/octet-stream"
        resp = FileResponse(reading.photo.open("rb"), content_type=ctype)
        resp["Cache-Control"] = "private, no-store"
        return resp
