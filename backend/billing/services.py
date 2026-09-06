"""
Бизнес-логика billing: массовое создание начислений.
"""
from decimal import Decimal
from django.db import transaction
from .models import BillingPeriod, Charge, ChargeType
from members.models import Plot


def create_membership_charges(period: BillingPeriod, amount: Decimal, description: str = "") -> int:
    """
    Массово создаёт начисления членских взносов для всех активных участков периода.
    Возвращает количество созданных записей.
    """
    org = period.organization
    charge_type, _ = ChargeType.objects.get_or_create(
        organization=org,
        category=ChargeType.TYPE_MEMBERSHIP,
        defaults={"name": "Членский взнос"},
    )

    plots = Plot.objects.filter(
        organization=org,
        ownerships__date_to__isnull=True,  # только с текущим владельцем
    ).distinct()

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

    return len(charges)


def create_target_charges(period: BillingPeriod, charge_type: ChargeType,
                          amount: Decimal, plot_ids: list | None = None,
                          description: str = "") -> int:
    """
    Создаёт целевые взносы.
    plot_ids=None — для всех участков организации.
    """
    org = period.organization

    qs = Plot.objects.filter(organization=org)
    if plot_ids:
        qs = qs.filter(pk__in=plot_ids)

    charges = []
    for plot in qs:
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

    return len(charges)


def get_debt_summary(organization):
    """
    Возвращает список словарей с долгами по каждому участку.
    """
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    from django.db.models.functions import Coalesce

    plots = (
        Plot.objects.filter(organization=organization)
        .prefetch_related(
            "charges__payments",
            "ownerships__member",
        )
    )

    result = []
    for plot in plots:
        owner = plot.current_owner
        total_charged = Decimal("0")
        total_paid = Decimal("0")
        for charge in plot.charges.all():
            total_charged += charge.amount
            total_paid += charge.paid_amount
        debt = total_charged - total_paid
        result.append({
            "plot_id": plot.id,
            "plot_number": plot.number,
            "owner_name": owner.full_name if owner else "—",
            "total_charged": total_charged,
            "total_paid": total_paid,
            "debt": debt,
        })

    # Сортируем должников сначала
    result.sort(key=lambda x: x["debt"], reverse=True)
    return result
