from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import EnergyTariff, Meter, MeterReading


def _check_same_org(obj, request, label):
    """Объект из чужого СНТ подставить по id нельзя."""
    org = getattr(request, "org", None) if request else None
    if obj is not None and org is not None and obj.organization_id != org.id:
        raise serializers.ValidationError(f"{label} не найден.")
    return obj


class EnergyTariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnergyTariff
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")


class OpeningFieldsMixin(serializers.Serializer):
    """
    Что на счётчике сейчас и сколько за свет должны до сайта.

    Счётчик почти всегда заводят на участке, где свет давно горит: без
    показания на сегодня первый расчёт считать не от чего, а долг за
    прошлое иначе пришлось бы вносить отдельно.
    """

    initial_reading = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0"),
        required=False, allow_null=True, write_only=True,
    )
    initial_reading_night = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0"),
        required=False, allow_null=True, write_only=True,
    )
    initial_date = serializers.DateField(
        required=False, allow_null=True, write_only=True,
    )
    opening_debt = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True, write_only=True,
    )

    def check_opening(self, attrs, *, is_main, plot):
        reading = attrs.get("initial_reading")
        night = attrs.get("initial_reading_night")
        debt = attrs.get("opening_debt") or Decimal("0")
        if night is not None and reading is None:
            raise serializers.ValidationError(
                {"initial_reading_night": "Сначала укажите дневное (общее) показание."})
        if debt > 0:
            if is_main:
                raise serializers.ValidationError(
                    {"opening_debt": "У главного ввода долга нет — долг вносится "
                                     "по счётчику участка."})
            if not plot:
                raise serializers.ValidationError(
                    {"opening_debt": "Выберите участок — долг записывается на него."})
        return attrs


class MeterSerializer(OpeningFieldsMixin, serializers.ModelSerializer):
    plot_number = serializers.CharField(source="plot.number", read_only=True)

    INITIAL_FIELDS = ("initial_reading", "initial_reading_night",
                      "initial_date", "opening_debt")

    class Meta:
        model = Meter
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")

    def validate_plot(self, plot):
        return _check_same_org(plot, self.context.get("request"), "Участок")

    def validate(self, attrs):
        if self.instance is not None:
            # Правка счётчика: начальные значения так не задаются — для
            # них отдельная кнопка «Показание и долг».
            for f in self.INITIAL_FIELDS:
                attrs.pop(f, None)
            return attrs
        return self.check_opening(attrs, is_main=attrs.get("is_main"),
                                  plot=attrs.get("plot"))

    @transaction.atomic
    def create(self, validated_data):
        reading = validated_data.pop("initial_reading", None)
        night = validated_data.pop("initial_reading_night", None)
        on_date = validated_data.pop("initial_date", None)
        debt = validated_data.pop("opening_debt", None) or Decimal("0")
        on_date = (on_date or validated_data.get("installed_at")
                   or timezone.localdate())

        meter = super().create(validated_data)
        request = self.context.get("request")
        apply_opening(meter, user=getattr(request, "user", None), reading=reading,
                      night=night, on_date=on_date, debt=debt)
        return meter


class MeterOpeningSerializer(OpeningFieldsMixin):
    """Показание и долг для счётчика, заведённого раньше без них."""

    def validate(self, attrs):
        meter = self.context["meter"]
        if attrs.get("initial_reading") is None and not attrs.get("opening_debt"):
            raise serializers.ValidationError(
                "Укажите показание, долг или и то и другое.")
        attrs = self.check_opening(attrs, is_main=meter.is_main, plot=meter.plot)
        on_date = attrs.get("initial_date") or timezone.localdate()
        if (attrs.get("initial_reading") is not None
                and MeterReading.objects.filter(meter=meter, date=on_date).exists()):
            raise serializers.ValidationError(
                {"initial_date": f"На {on_date:%d.%m.%Y} показание по этому "
                                 f"счётчику уже есть."})
        return attrs


