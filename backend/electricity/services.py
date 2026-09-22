"""
Алгоритм расчёта электроэнергии с учётом потерь в сети.

Порядок расчёта за месяц:
1. Потребление каждого участка: расход_i = показание_тек - показание_пред
2. Потребление по главному вводу: V_main
3. Потери = V_main - Σ расход_i
4. Доля потерь участка: потери_i = потери × (расход_i / Σ расход_i)
5. Итог участка: итог_i = расход_i + потери_i
6. Сумма: сумма_i = итог_i × тариф

Показание «за период» — это показание, снятое ВНУТРИ периода. Раньше
брали просто последнее показание не позже даты расчёта, и у человека,
переставшего их сдавать, каждый месяц заново считалась одна и та же
старая разница: он платил за одни и те же киловатты столько месяцев,
сколько молчал, а когда наконец сдавал показание — ещё раз за всё
разом. Флаг missing_reading при этом не поднимался никогда, так что со
стороны это выглядело нормальным начислением.

Если показания за период нет, оно не пропускается, а достраивается
расчётным (MeterReading.is_estimated). Расчётное показание становится
основанием для следующего месяца, поэтому настоящее показание, пришедшее
через полгода, даёт разницу уже за вычетом начисленного — задвоения не
происходит. Если среднее оказалось завышенным и настоящее показание
ниже расчётного, переплата возвращается авансом на лицевой счёт участка.
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
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
    overpaid: Decimal = Decimal("0")   # возвращено авансом, ₽
    loss_basis: Decimal = Decimal("0")  # вес при распределении потерь


def _period_bounds(billing_period):
    """
    Границы расчётного периода: первый и последний день его месяца.

    Окно берётся из самого периода, а не из period_date, который
    передаёт вызывающий. Фронт, например, шлёт первое число месяца — и
    окно «с 1-го по 1-е» означало бы, что показание, сданное 20-го, за
    период не считается и человеку начислят по среднему. Месяц у
    периода один, ошибиться в нём нельзя, поэтому окно строим по нему.

    Из этого следует соглашение: показание относится к тому месяцу,
    которым оно датировано. Снимают показания за август — ставят дату
    августа, даже если записали их 3 сентября. Иначе август уйдёт в
    расчётные, а сентябрьская разница их потом зачтёт: деньги сойдутся,
    но месяц будет помечен расчётным зря.
    """
    import calendar
    from datetime import date

    year, month = billing_period.year, billing_period.month
    if not month:
        # Период без месяца — годовой: такие заводят под целевые взносы.
        # Свет по нему считать нельзя: показания, тариф и потери
        # помесячные, а окно в двенадцать месяцев дало бы одну разницу
        # за год и одно «среднее» вместо двенадцати.
        raise ValueError(
            "Электроэнергия считается помесячно. "
            f"У периода «{billing_period}» не указан месяц — "
            "заведите месячный расчётный период."
        )
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def calculate_electricity(organization, period_date, billing_period) -> list[PlotConsumption]:
    """
    Рассчитывает начисления за электроэнергию для всего СНТ за указанный период.

    period_date: дата для выбора тарифа. Окно, в котором ищутся
    показания, берётся не отсюда, а из самого billing_period — см.
    _period_bounds().
    billing_period: объект BillingPeriod для создания Charge.

    Возвращает список PlotConsumption. Charge создаются внутри функции.

    Повторный запуск за тот же период безопасен: начисления
    пересоздаются, расчётные показания за этот период заменяются. Но если
    показание за давно закрытый месяц пришло задним числом, пересчитать
    надо и все месяцы после него — расчётные показания следующих месяцев
    построены на предыдущих.
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
    # period_date отвечает только за выбор тарифа. Показания ищем и
    # расчётные проставляем по границам самого периода.
    start, as_of = _period_bounds(billing_period)

    # Главный ввод. Его показание расчётным не достраиваем: счётчик один,
    # снимает его правление, и выдуманная цифра здесь разъехалась бы по
    # всем участкам сразу. Нет показания за период — считаем, что потерь
    # к распределению нет, и говорим об этом в журнал.
    main_meter = Meter.objects.filter(organization=organization, is_main=True).first()
    main_consumption = Decimal("0")
    main_missing = False
    if main_meter:
        main_reading = _reading_in_period(main_meter, start, as_of)
        prev_main = _reading_before(main_meter, start)
        if main_reading and prev_main:
            main_consumption = max(main_reading.value - prev_main.value, Decimal("0"))
        else:
            main_missing = True
            logger.warning(
                "Главный ввод org=%s: нет показания за период %s — "
                "потери за этот месяц не распределяются.",
                organization.id, billing_period,
            )

    # Участки
    charge_type, _ = ChargeType.objects.get_or_create(
        organization=organization,
        category=ChargeType.TYPE_ELECTRICITY,
        defaults={"name": "Электроэнергия"},
    )

    plots = Plot.objects.filter(organization=organization).prefetch_related("meters")
    plot_results: list[PlotConsumption] = []
    estimated_rows = []   # (meter, значение) — дописываем после расчёта
    stale_estimates = []  # (meter, начало, конец) — расчётные, ставшие ненужными
    overpayments = []     # (plot, ₽) — вернуть авансом

    for plot in plots:
        # Счётчик берём из уже подтянутого prefetch-ем списка: .filter()
        # по нему сходил бы в базу на каждый участок и prefetch стал бы
        # бесполезен.
        meter = next((m for m in plot.meters.all() if not m.is_main), None)
        if not meter:
            continue

        current = _reading_in_period(meter, start, as_of)
        previous = _reading_before(meter, start)
        missing = current is None
        overpaid = Decimal("0")
        loss_basis = None      # None — значит «как расход»

        if current is not None:
            # Показание за период всё-таки пришло — расчётное за тот же
            # период больше не нужно. Если его оставить, следующий месяц
            # оттолкнётся от догадки, лежащей позже настоящего показания.
            stale_estimates.append((meter, start, as_of))

        if previous is None:
            # Первый месяц счётчика: сравнивать не с чем. Начислить
            # «всё показание целиком» нельзя — это показания с момента
            # установки, а не за месяц.
            consumption = Decimal("0")
            missing = current is None
        elif missing:
            consumption = _avg_consumption(meter, as_of, months=3)
            estimated_rows.append((meter, previous.value + consumption))
        elif previous.is_estimated:
            # Месяц сверки: человек молчал, ему считали по среднему, и
            # сейчас разница закрывает сразу несколько месяцев. К оплате
            # она верна, а вот весом при распределении потерь служить не
            # может — ни ноль (если среднее угадало), ни разница за
            # полгода не говорят, сколько он взял из сети именно в этом
            # месяце. Весом берём его же среднее.
            delta = current.value - previous.value
            loss_basis = _avg_consumption(meter, as_of, months=3)
            if delta < 0:
                consumption = Decimal("0")
                overpaid = (-delta * tariff).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if overpaid > 0:
                    overpayments.append((plot, overpaid, -delta))
            else:
                consumption = delta
        else:
            delta = current.value - previous.value
            if delta < 0:
                # Настоящее показание ниже расчётного: среднее было
                # завышено, человеку начислили лишнего. Молча обнулить
                # — значит оставить себе чужие деньги, поэтому разницу
                # возвращаем авансом на лицевой счёт участка.
                consumption = Decimal("0")
                overpaid = (-delta * tariff).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if overpaid > 0:
                    overpayments.append((plot, overpaid, -delta))
            else:
                consumption = delta

        if loss_basis is None:
            loss_basis = consumption

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
            overpaid=overpaid,
            loss_basis=loss_basis,
        ))

    # Распределяем потери
    # Размер потерь — строго «сколько зашло на ввод минус сколько
    # начислено участкам». Товарищество платит энергосбыту ровно по
    # главному вводу, и собрать оно должно ровно столько же: любая
    # другая формула означает дыру, которую закрывают членскими
    # взносами.
    #
    # А вот РАСПРЕДЕЛЯЮТСЯ потери по весам, а не по начисляемому
    # расходу. В месяц сверки у вернувшегося расход к начислению почти
    # ноль — всё уже взято по среднему, — и по расходу ему досталось бы
    # ноль потерь, а весь остаток упал бы на соседей.
    total_consumption = sum((r.consumption for r in plot_results), Decimal("0"))
    total_basis = sum((r.loss_basis for r in plot_results), Decimal("0"))
    losses = Decimal("0")
    if not main_missing:
        losses = max(main_consumption - total_consumption, Decimal("0"))

    if losses > 0 and total_basis <= 0:
        logger.warning(
            "org=%s период=%s: потери %.3f кВт·ч не на что распределить — "
            "ни у одного участка нет расхода. Начисления уйдут неполными.",
            organization.id, billing_period, losses,
        )

    for r in plot_results:
        if total_basis > 0:
            r.loss_share = (losses * r.loss_basis / total_basis).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )
        r.total_kwh = (r.consumption + r.loss_share).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
        r.amount = (r.total_kwh * tariff).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    with transaction.atomic():
        for meter, since, until in stale_estimates:
            MeterReading.objects.filter(
                meter=meter, date__gte=since, date__lte=until,
                is_estimated=True,
            ).delete()

        # Расчётные показания за этот период. Ставим их последним днём
        # месяца:
        # так следующий месяц оттолкнётся от них, а не от последнего
        # настоящего, и та же разница не начислится второй раз.
        for meter, value in estimated_rows:
            MeterReading.objects.update_or_create(
                meter=meter, date=as_of,
                defaults={
                    "organization": organization,
                    "value": value,
                    "is_estimated": True,
                    "notes": "Расчётное: показание за период не сдано",
                },
            )

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
            else:
                # Пересчёт дал ноль (например, показание пришло задним
                # числом и разница схлопнулась). Прошлое начисление за
                # этот месяц должно уйти — но только если по нему ещё
                # ничего не заплачено: трогать оплаченное нельзя.
                _drop_unpaid_charge(organization, billing_period, r.plot_id,
                                    charge_type)

        from billing.credits import sync_refund
        from billing.models import PlotCredit

        for plot, rubles, kwh in overpayments:
            sync_refund(
                plot, amount=rubles, date=as_of,
                period=billing_period,
                source=PlotCredit.SOURCE_ELECTRICITY,
                organization=organization,
                notes=(f"Возврат за свет: расчётное показание было выше "
                       f"настоящего на {kwh} кВт·ч"),
            )
            logger.info(
                "Участок %s: расчётные показания завышены на %s кВт·ч, "
                "возвращено авансом %s ₽",
                plot.number, kwh, rubles,
            )

    # После начисления за свет у заплативших вперёд появляется, во что
    # зачесть аванс.
    from billing.credits import spend_all_credits
    spend_all_credits(organization)

    missing_count = sum(1 for r in plot_results if r.missing_reading)
    logger.info(
        "Electricity calculated for org=%s period=%s: %d plots, "
        "losses=%.3f кВт·ч, без показаний %d",
        organization.id, billing_period, len(plot_results), losses, missing_count,
    )
    return plot_results


