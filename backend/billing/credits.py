"""
Аванс: деньги, поступившие сверх начислений.

Садоводы нередко платят вперёд за сезон, а начисления появляются
позже. Такие деньги нельзя ни потерять, ни зачислить в чужой долг:
они лежат на лицевом счёте участка и расходуются на его начисления по
мере их появления.

Остаток считается как сумма ленты движений, отдельного поля с балансом
нет: рассинхронизация ленты и поля — классический источник расхождений
в учёте денег, а лишний SUM по паре строк ничего не стоит.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import Charge, Payment, PlotCredit

log = logging.getLogger(__name__)


def credit_balance(plot) -> Decimal:
    """Остаток аванса по участку."""
    total = PlotCredit.objects.filter(plot=plot).aggregate(
        total=Sum("amount")
    )["total"]
    return total or Decimal("0")


def credit_balances(organization) -> dict:
    """Остатки авансов по всем участкам организации: {plot_id: сумма}."""
    rows = (
        PlotCredit.objects.filter(organization=organization)
        .values("plot_id")
        .annotate(total=Sum("amount"))
    )
    return {r["plot_id"]: r["total"] or Decimal("0") for r in rows
            if (r["total"] or 0) != 0}


def add_credit(plot, *, amount, date, organization=None, transaction_row=None,
               notes="", source=PlotCredit.SOURCE_STATEMENT, period=None):
    """Зачислить аванс."""
    amount = Decimal(amount)
    if amount <= 0:
        return None
    return PlotCredit.objects.create(
        organization=organization or plot.organization,
        plot=plot, date=date, amount=amount, source=source, period=period,
        transaction=transaction_row, notes=notes or "Переплата по выписке",
    )


def sync_refund(plot, *, amount, date, period, source, organization=None,
                notes=""):
    """
    Выставить возврат по участку за период ровно на указанную сумму.

    Расчёт можно запустить за один и тот же месяц повторно, и возврат
    не должен выписываться заново: иначе каждый пересчёт дарил бы
    человеку ещё столько же. Просто удалить прошлую строку тоже нельзя —
    её уже могли зачесть в долг, и тогда пропала бы только половина
    проводки. Поэтому доначисляем разницу: лента остаётся правдивой,
    а итог сходится с текущим расчётом.
    """
    amount = Decimal(amount)
    # Считаем все строки возврата за этот период — и первую, и
    # поправочные. Строки расходования аванса сюда не попадают: у них
    # period пуст, а источник свой.
    already = PlotCredit.objects.filter(
        plot=plot, period=period, source=source,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    delta = amount - already
    if delta == 0:
        return None
    return PlotCredit.objects.create(
        organization=organization or plot.organization,
        plot=plot, date=date, amount=delta, source=source, period=period,
        notes=notes or "Возврат",
    )


@transaction.atomic
def spend_credit(plot, *, user=None, today=None):
    """
    Пустить аванс участка на его непогашенные начисления.

    Гасим от старых к новым — как и везде в проекте. За каждое списание
    создаётся и платёж (он уменьшает долг), и отрицательная строка ленты
    (она уменьшает аванс), одной транзакцией: если уцелеет только одно
    из двух, деньги либо задвоятся, либо пропадут.
    """
    from django.utils import timezone

    balance = credit_balance(plot)
    if balance <= 0:
        return {"spent": Decimal("0"), "left": balance, "charges": 0}

    today = today or timezone.localdate()
    charges = (
        Charge.objects.filter(organization=plot.organization, plot=plot)
        .select_related("charge_type", "period")
        .prefetch_related("payments")
        .order_by("period__year", "period__month", "pk")
        .select_for_update()
    )

    spent = Decimal("0")
    touched = 0
    for charge in charges:
        if balance <= 0:
            break
        debt = charge.debt
        if debt <= 0:
            continue
        take = min(debt, balance)

        payment = Payment.objects.create(
            organization=plot.organization,
            charge=charge, date=today, amount=take,
            method=Payment.METHOD_BANK,
            notes="Зачтено из аванса",
            recorded_by=user,
        )
        PlotCredit.objects.create(
            organization=plot.organization,
            plot=plot, date=today, amount=-take,
            charge=charge, payment=payment,
            notes=f"Зачтено в «{charge.charge_type.name}»",
        )
        balance -= take
        spent += take
        touched += 1

    if spent:
        log.info("Участок %s: зачтено из аванса %s ₽ на %s начислений",
                 plot.number, spent, touched)
    return {"spent": spent, "left": balance, "charges": touched}


def spend_all_credits(organization, *, user=None):
    """
    Зачесть авансы по всем участкам, где они есть.

    Вызывается после массового начисления: именно в этот момент у людей,
    заплативших вперёд, появляется то, во что аванс можно зачесть.
    """
    from members.models import Plot

    balances = credit_balances(organization)
    if not balances:
        return {"plots": 0, "spent": Decimal("0")}

    plots = Plot.objects.filter(pk__in=balances.keys())
    total = Decimal("0")
    touched = 0
    for plot in plots:
        result = spend_credit(plot, user=user)
        if result["spent"]:
            total += result["spent"]
            touched += 1
    return {"plots": touched, "spent": total}
