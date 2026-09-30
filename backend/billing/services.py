"""
Бизнес-логика billing: массовое создание начислений.
"""
from decimal import ROUND_HALF_UP, Decimal
from django.db import transaction
from django.db.models import Exists, OuterRef
from .credits import spend_all_credits
from .models import BillingPeriod, Charge, ChargeType
from members.models import Plot

# Как считается сумма взноса
BASIS_FLAT = "flat"              # одинаково на каждый участок
BASIS_PER_SOTKA = "per_sotka"    # ставка за сотку × площадь участка
BASIS_CHOICES = (BASIS_FLAT, BASIS_PER_SOTKA)

KOPEK = Decimal("0.01")


def _amount_for(plot, *, basis, amount, rate):
    """
    Сумма начисления для участка.

    Возвращает None, если начислять нечего: при расчёте по соткам у
    участка не заполнена площадь. Такой участок пропускается, а его
    номер возвращается вызывающему — молча не начислить нельзя,
    казначей будет уверен, что охватил всех.
    """
    if basis != BASIS_PER_SOTKA:
        return amount
    area = plot.area_sotok
    if area is None or area <= 0:
        return None
    # Округляем каждое начисление до копейки по правилу «половина вверх»:
    # 1200 ₽ × 6.33 сотки = 7596.00, а 1200 × 6.335 = 7602.00, и банк
    # с долями копеек работать не умеет.
    return (Decimal(rate) * area).quantize(KOPEK, rounding=ROUND_HALF_UP)


def _penalty_fields(due_date, penalty_percent):
    """
    Срок оплаты и ставка пеней для создаваемого начисления.

    Ставку не передаём вовсе, если её не указали: у поля есть значение
    по умолчанию (20 %), и подставлять сюда None значило бы затереть
    его на NULL, а потом получить падение при расчёте пеней.
    """
    fields = {"due_date": due_date}
    if penalty_percent is not None:
        fields["penalty_percent"] = penalty_percent
    return fields


def _auto_description(basis, rate, plot):
    """Расшифровка расчёта, если казначей не написал своё описание."""
    if basis != BASIS_PER_SOTKA:
        return ""
    return f"{rate} ₽ за сотку × {plot.area_sotok} сот."


def create_membership_charges(period: BillingPeriod, amount: Decimal = None,
                              description: str = "",
                              basis: str = BASIS_FLAT,
                              rate: Decimal = None,
                              due_date=None,
                              penalty_percent: Decimal = None) -> dict:
    """
    Массово создаёт начисления членских взносов для всех активных участков периода.

    basis="flat" — amount на каждый участок;
    basis="per_sotka" — rate ₽ за сотку × площадь участка.

    Возвращает {"created": сколько создано, "skipped_no_owner": [номера],
    "skipped_no_area": [номера]}.
    Участки без текущего собственника пропускаются — начислять некому, —
    но молчать об этом нельзя: казначей уверен, что начислил всем, а
    часть участков осталась без взноса. Так же и с участками без
    заполненной площади при расчёте по соткам.
    """
    org = period.organization
    charge_type, _ = ChargeType.objects.get_or_create(
        organization=org,
        category=ChargeType.TYPE_MEMBERSHIP,
        defaults={"name": "Членский взнос"},
    )

    # Именно Exists, а не filter(ownerships__date_to__isnull=True):
    # обращение к обратной связи через __isnull=True Django переводит в
    # LEFT OUTER JOIN, и участок, у которого строк владения НЕТ ВООБЩЕ,
    # попадает в выборку «только с текущим владельцем» — date_to у него
    # NULL просто потому, что приджойнить нечего. Такому участку
    # начислялся членский взнос, и начисление не появлялось ни в одном
    # личном кабинете: показывать его некому.
    from members.models import PlotOwnership

    has_owner = PlotOwnership.objects.filter(
        plot=OuterRef("pk"), date_to__isnull=True,
    )
    plots = Plot.objects.filter(organization=org).filter(Exists(has_owner))

    skipped = list(
        Plot.objects.filter(organization=org)
        .exclude(pk__in=plots.values("pk"))
        .order_by("number")
        .values_list("number", flat=True)
    )

    charges = []
    no_area = []
    for plot in plots:
        plot_amount = _amount_for(plot, basis=basis, amount=amount, rate=rate)
        if plot_amount is None:
            no_area.append(plot.number)
            continue
        # Не дублировать, если уже есть
        if not Charge.objects.filter(period=period, plot=plot, charge_type=charge_type).exists():
            charges.append(
                Charge(
                    organization=org,
                    period=period,
                    plot=plot,
                    charge_type=charge_type,
                    amount=plot_amount,
                    description=description or _auto_description(basis, rate, plot),
                    **_penalty_fields(due_date, penalty_percent),
                )
            )

    with transaction.atomic():
        Charge.objects.bulk_create(charges)
        # Именно сейчас у заплативших вперёд появилось, во что зачесть
        # аванс. Если этого не сделать, человек увидит долг при том, что
        # деньги товарищество уже получило.
        spend_all_credits(org)

    return {"created": len(charges), "skipped_no_owner": skipped,
            "skipped_no_area": sorted(no_area)}