def _drop_unpaid_charge(organization, billing_period, plot_id, charge_type):
    from billing.models import Charge

    for charge in Charge.objects.filter(
        organization=organization, period=billing_period,
        plot_id=plot_id, charge_type=charge_type,
    ):
        if charge.paid_amount == 0:
            charge.delete()


def _reading_in_period(meter, start, as_of):
    """
    Показание, снятое внутри периода.

    Расчётные показания сюда не попадают: если за период уже
    достраивали среднее, а потом пришло настоящее показание, считать
    надо по настоящему. Иначе пересчёт месяца опирался бы на собственную
    же прошлую догадку.
    """
    from .models import MeterReading

    return (
        MeterReading.objects.filter(
            meter=meter, date__gte=start, date__lte=as_of,
            is_estimated=False,
        )
        .order_by("-date")
        .first()
    )


def _reading_before(meter, start):
    """
    Показание, от которого считаем: последнее до начала периода.

    Расчётные учитываются наравне с настоящими — в этом весь смысл:
    начисленное авансом по среднему уже уменьшило остаток, и следующий
    месяц должен считаться от него.
    """
    from .models import MeterReading

    return (
        MeterReading.objects.filter(meter=meter, date__lt=start)
        .order_by("-date")
        .first()
    )


def _avg_consumption(meter, as_of, months: int = 3) -> Decimal:
    """
    Среднее месячное потребление по последним снятым показаниям.

    Берём именно последние настоящие показания, а не окно «последние N
    месяцев»: у молчащего человека в окно ничего не попадает, среднее
    выходит нулевым, и его расход целиком уезжает в потери, то есть на
    соседей. Среднее по расчётным показаниям тоже не считаем — это было
    бы среднее из собственных догадок.
    """
    from .models import MeterReading

    readings = list(
        MeterReading.objects.filter(
            meter=meter, date__lte=as_of, is_estimated=False,
        ).order_by("-date")[: months + 1]
    )
    if len(readings) < 2:
        return Decimal("0")

    readings.reverse()
    total = readings[-1].value - readings[0].value
    days = (readings[-1].date - readings[0].date).days or 1
    monthly = total / days * 30
    return max(monthly, Decimal("0")).quantize(Decimal("0.001"))
