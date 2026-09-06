"""
Алгоритм расчёта электроэнергии с учётом потерь в сети.

Порядок расчёта за месяц:
1. Потребление каждого участка: расход_i = показание_тек - показание_пред
2. Потребление по главному вводу: V_main
3. Потери = V_main - Σ расход_i
4. Доля потерь участка: потери_i = потери × (расход_i / Σ расход_i)
5. Итог участка: итог_i = расход_i + потери_i
6. Сумма: сумма_i = итог_i × тариф
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PlotConsumption:
    plot_id: int
    plot_number: str
    meter_id: int
    consumption: Decimal       # кВт·ч без потерь
    loss_share: Decimal        # доля потерь
    total_kwh: Decimal         # итоговое потребление
    tariff: Decimal            # руб./кВт·ч
    amount: Decimal            # сумма к оплате
    missing_reading: bool      # нет показания за период


def calculate_electricity(organization, period_date, billing_period) -> list[PlotConsumption]:
    """
    Рассчитывает начисления за электроэнергию для всего СНТ за указанный период.

    period_date: дата, за которую берём «текущее» показание (обычно последний день месяца).
    billing_period: объект BillingPeriod для создания Charge.

    Возвращает список PlotConsumption. Charge создаются внутри функции.
    """
    from .models import Meter, MeterReading, EnergyTariff
    from billing.models import Charge, ChargeType
    from members.models import Plot
    from django.db import transaction

    # Получаем актуальный тариф
    tariff_obj = (
        EnergyTariff.objects.filter(
            organization=organization,
            valid_from__lte=period_date,
        )
        .order_by("-valid_from")
        .first()
    )
    if not tariff_obj:
        raise ValueError("Не найден тариф на электроэнергию для данного периода.")

    tariff = tariff_obj.price_per_kwh

    # Главный ввод
    main_meter = Meter.objects.filter(organization=organization, is_main=True).first()
    main_consumption = Decimal("0")
    if main_meter:
        main_reading = _get_reading(main_meter, period_date)
        prev_main = _get_prev_reading(main_meter, period_date)
        if main_reading and prev_main:
            main_consumption = main_reading.value - prev_main.value

    # Участки
    charge_type, _ = ChargeType.objects.get_or_create(
        organization=organization,
        category=ChargeType.TYPE_ELECTRICITY,
        defaults={"name": "Электроэнергия"},
    )

    plots = Plot.objects.filter(organization=organization).prefetch_related("meters")
    plot_results: list[PlotConsumption] = []

    for plot in plots:
        meter = plot.meters.filter(is_main=False).first()
        if not meter:
            continue

        current = _get_reading(meter, period_date)
        previous = _get_prev_reading(meter, period_date)
        missing = not (current and previous)

        if missing:
            # Используем среднее за последние 3 месяца как временную меру
            consumption = _avg_consumption(meter, period_date, months=3)
        else:
            consumption = max(current.value - previous.value, Decimal("0"))

        plot_results.append(PlotConsumption(
            plot_id=plot.id,
            plot_number=plot.number,
            meter_id=meter.id,
            consumption=consumption,
            loss_share=Decimal("0"),
            total_kwh=consumption,
            tariff=tariff,
            amount=Decimal("0"),
            missing_reading=missing,
        ))

    # Распределяем потери
    total_consumption = sum(r.consumption for r in plot_results)
    losses = max(main_consumption - total_consumption, Decimal("0"))

    for r in plot_results:
        if total_consumption > 0:
            r.loss_share = (losses * r.consumption / total_consumption).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )
        r.total_kwh = (r.consumption + r.loss_share).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
        r.amount = (r.total_kwh * tariff).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # Создаём Charge
    with transaction.atomic():
        for r in plot_results:
            if r.amount > 0:
                Charge.objects.update_or_create(
                    organization=organization,
                    period=billing_period,
                    plot_id=r.plot_id,
                    charge_type=charge_type,
                    defaults={
                        "amount": r.amount,
                        "kwh": r.total_kwh,
                        "tariff": tariff,
                        "description": (
                            f"{r.total_kwh} кВт·ч × {tariff} руб."
                            + (" [расч. среднее]" if r.missing_reading else "")
                        ),
                    },
                )

    logger.info(
        "Electricity calculated for org=%s period=%s: %d plots, losses=%.3f кВт·ч",
        organization.id, billing_period, len(plot_results), losses,
    )
    return plot_results


def _get_reading(meter, period_date):
    from .models import MeterReading
    return (
        MeterReading.objects.filter(meter=meter, date__lte=period_date)
        .order_by("-date")
        .first()
    )


def _get_prev_reading(meter, period_date):
    from .models import MeterReading
    current = _get_reading(meter, period_date)
    if not current:
        return None
    return (
        MeterReading.objects.filter(meter=meter, date__lt=current.date)
        .order_by("-date")
        .first()
    )


def _avg_consumption(meter, period_date, months: int = 3) -> Decimal:
    """Среднее потребление за последние N месяцев."""
    from .models import MeterReading
    from datetime import timedelta

    cutoff = period_date - timedelta(days=30 * months)
    readings = list(
        MeterReading.objects.filter(
            meter=meter, date__gte=cutoff, date__lte=period_date
        ).order_by("date")
    )
    if len(readings) < 2:
        return Decimal("0")

    total = readings[-1].value - readings[0].value
    days = (readings[-1].date - readings[0].date).days or 1
    monthly = total / days * 30
    return max(monthly, Decimal("0")).quantize(Decimal("0.001"))