def create_target_charges(period: BillingPeriod, charge_type: ChargeType,
                          amount: Decimal = None, plot_ids: list | None = None,
                          description: str = "",
                          basis: str = BASIS_FLAT,
                          rate: Decimal = None,
                          due_date=None,
                          penalty_percent: Decimal = None) -> dict:
    """
    Создаёт целевые взносы.
    plot_ids=None — для всех участков организации.

    basis="flat" — amount на каждый участок;
    basis="per_sotka" — rate ₽ за сотку × площадь участка.

    Возвращает {"created": сколько создано, "no_owner": [номера],
    "skipped_no_area": [номера]}.
    В отличие от членских, целевой взнос начисляется и на участок без
    текущего собственника: он может быть решением общего собрания по
    всем участкам, включая заброшенные. Но такое начисление ни в одном
    личном кабинете не появится — показывать его некому, — поэтому
    номера таких участков возвращаются отдельно.
    """
    org = period.organization

    qs = Plot.objects.filter(organization=org).prefetch_related("ownerships")
    if plot_ids:
        qs = qs.filter(pk__in=plot_ids)

    charges = []
    no_owner = []
    no_area = []
    for plot in qs:
        plot_amount = _amount_for(plot, basis=basis, amount=amount, rate=rate)
        if plot_amount is None:
            no_area.append(plot.number)
            continue
        if not any(o.date_to is None for o in plot.ownerships.all()):
            no_owner.append(plot.number)
        if not Charge.objects.filter(period=period, plot=plot, charge_type=charge_type).exists():
            charges.append(
                Charge(
                    organization=org,
                    period=period,
                    plot=plot,
                    charge_type=charge_type,
                    amount=plot_amount,
                    description=description or _auto_description(basis, rate, plot),
                    **_penalty_fields(due_date, penalty_percent),
                )
            )

    with transaction.atomic():
        Charge.objects.bulk_create(charges)
        # Именно сейчас у заплативших вперёд появилось, во что зачесть
        # аванс. Если этого не сделать, человек увидит долг при том, что
        # деньги товарищество уже получило.
        spend_all_credits(org)

    return {"created": len(charges), "no_owner": sorted(no_owner),
            "skipped_no_area": sorted(no_area)}


