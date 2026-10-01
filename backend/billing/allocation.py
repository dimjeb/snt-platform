"""
Разнесение полученных денег по начислениям участка.

Одно правило на все способы приёма денег — банковскую выписку и деньги,
которые казначей принял сам. Раньше оно жило внутри проведения выписки,
и ручной ввод платежа шёл в обход: можно было закрыть начисление сверх
долга или положить целевые деньги в членский. Два места с одним
правилом рано или поздно расходятся — поэтому здесь одно.

Правило:
  * указано конкретное начисление — сначала в него;
  * указаны части по категориям — каждая часть в начисления своей
    категории, от старых к новым;
  * указана категория — только в начисления этой категории;
  * ничего не указано — по всем начислениям участка от старых к новым.
Деньги с назначением в чужую категорию не уходят никогда: не хватило
долга — остаток ложится авансом с тем же назначением и ждёт, пока
нужное начисление появится. Деньги без назначения сверх долга — общим
авансом.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from .credits import add_credit
from .models import Charge, Payment


@dataclass
class Allocation:
    paid: list = field(default_factory=list)          # [(Charge, сумма)]
    earmarked: dict = field(default_factory=dict)     # {категория: сумма авансом}
    advance: Decimal = Decimal("0")                   # общий аванс

    @property
    def paid_total(self):
        return sum((amount for _, amount in self.paid), Decimal("0"))

    @property
    def earmarked_total(self):
        return sum(self.earmarked.values(), Decimal("0"))


def allocate(plot, amount, *, date, payment_fields, credit_notes,
             category="", charge=None, parts=None, transaction_row=None):
    """
    Разнести amount ₽ по начислениям участка и вернуть, куда что легло.

    payment_fields — поля создаваемых платежей помимо начисления и суммы
    (method, external_ref, notes, recorded_by, bank_transaction).
    credit_notes — откуда деньги, для примечания к авансу.
    Вызывать внутри транзакции.
    """
    result = Allocation()
    charges = list(
        Charge.objects.filter(organization=plot.organization, plot=plot)
        .select_related("charge_type", "period")
        .prefetch_related("payments")
        .order_by("period__year", "period__month", "pk")
    )

    def pay(candidates, limit):
        spent = Decimal("0")
        for target in candidates:
            if spent >= limit:
                break
            debt = target.debt
            if debt <= 0:
                continue
            take = min(debt, limit - spent)
            Payment.objects.create(
                organization=plot.organization, charge=target, date=date,
                amount=take, **payment_fields,
            )
            # Платёж только что создан, а prefetch его не видит: сбрасываем
            # кэш, иначе следующая часть тех же денег посчитала бы долг
            # без него — и вышла бы переплата.
            getattr(target, "_prefetched_objects_cache", {}).pop("payments", None)
            result.paid.append((target, take))
            spent += take
        return spent

    def earmark(cat, value):
        if value > 0:
            result.earmarked[cat] = result.earmarked.get(cat, Decimal("0")) + value

    remaining = Decimal(amount)

    if charge is not None:
        # Конкретное начисление — из того же участка, иначе это чужой долг.
        chosen = next((c for c in charges if c.pk == charge.pk), None)
        if chosen is None:
            raise ValueError("Начисление не относится к этому участку.")
        got = pay([chosen], remaining)
        earmark(chosen.charge_type.category, remaining - got)
        remaining = Decimal("0")

    for part in parts or []:
        want = min(Decimal(part["amount"]), remaining)
        same = [c for c in charges if c.charge_type.category == part["category"]]
        earmark(part["category"], want - pay(same, want))
        remaining -= want

    if remaining > 0 and category:
        same = [c for c in charges if c.charge_type.category == category]
        earmark(category, remaining - pay(same, remaining))
        remaining = Decimal("0")
    elif remaining > 0:
        remaining -= pay(charges, remaining)

    from .statement_service import CATEGORY_LABELS

    for cat, value in result.earmarked.items():
        label = CATEGORY_LABELS.get(cat, cat)
        add_credit(plot, amount=value, date=date, organization=plot.organization,
                   transaction_row=transaction_row, category=cat,
                   notes=f"Ждёт начислений «{label}» — {credit_notes}")
    if remaining > 0:
        add_credit(plot, amount=remaining, date=date, organization=plot.organization,
                   transaction_row=transaction_row,
                   notes=f"Переплата — {credit_notes}")
        result.advance = remaining
    return result
