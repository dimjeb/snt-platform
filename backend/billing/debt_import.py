"""
Загрузка долгов из Excel — начальные остатки при переходе на сайт.

Каждая строка становится начислением на участок в годовом периоде
указанного года. Годовой, а не месячный, — по той же причине, что и долг
при добавлении счётчика: месячное «Электроэнергия» перезаписывает расчёт
света.

«За что» — либо название вида начисления, как оно заведено на сайте
(например «Погорелец»), либо слово-категория: членский, целевой, свет,
прочее. Незнакомое слово — строка пропускается: создать вид по опечатке
хуже, чем переспросить.

Повторная загрузка того же файла ничего не задваивает: строка с тем же
участком, годом, видом, суммой и описанием считается уже внесённой.
"""
import datetime as dt
from decimal import Decimal

from django.utils import timezone

from core.xlsx import cell_date, cell_decimal, cell_text

COLUMNS = {
    "due": ("срок", "оплатить до"),
    "plot": ("участ",),
    "amount": ("сумм", "долг"),
    "kind": ("за что", "вид", "назначен", "статья"),
    "year": ("год", "период"),
    "note": ("описан", "коммент", "примечан"),
}
REQUIRED = {"plot", "amount"}

DEFAULT_NOTE = "Долг на момент перехода на сайт"

TEMPLATE_HEADER = ["Участок", "Сумма, ₽", "За что", "Год", "Описание", "Срок оплаты"]
TEMPLATE_NOTES = [
    "Загрузка долгов (начальных остатков). Первая строка листа «Данные» — заголовки.",
    "Обязательны «Участок» и «Сумма». Один долг — одна строка; у участка может",
    "быть несколько строк: за разные годы и за разное.",
    "",
    "За что — членский, целевой, свет (электроэнергия) или прочее. Можно написать",
    "  точное название вида начисления, как он заведён на сайте, например «Погорелец».",
    "  Пусто — «прочее».",
    "Год — за какой год долг. Пусто — текущий год. Долг ложится в годовой период",
    "  этого года.",
    "Описание — по желанию; пусто — «" + DEFAULT_NOTE + "».",
    "Срок оплаты — дд.мм.гггг, по желанию. После него долг попадёт под пени.",
    "",
    "Участки этой загрузкой не создаются: сначала загрузите реестр членов.",
    "Если у участка есть аванс, он сразу пойдёт в погашение этих долгов.",
    "Повторная загрузка того же файла ничего не задвоит.",
]

KIND_WORDS = (
    ("membership", ("членск",)),
    ("target", ("целев",)),
    ("electricity", ("свет", "электр", "квт")),
    ("other", ("проч", "друг")),
)
DEFAULT_NAMES = {
    "membership": "Членский взнос",
    "target": "Целевой взнос",
    "electricity": "Электроэнергия",
    "other": "Прочее",
}


def template_examples():
    year = timezone.localdate().year
    return [
        ["12", 4500, "членский", year - 1, "", ""],
        ["12", 1250.50, "свет", year, "", ""],
        ["13", 3000, "целевой", year, "Взнос на дорогу", f"01.07.{year}"],
    ]


def _resolve_type(org, kind, cache):
    from .models import ChargeType

    key = kind.lower().replace("ё", "е")
    if key in cache:
        return cache[key]
    # Сначала — точное название вида, заведённого в этом СНТ.
    by_name = [t for t in ChargeType.objects.filter(organization=org)
               if t.name.lower().replace("ё", "е") == key]
    if by_name:
        cache[key] = by_name[0]
        return by_name[0]
    category = "other" if not key else None
    for cat, words in KIND_WORDS:
        if any(w in key for w in words):
            category = cat
            break
    if category is None:
        cache[key] = None
        return None
    # Первый вид этой категории; если нет — заводим с обычным названием.
    # get_or_create по категории не годится: целевых видов бывает несколько.
    ctype = (ChargeType.objects.filter(organization=org, category=category)
             .order_by("pk").first())
    if ctype is None:
        ctype = ChargeType.objects.create(organization=org, category=category,
                                          name=DEFAULT_NAMES[category])
    cache[key] = ctype
    return ctype


def import_debts(org, rows, user):
    from members.models import Plot

    from .credits import spend_credit
    from .models import BillingPeriod, Charge

    stats = {"Долги внесены": 0, "Уже были": 0}
    total = Decimal("0")
    issues = []
    plots = {p.number: p for p in Plot.objects.filter(organization=org)}
    types, periods, touched = {}, {}, {}
    this_year = timezone.localdate().year

    for row_no, values in rows:
        number = cell_text(values.get("plot"))
        plot = plots.get(number)
        if not number:
            issues.append(f"строка {row_no}: нет номера участка — пропущена")
            continue
        if plot is None:
            issues.append(f"строка {row_no}: участка {number} нет в реестре — пропущена")
            continue
        try:
            amount = cell_decimal(values.get("amount"))
        except ValueError as exc:
            issues.append(f"строка {row_no}: сумма «{exc}» — не число, пропущена")
            continue
        if amount is None or amount <= 0:
            issues.append(f"строка {row_no}: сумма пустая или не больше нуля — пропущена")
            continue
        amount = amount.quantize(Decimal("0.01"))

        kind = cell_text(values.get("kind"))
        ctype = _resolve_type(org, kind, types)
        if ctype is None:
            issues.append(f"строка {row_no}: «{kind}» — непонятно, за что долг. "
                          "Напишите членский, целевой, свет, прочее или точное "
                          "название вида начисления — строка пропущена")
            continue

        raw_year = values.get("year")
        year = this_year
        if raw_year is not None and cell_text(raw_year):
            if isinstance(raw_year, (dt.date, dt.datetime)):
                year = raw_year.year
            else:
                text = cell_text(raw_year)
                if not (text.isdigit() and 2000 <= int(text) <= this_year + 1):
                    issues.append(f"строка {row_no}: год «{text}» не распознан — "
                                  "пропущена")
                    continue
                year = int(text)

        try:
            due = cell_date(values.get("due"))
        except ValueError as exc:
            issues.append(f"строка {row_no}: срок оплаты «{exc}» не распознан — "
                          "пропущена (нужно дд.мм.гггг)")
            continue

        note = cell_text(values.get("note"))[:500] or DEFAULT_NOTE

        period = periods.get(year)
        if period is None:
            period = (BillingPeriod.objects
                      .filter(organization=org, year=year, month__isnull=True)
                      .order_by("pk").first())
            if period is None:
                period = BillingPeriod.objects.create(organization=org, year=year,
                                                      month=None)
            periods[year] = period

        if Charge.objects.filter(organization=org, plot=plot, period=period,
                                 charge_type=ctype, amount=amount,
                                 description=note).exists():
            stats["Уже были"] += 1
            continue
        Charge.objects.create(organization=org, plot=plot, period=period,
                              charge_type=ctype, amount=amount, description=note,
                              due_date=due)
        stats["Долги внесены"] += 1
        total += amount
        touched[plot.pk] = plot

    # Аванс участка сразу идёт в погашение — как после любого начисления.
    for plot in touched.values():
        spend_credit(plot, user=user)

    result = [[k, v] for k, v in stats.items()]
    if total:
        result.append(["Сумма внесённых долгов, ₽", f"{total:.2f}"])
    return {"rows": len(rows), "stats": result, "issues": issues}