def apply_penalties(organization, *, today=None, user=None) -> dict:
    """
    Начислить пени по просроченным начислениям.

    Пени начисляются **однократно** на каждое начисление и считаются от
    остатка долга на момент запуска, а не от полной суммы: заплатил
    половину до срока — пени только на вторую половину, заплатил всё —
    пеней нет вовсе.

    Повторный запуск ничего не задваивает: начисление пеней связано с
    исходным через OneToOne, и вторую строку база не даст создать. Это
    важнее, чем кажется: команду ставят в cron, и однажды она
    отработает дважды.

    Начисление, срок которого прошёл, но долг уже закрыт, пропускается
    и **остаётся без пометки** — если человек заплатил после срока, но
    до запуска команды, пеней он не получит. Так сделано намеренно:
    наказывать за задержку, которую товарищество не заметило, нечестно.
    Чтобы пени были предсказуемыми, команду надо гонять по расписанию,
    раз в сутки.
    """
    from django.utils import timezone

    today = today or timezone.localdate()

    overdue = (
        Charge.objects.filter(organization=organization, due_date__lt=today)
        .exclude(charge_type__category=ChargeType.TYPE_PENALTY)
        .filter(penalty__isnull=True)
        .select_related("charge_type", "period", "plot")
        .prefetch_related("payments")
        .order_by("plot__number", "pk")
    )

    charge_type = None
    created, total = [], Decimal("0")

    for charge in overdue:
        debt = charge.debt
        if debt <= 0:
            continue
        percent = charge.penalty_percent or Decimal("0")
        if percent <= 0:
            continue
        amount = (debt * percent / Decimal("100")).quantize(
            KOPEK, rounding=ROUND_HALF_UP
        )
        if amount <= 0:
            # Долг в копейку: 20 % от него округляются в ноль. Строку на
            # ноль рублей не заводим — она только мусорит квитанцию.
            continue

        if charge_type is None:
            charge_type, _ = ChargeType.objects.get_or_create(
                organization=organization,
                category=ChargeType.TYPE_PENALTY,
                defaults={"name": "Пени за просрочку"},
            )

        # normalize() + формат «f»: у Decimal «:g» не убирает хвостовые
        # нули, и в квитанции стояло бы «Пени 20.00 %». Так получается
        # «20 %», а дробная ставка вроде 7.5 % сохраняется.
        percent_text = f"{percent.normalize():f}"
        created.append(Charge(
            organization=organization,
            period=charge.period,
            plot=charge.plot,
            charge_type=charge_type,
            amount=amount,
            penalty_for=charge,
            description=(
                f"Пени {percent_text} % за просрочку: "
                f"«{charge.charge_type.name}», срок {charge.due_date:%d.%m.%Y}, "
                f"долг на {today:%d.%m.%Y} — {debt} ₽"
            )[:500],
        ))
        total += amount

    with transaction.atomic():
        Charge.objects.bulk_create(created)
        # Пени — такой же долг, как остальные, и аванс должен их гасить.
        spend_all_credits(organization, user=user)

    return {"created": len(created), "total": total}


def get_debt_summary(organization, period=None):
    """
    Возвращает список словарей с долгами по каждому участку.

    period — если задан, учитываются только начисления этого расчётного
    периода. Без него сводка идёт по всем начислениям организации:
    так её вызывает генератор отчётов (reports/generators.py).
    """
    from django.db.models import Prefetch

    charges_qs = Charge.objects.prefetch_related("payments")
    if period is not None:
        charges_qs = charges_qs.filter(period=period)

    plots = (
        Plot.objects.filter(organization=organization)
        .prefetch_related(
            Prefetch("charges", queryset=charges_qs),
            "ownerships__member",
        )
    )

    result = []
    for plot in plots:
        owners = plot.current_owners
        total_charged = Decimal("0")
        total_paid = Decimal("0")
        for charge in plot.charges.all():
            total_charged += charge.amount
            total_paid += charge.paid_amount
        debt = total_charged - total_paid
        result.append({
            "plot_id": plot.id,
            "plot_number": plot.number,
            # Участок в общей собственности — в отчёте должны стоять все,
            # иначе счёт уходит одному, а спрашивают со второго.
            "owner_name": ", ".join(o.full_name for o in owners) or "—",
            "total_charged": total_charged,
            "total_paid": total_paid,
            "debt": debt,
        })

    # Сортируем должников сначала
    result.sort(key=lambda x: x["debt"], reverse=True)
    return result
