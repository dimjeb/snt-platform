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


def credit_balance(plot, category=None) -> Decimal:
    """
    Остаток аванса по участку.

    category=None — весь аванс; "" — только общий; "target" и т. п. —
    только деньги, которые ждут начислений этой категории.
    """
    rows = PlotCredit.objects.filter(plot=plot)
    if category is not None:
        rows = rows.filter(category=category)
    total = rows.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


def credit_buckets(plot) -> dict:
    """Остатки аванса участка по назначению: {"": общий, "target": …}."""
    rows = (PlotCredit.objects.filter(plot=plot)
            .values("category").annotate(total=Sum("amount")))
    return {r["category"]: r["total"] or Decimal("0") for r in rows}


def credit_balances(organization) -> dict:
    """
    Участки, где есть что тратить: {plot_id: сумма положительных корзин}.

    Смотрим корзины, а не общий итог: у участка может лежать целевой
    аванс при нулевом итоге, если общая корзина ушла в минус после
    исправления старой раскладки (см. fix_earmarked_statements).
    """
    rows = (
        PlotCredit.objects.filter(organization=organization)
        .values("plot_id", "category")
        .annotate(total=Sum("amount"))
    )
    result = {}
    for r in rows:
        total = r["total"] or Decimal("0")
        if total > 0:
            result[r["plot_id"]] = result.get(r["plot_id"], Decimal("0")) + total
    return result


def add_credit(plot, *, amount, date, organization=None, transaction_row=None,
               notes="", source=PlotCredit.SOURCE_STATEMENT, period=None,
               category=""):
    """
    Зачислить аванс.

    category — на что эти деньги. Целевой аванс гасит только целевые
    начисления и ждёт их, сколько потребуется; общий — любые.
    """
    amount = Decimal(amount)
    if amount <= 0:
        return None
    return PlotCredit.objects.create(
        organization=organization or plot.organization,
        plot=plot, date=date, amount=amount, source=source, period=period,
        transaction=transaction_row, notes=notes or "Переплата по выписке",
        category=category,
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

    Аванс лежит «корзинами» по назначению. Целевой гасит только целевые
    начисления, членский — только членские; общий — любые. Сначала
    тратятся корзины с назначением, потом общая: иначе общие деньги
    могли бы занять целевое начисление, и целевой аванс остался бы
    лежать без дела.

    Гасим от старых к новым — как и везде в проекте. За каждое списание
    создаётся и платёж (он уменьшает долг), и отрицательная строка ленты
    той же корзины (она уменьшает аванс), одной транзакцией: если уцелеет
    только одно из двух, деньги либо задвоятся, либо пропадут.
    """
    from django.utils import timezone

    today = today or timezone.localdate()
    buckets = credit_buckets(plot)
    order = sorted((c for c, total in buckets.items() if total > 0),
                   key=lambda c: c == "")

    spent = Decimal("0")
    touched = 0
    for category in order:
        balance = buckets[category]
        charges = (
            Charge.objects.filter(organization=plot.organization, plot=plot)
            .select_related("charge_type", "period")
            .prefetch_related("payments")
            .order_by("period__year", "period__month", "pk")
            .select_for_update(of=("self",))
        )
        if category:
            charges = charges.filter(charge_type__category=category)
        # Выборка заново для каждой корзины: платежи предыдущей корзины
        # в кэше prefetch не видны, и долг посчитался бы по устаревшим
        # данным — вышла бы переплата.
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
                plot=plot, date=today, amount=-take, category=category,
                charge=charge, payment=payment,
                notes=f"Зачтено в «{charge.charge_type.name}»",
            )
            balance -= take
            spent += take
            touched += 1

    if spent:
        log.info("Участок %s: зачтено из аванса %s ₽ на %s начислений",
                 plot.number, spent, touched)
    return {"spent": spent, "left": credit_balance(plot), "charges": touched}


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