@transaction.atomic
def apply_opening(meter, *, user, reading, night, on_date, debt):
    """Записать начальное показание и долг за свет — одной транзакцией."""
    if user is not None and not user.is_authenticated:
        user = None
    if reading is not None:
        # Обычное (не расчётное) показание: от него пойдёт первый
        # расчёт. Расход до этой даты не начисляется — он либо уже
        # оплачен, либо сидит в долге ниже.
        MeterReading.objects.create(
            organization=meter.organization, meter=meter,
            date=on_date, value=reading, value_night=night,
            submitted_by=user,
            notes="Начальное показание при добавлении счётчика",
        )
    if debt and debt > 0:
        add_opening_debt(meter, debt, on_date, reading, user)


def add_opening_debt(meter, amount, on_date, reading, user):
    """
    Долг за свет, накопленный до сайта, — начислением на участок.

    Кладём в годовой период, а не в месячный: месячное начисление за свет
    перезаписывает расчёт (одно «Электроэнергия» на участок в месяц), и
    долг на момент установки он бы затёр или удалил. Годовой период
    расчёт света не трогает никогда.
    """
    from billing.credits import spend_credit
    from billing.models import BillingPeriod, Charge, ChargeType

    org = meter.organization
    period = (BillingPeriod.objects
              .filter(organization=org, year=on_date.year, month__isnull=True)
              .order_by("pk").first())
    if period is None:
        period = BillingPeriod.objects.create(
            organization=org, year=on_date.year, month=None)
    # Тот же вид, что берёт расчёт: второй вид с категорией «электроэнергия»
    # завести нельзя — get_or_create в расчёте упадёт на двух.
    charge_type = (ChargeType.objects
                   .filter(organization=org, category=ChargeType.TYPE_ELECTRICITY)
                   .order_by("pk").first())
    if charge_type is None:
        charge_type = ChargeType.objects.create(
            organization=org, category=ChargeType.TYPE_ELECTRICITY,
            name="Электроэнергия")
    note = f"Долг за электроэнергию на {on_date:%d.%m.%Y}, до добавления счётчика"
    if reading is not None:
        note += f" (показание {reading.normalize():f})"
    charge = Charge.objects.create(
        organization=org, period=period, plot=meter.plot,
        charge_type=charge_type, amount=amount, description=note,
    )
    # Если у участка уже лежит аванс за свет или общий — он гасит долг.
    spend_credit(meter.plot, user=user)
    return charge


class MeterReadingSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(
        source="submitted_by.get_full_name", read_only=True
    )
    meter_label = serializers.CharField(source="meter.__str__", read_only=True)
    # Эти два поля ждёт список показаний на фронте. Без них строка
    # рендерилась как «Сч. · Уч. —». default=None — у главного ввода
    # участка нет, обход meter.plot.number там упирается в None.
    meter_serial = serializers.CharField(
        source="meter.serial_number", read_only=True, default=None
    )
    plot_number = serializers.CharField(
        source="meter.plot.number", read_only=True, default=None
    )

    # Файл только принимается; наружу — признак и адрес в API с проверкой
    # прав, а не путь в открытой /media/.
    photo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    has_photo = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    def get_has_photo(self, obj):
        return bool(obj.photo)

    def get_photo_url(self, obj):
        # Путь относительно /api — как у всех запросов фронта.
        return f"/electricity/readings/{obj.pk}/photo/" if obj.photo else None

    class Meta:
        model = MeterReading
        exclude = ("organization",)
        # is_estimated ставит только расчёт. Иначе показание, введённое
        # руками, можно было бы объявить расчётным — и наоборот.
        read_only_fields = ("created_at", "updated_at", "submitted_by",
                            "is_estimated")

    def validate_meter(self, meter):
        request = self.context.get("request")
        _check_same_org(meter, request, "Счётчик")
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            from .views import own_meter_q, own_meters_only
            if own_meters_only(user) and not Meter.objects.filter(
                    own_meter_q(user), pk=meter.pk).exists():
                raise serializers.ValidationError("Счётчик не найден.")
        return meter


class CalculateElectricitySerializer(serializers.Serializer):
    """Запрос на расчёт электроэнергии за период."""
    billing_period_id = serializers.IntegerField()
    period_date = serializers.DateField(help_text="Дата окончания расчётного периода (последнее показание).")
