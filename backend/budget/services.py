"""
Расчёты по смете: размер взноса и исполнение.

База для взноса — те же участки, по которым потом пойдёт начисление
(create_membership_charges): с текущим собственником. Иначе ставка,
посчитанная здесь, разошлась бы с тем, что соберётся на деле.
"""
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from django.db.models import Exists, OuterRef, Sum

KOPEK = Decimal("0.01")
ZERO = Decimal("0")


def fee_base(org):
    """Участки с собственником: сколько их и сколько у них соток."""
    from members.models import Plot, PlotOwnership

    has_owner = PlotOwnership.objects.filter(plot=OuterRef("pk"), date_to__isnull=True)
    plots = list(Plot.objects.filter(organization=org).filter(Exists(has_owner))
                 .values("number", "area_sotok"))
    with_area = [p for p in plots if p["area_sotok"]]
    return {
        "plots": len(plots),
        "area": sum((p["area_sotok"] for p in with_area), ZERO),
        "plots_with_area": len(with_area),
        "areas": [p["area_sotok"] for p in with_area],
    }


def _ceil(value):
    return value.quantize(KOPEK, rounding=ROUND_CEILING)


def fee_calc(budget):
    """
    Размер членского взноса по смете и что он соберёт.

    Ставка округляется ВВЕРХ до копейки: округление вниз гарантирует
    недобор, а смета утверждается как сумма, которую нужно собрать.
    Сколько выйдет сверху из-за округления — показывается.
    """
    from .models import Budget, BudgetItem

    items = list(budget.items.all())
    membership = sum((i.amount for i in items
                      if i.section == BudgetItem.SECTION_MEMBERSHIP), ZERO)
    target_items = [i for i in items if i.section == BudgetItem.SECTION_TARGET]
    base = fee_base(budget.organization)
    warnings = []

    rate = None
    collected = None
    if budget.basis == Budget.BASIS_PER_SOTKA:
        if base["area"] > 0:
            rate = _ceil(membership / base["area"])
            collected = sum(((rate * a).quantize(KOPEK, rounding=ROUND_HALF_UP)
                             for a in base["areas"]), ZERO)
        missing = base["plots"] - base["plots_with_area"]
        if missing:
            warnings.append(f"У {missing} участков не указана площадь — взнос "
                            "по соткам им не начислится. Заполните площадь в реестре.")
    else:
        if base["plots"]:
            rate = _ceil(membership / base["plots"])
            collected = rate * base["plots"]
    if not base["plots"]:
        warnings.append("В реестре нет участков с собственником — делить смету "
                        "не на кого. Сначала загрузите реестр членов.")

    targets = []
    for item in target_items:
        per_plot = _ceil(item.amount / base["plots"]) if base["plots"] else None
        targets.append({"id": item.pk, "name": item.name, "amount": item.amount,
                        "per_plot": per_plot})

    return {
        "membership_total": membership,
        "target_total": sum((t["amount"] for t in targets), ZERO),
        "basis": budget.basis,
        "plots": base["plots"],
        "area": base["area"],
        "plots_with_area": base["plots_with_area"],
        "rate": rate,
        "collected": collected,
        "rounding_surplus": (collected - membership) if collected is not None else None,
        "targets": targets,
        "warnings": warnings,
    }


def execution(budget):
    """
    Исполнение сметы за год: план и факт по статьям, доходы — начислено и
    поступило по членским и целевым взносам года.
    """
    from billing.models import Charge, ChargeType, Payment

    from .models import Expense

    org = budget.organization
    year = budget.year
    facts = dict(
        Expense.objects.filter(organization=org, item__budget=budget)
        .values("item").annotate(s=Sum("amount")).values_list("item", "s"))
    rows = []
    for item in budget.items.all():
        fact = facts.get(item.pk) or ZERO
        rows.append({
            "id": item.pk, "section": item.section, "name": item.name,
            "plan": item.amount, "fact": fact, "diff": item.amount - fact,
            "percent": (fact * 100 / item.amount).quantize(Decimal("0.1"))
            if item.amount else None,
        })
    outside = (Expense.objects.filter(organization=org, date__year=year)
               .exclude(item__budget=budget).aggregate(s=Sum("amount"))["s"] or ZERO)

    income = []
    for category, label in ((ChargeType.TYPE_MEMBERSHIP, "Членские взносы"),
                            (ChargeType.TYPE_TARGET, "Целевые взносы")):
        charges = Charge.objects.filter(organization=org, period__year=year,
                                        charge_type__category=category)
        charged = charges.aggregate(s=Sum("amount"))["s"] or ZERO
        paid = (Payment.objects.filter(charge__in=charges, is_cancelled=False)
                .aggregate(s=Sum("amount"))["s"] or ZERO)
        income.append({"category": category, "name": label, "charged": charged,
                       "paid": paid, "debt": charged - paid})

    plan_total = sum((r["plan"] for r in rows), ZERO)
    fact_total = sum((r["fact"] for r in rows), ZERO)
    return {"rows": rows, "plan_total": plan_total, "fact_total": fact_total,
            "outside_budget": outside, "income": income}


def item_amount(quantity, unit_price, amount):
    """Сумма статьи: количество × цена, если оба заданы, иначе как ввели."""
    if quantity is not None and unit_price is not None:
        return (quantity * unit_price).quantize(KOPEK, rounding=ROUND_HALF_UP)
    return amount


def copy_items(source, target):
    """Перенести статьи прошлогодней сметы в новую — как черновик."""
    from .models import BudgetItem

    BudgetItem.objects.bulk_create([
        BudgetItem(organization=target.organization, budget=target,
                   section=i.section, name=i.name, quantity=i.quantity,
                   unit=i.unit, unit_price=i.unit_price, amount=i.amount,
                   justification=i.justification, position=i.position)
        for i in source.items.all()
    ])


def as_json(value):
    """Деньги в ответ API — строкой, как у остальных полей: float теряет копейки."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: as_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_json(v) for v in value]
    return value
