"""
Бизнес-логика billing: массовое создание начислений.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Exists, OuterRef
from .credits import spend_all_credits
from .models import BillingPeriod, Charge, ChargeType
from members.models import Plot


def create_membership_charges(period: BillingPeriod, amount: Decimal,
                              description: str = "") -> dict:
    """
    Массово создаёт начисления членских взносов для всех активных участков периода.

    Возвращает {"created": сколько создано, "skipped_no_owner": [номера]}.
    Участки без текущего собственника пропускаются — начислять некому, —
    но молчать об этом нельзя: казначей уверен, что начислил всем, а
    часть участков осталась без взноса.
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
    for plot in plots:
        # Не дублировать, если уже есть
        if not Charge.objects.filter(period=period, plot=plot, charge_type=charge_type).exists():
            charges.append(
                Charge(
                    organization=org,
                    period=period,
                    plot=plot,
                    charge_type=charge_type,
                    amount=amount,
                    description=description,
                )
            )

    with transaction.atomic():
        Charge.objects.bulk_create(charges)
        # Именно сейчас у заплативших вперёд появилось, во что зачесть
        # аванс. Если этого не сделать, человек увидит долг при том, что
        # деньги товарищество уже получило.
        spend_all_credits(org)

    return {"created": len(charges), "skipped_no_owner": skipped}


def create_target_charges(period: BillingPeriod, charge_type: ChargeType,
                          amount: Decimal, plot_ids: list | None = None,
                          description: str = "") -> dict:
    """
    Создаёт целевые взносы.
    plot_ids=None — для всех участков организации.

    Возвращает {"created": сколько создано, "no_owner": [номера]}.
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
    for plot in qs:
        if not any(o.date_to is None for o in plot.ownerships.all()):
            no_owner.append(plot.number)
        if not Charge.objects.filter(period=period, plot=plot, charge_type=charge_type).exists():
            charges.append(
                Charge(
                    organization=org,
                    period=period,
                    plot=plot,
                    charge_type=charge_type,
                    amount=amount,
                    description=description,
                )
            )

    with transaction.atomic():
        Charge.objects.bulk_create(charges)
        # Именно сейчас у заплативших вперёд появилось, во что зачесть
        # аванс. Если этого не сделать, человек увидит долг при том, что
        # деньги товарищество уже получило.
        spend_all_credits(org)

    return {"created": len(charges), "no_owner": sorted(no_owner)}


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
