"""
Главная правления: короткая сводка и список «что сделать сейчас».

Главная должна отвечать не на «сколько у нас участков», а на «что мне
сегодня сделать»: кто просрочил, что лежит непроведённым в выписке, кто
не сдал показания, утверждена ли смета. Каждый пункт ведёт туда, где
это решается.

Долг считается по ВСЕМ начислениям, а не по одному открытому периоду,
как было раньше на главной: иначе долг за прошлый год с главной пропадал.
"""
import datetime as dt
from decimal import Decimal

from django.db.models import DecimalField, Exists, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

ZERO = Decimal("0")
MONEY = DecimalField(max_digits=14, decimal_places=2)


def _charges_with_paid(org):
    from .models import Charge

    return Charge.objects.filter(organization=org).annotate(
        paid=Coalesce(Sum("payments__amount",
                          filter=Q(payments__is_cancelled=False)),
                      Value(ZERO), output_field=MONEY))


def _money(value):
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def _plural(n, one, few, many):
    n = abs(n) % 100
    if 11 <= n <= 19:
        return many
    n %= 10
    return one if n == 1 else few if 2 <= n <= 4 else many


def build_dashboard(org, today=None):
    from budget.models import Budget
    from electricity.models import Meter, MeterReading
    from members.models import Member, Plot, PlotOwnership

    from .models import BankTransaction, Charge, ChargeType, Payment, PlotCredit

    today = today or timezone.localdate()
    todo = []

    # ── долги ──
    has_penalty = Charge.objects.filter(penalty_for=OuterRef("pk"))
    open_charges = [c for c in _charges_with_paid(org)
                    .annotate(has_penalty=Exists(has_penalty))
                    .select_related("charge_type") if c.amount > c.paid]
    total_debt = sum((c.amount - c.paid for c in open_charges), ZERO)
    debtors = len({c.plot_id for c in open_charges})

    overdue = [c for c in open_charges if c.due_date and c.due_date < today]
    if overdue:
        n = len({c.plot_id for c in overdue})
        amount = sum((c.amount - c.paid for c in overdue), ZERO)
        no_penalty = [c for c in overdue
                      if c.charge_type.category != ChargeType.TYPE_PENALTY
                      and not c.has_penalty]
        detail = f"Долг по ним — {_money(amount)}."
        if no_penalty:
            detail += " Пени по ним ещё не начислены."
        todo.append({
            "key": "overdue", "level": "attention",
            "title": f"{n} {_plural(n, 'участок просрочил', 'участка просрочили', 'участков просрочили')} оплату",
            "detail": detail, "action": "Открыть долги", "to": "/billing",
        })

    # ── выписка ──
    fresh = BankTransaction.objects.filter(organization=org,
                                           status=BankTransaction.STATUS_NEW)
    n_fresh = fresh.count()
    if n_fresh:
        n_unknown = fresh.filter(plot__isnull=True).count()
        detail = f"На {_money(fresh.aggregate(s=Sum('amount'))['s'] or ZERO)}."
        if n_fresh - n_unknown:
            detail += (f" {n_fresh - n_unknown} можно провести сразу — "
                       "участок известен.")
        if n_unknown:
            detail += (f" У {n_unknown} {_plural(n_unknown, 'строки', 'строк', 'строк')} "
                       "участок не определился — укажите его или пропустите строку, "
                       "если это не взнос.")
        # Сразу в ту выписку, где ждут строки (самую старую из таких), —
        # иначе непонятно, какую из загруженных открывать.
        oldest = fresh.order_by("statement__created_at").values_list(
            "statement_id", flat=True).first()
        todo.append({
            "key": "statement", "level": "attention",
            "title": f"В выписке {n_fresh} {_plural(n_fresh, 'непроведённая строка', 'непроведённые строки', 'непроведённых строк')}",
            "detail": detail, "action": "Провести выписку",
            "to": f"/statements?open={oldest}",
        })

    # ── показания за прошлый месяц ──
    first_this = today.replace(day=1)
    last_month_end = first_this - dt.timedelta(days=1)
    month_start = last_month_end.replace(day=1)
    meters = Meter.objects.filter(organization=org, is_main=False)
    n_meters = meters.count()
    if n_meters:
        has_reading = MeterReading.objects.filter(
            meter=OuterRef("pk"), is_estimated=False,
            date__gte=month_start, date__lte=last_month_end)
        missing = meters.exclude(Exists(has_reading)).count()
        if missing:
            month = _MONTHS[month_start.month - 1]
            todo.append({
                "key": "readings", "level": "info",
                "title": f"За {month} не сдали показания: {missing} из {n_meters}",
                "detail": "Без показаний расчёт пойдёт по среднему.",
                "action": "Показания", "to": "/electricity",
            })

    # ── смета ──
    year = today.year
    budget = Budget.objects.filter(organization=org, year=year).first()
    if budget is None:
        todo.append({
            "key": "budget", "level": "info",
            "title": f"Нет сметы на {year} год",
            "detail": "По смете считается размер членского взноса к собранию.",
            "action": "Составить смету", "to": "/budget",
        })
    elif not budget.is_approved:
        todo.append({
            "key": "budget", "level": "info",
            "title": f"Смета на {year} год не утверждена",
            "detail": "После собрания отметьте решение — и по ней можно начислить взнос.",
            "action": "Открыть смету", "to": "/budget",
        })
    elif not Charge.objects.filter(organization=org, period__year=year,
                                   charge_type__category=ChargeType.TYPE_MEMBERSHIP).exists():
        todo.append({
            "key": "budget", "level": "attention",
            "title": f"Членский взнос на {year} год не начислен",
            "detail": "Смета утверждена — начисление по ней в один клик.",
            "action": "Начислить по смете", "to": "/budget",
        })

    # ── реестр ──
    has_owner = PlotOwnership.objects.filter(plot=OuterRef("pk"), date_to__isnull=True)
    no_owner = Plot.objects.filter(organization=org).exclude(Exists(has_owner)).count()
    if no_owner:
        todo.append({
            "key": "owners", "level": "info",
            "title": f"{no_owner} {_plural(no_owner, 'участок', 'участка', 'участков')} без собственника",
            "detail": "Им не начисляются взносы.", "action": "Участки", "to": "/plots",
        })
    members = Member.objects.filter(organization=org, status=Member.STATUS_ACTIVE)
    n_members = members.count()
    no_access = members.filter(user_account__isnull=True).count()
    if n_members and no_access:
        todo.append({
            "key": "access", "level": "info",
            "title": f"{no_access} из {n_members} членов без доступа к кабинету",
            "detail": "Выдайте доступ — они увидят долг и смогут платить по QR.",
            "action": "Члены СНТ", "to": "/members",
        })

    # ── сводка ──
    spends = PlotCredit.objects.filter(organization=org, payment__isnull=False) \
        .values_list("payment", flat=True)
    collected = (Payment.objects.filter(organization=org, is_cancelled=False,
                                        date__year=year)
                 .exclude(method=Payment.METHOD_TRANSFER).exclude(pk__in=spends)
                 .aggregate(s=Sum("amount"))["s"] or ZERO)

    order = {"attention": 0, "info": 1}
    todo.sort(key=lambda t: order[t["level"]])
    return {
        "summary": {
            "plots": Plot.objects.filter(organization=org).count(),
            "members": n_members,
            "debtors": debtors,
            "total_debt": str(total_debt),
            "collected_year": str(collected),
            "year": year,
        },
        "todo": todo,
    }


_MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль",
           "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
