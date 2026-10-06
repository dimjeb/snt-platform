"""
Загрузка счётчиков и их показаний из Excel.

Одна строка — один счётчик и (по желанию) одно показание. Чтобы загрузить
историю, счётчик повторяется в нескольких строках с разными датами.

Правила:
- участки не создаются: они приходят из реестра. Строка с неизвестным
  участком пропускается и называется в отчёте;
- счётчик ищется по серийному номеру, а без номера — по участку; не
  нашёлся — заводится;
- показание на ту же дату с тем же числом — уже есть, пропускается молча;
  с другим числом — не перезаписывается, а показывается: какое из двух
  верное, решает человек;
- показание меньше предыдущего (или больше следующего) не записывается:
  расчёт дал бы отрицательный расход;
- «Долг за свет» вносится только для счётчика, заведённого этой же
  загрузкой, — так повторная загрузка файла долг не задвоит. Долг ложится
  так же, как из окна «Новый счётчик»: начислением «Электроэнергия» в
  годовой период.
"""
from decimal import Decimal

from django.utils import timezone

from core.xlsx import cell_date, cell_decimal, cell_flag, cell_text

# Узкие ключи раньше широких: «Показание ночь» содержит «показан».
COLUMNS = {
    "night": ("ночн", "ночь", "т2"),
    "value": ("показан", "т1", "день"),
    "debt": ("долг",),
    "main": ("главн", "общий", "ввод"),
    "date": ("дата",),
    "serial": ("серийн", "заводск", "номер счетчика", "№ счетчика", "счетчик"),
    "plot": ("участ",),
}
REQUIRED = {"plot"}

TEMPLATE_HEADER = ["Участок", "Номер счётчика", "Дата", "Показание",
                   "Показание ночь", "Главный", "Долг за свет, ₽"]
TEMPLATE_NOTES = [
    "Загрузка счётчиков и показаний. Первая строка листа «Данные» — заголовки.",
    "Обязательна колонка «Участок». Номер счётчика — желательно: по нему",
    "  счётчик находится при повторной загрузке.",
    "",
    "Одна строка — один счётчик и одно показание. История показаний — тот же",
    "счётчик в нескольких строках с разными датами.",
    "Участок — номер, как в реестре. Участки этой загрузкой не создаются:",
    "  сначала загрузите реестр членов.",
    "Главный — «да» для общего счётчика на вводе. Участок у него не пишется.",
    "Дата — дата снятия показания (дд.мм.гггг). Показание — всё число со",
    "  счётчика целиком, не расход за месяц.",
    "Показание ночь — только для двухтарифных.",
    "Долг за свет — сколько участок должен за электричество на дату показания.",
    "  Вносится только для нового счётчика, повторная загрузка его не задвоит.",
    "",
    "Сначала нажмите «Проверить» — сайт покажет, что будет сделано, ничего",
    "не записывая.",
]


def template_examples():
    today = timezone.localdate()
    return [
        ["", "ГЛ-0001", today, 125000, "", "да", ""],
        ["12", "0123456", today, 14350, "", "", 1250.50],
        ["13", "0765432", today, 8020.5, 3100, "", ""],
    ]


def import_meters(org, rows, user):
    from members.models import Plot

    from .models import Meter, MeterReading
    from .serializers import add_opening_debt

    stats = {
        "Счётчики: новые": 0, "Счётчики: уже были": 0,
        "Показания: добавлены": 0, "Показания: уже были": 0,
        "Долги за свет начислены": 0,
    }
    debt_total = Decimal("0")
    issues = []
    created_ids = set()      # счётчики, заведённые этой загрузкой
    existing_ids = set()     # найденные готовыми — для счёта, по разу
    debt_done = set()        # кому долг уже внесён в этой загрузке
    plots = {p.number: p for p in Plot.objects.filter(organization=org)}

    for row_no, values in rows:
        is_main = cell_flag(values.get("main"))
        number = cell_text(values.get("plot"))
        serial = cell_text(values.get("serial"))[:50]

        plot = None
        if not is_main:
            if not number:
                issues.append(f"строка {row_no}: нет номера участка (или отметьте "
                              "«Главный») — строка пропущена")
                continue
            plot = plots.get(number)
            if plot is None:
                issues.append(f"строка {row_no}: участка {number} нет в реестре — "
                              "строка пропущена")
                continue

        try:
            on_date = cell_date(values.get("date"))
        except ValueError as exc:
            issues.append(f"строка {row_no}: дата «{exc}» не распознана — "
                          "строка пропущена (нужно дд.мм.гггг)")
            continue
        try:
            value = cell_decimal(values.get("value"))
            night = cell_decimal(values.get("night"))
            debt = cell_decimal(values.get("debt"))
        except ValueError as exc:
            issues.append(f"строка {row_no}: «{exc}» — не число, строка пропущена")
            continue
        if any(x is not None and x < 0 for x in (value, night, debt)):
            issues.append(f"строка {row_no}: отрицательное число — строка пропущена")
            continue

        # ── счётчик ──
        meter = None
        if serial:
            meter = Meter.objects.filter(organization=org, serial_number=serial).first()
            if meter is not None and (meter.is_main != is_main
                                      or (not is_main and meter.plot_id != plot.id)):
                where = "главный ввод" if meter.is_main else \
                    f"участок {meter.plot.number if meter.plot else '—'}"
                issues.append(f"строка {row_no}: счётчик {serial} уже числится "
                              f"за другим местом ({where}) — строка пропущена")
                continue
        if meter is None:
            same_place = Meter.objects.filter(organization=org, is_main=is_main)
            if not is_main:
                same_place = same_place.filter(plot=plot)
            existing = same_place.order_by("pk").first()
            if existing is not None and (not serial or not existing.serial_number):
                meter = existing
                if serial and not existing.serial_number:
                    existing.serial_number = serial
                    existing.save(update_fields=["serial_number", "updated_at"])
            elif existing is not None:
                issues.append(f"строка {row_no}: на этом месте уже есть счётчик "
                              f"{existing.serial_number}, а в файле {serial}. Если "
                              "счётчик заменили — заведите новый вручную, "
                              "строка пропущена")
                continue
        if meter is None:
            meter = Meter.objects.create(organization=org, plot=plot,
                                         is_main=is_main, serial_number=serial)
            created_ids.add(meter.pk)
            stats["Счётчики: новые"] += 1
        elif meter.pk not in created_ids and meter.pk not in existing_ids:
            existing_ids.add(meter.pk)
            stats["Счётчики: уже были"] += 1

        # ── показание ──
        if night is not None and value is None:
            issues.append(f"строка {row_no}: ночное показание без дневного — "
                          "показание не записано")
        elif (value is None) != (on_date is None):
            issues.append(f"строка {row_no}: есть {'дата' if on_date else 'показание'}, "
                          f"но нет {'показания' if on_date else 'даты'} — показание "
                          "не записано")
        elif value is not None:
            same_day = MeterReading.objects.filter(meter=meter, date=on_date).first()
            if same_day is not None:
                if same_day.value == value and same_day.value_night == night:
                    stats["Показания: уже были"] += 1
                else:
                    issues.append(f"строка {row_no}: на {on_date:%d.%m.%Y} у счётчика "
                                  f"уже есть другое показание ({same_day.value.normalize():f}) "
                                  "— не перезаписано, проверьте вручную")
            else:
                before = (MeterReading.objects.filter(meter=meter, date__lt=on_date)
                          .order_by("-date").first())
                after = (MeterReading.objects.filter(meter=meter, date__gt=on_date)
                         .order_by("date").first())
                if before is not None and value < before.value:
                    issues.append(f"строка {row_no}: показание меньше предыдущего "
                                  f"({before.value.normalize():f} на "
                                  f"{before.date:%d.%m.%Y}) — не записано")
                elif after is not None and value > after.value:
                    issues.append(f"строка {row_no}: показание больше следующего "
                                  f"({after.value.normalize():f} на "
                                  f"{after.date:%d.%m.%Y}) — не записано")
                else:
                    MeterReading.objects.create(
                        organization=org, meter=meter, date=on_date, value=value,
                        value_night=night, submitted_by=user,
                        notes="Загрузка из Excel",
                    )
                    stats["Показания: добавлены"] += 1

        # ── долг ──
        if debt:
            if is_main:
                issues.append(f"строка {row_no}: у главного счётчика долга нет — "
                              "не начислен")
            elif meter.pk not in created_ids:
                issues.append(f"строка {row_no}: долг вносится только для нового "
                              "счётчика — не начислен. Для заведённого счётчика: "
                              "кнопка «Показание и долг»")
            elif meter.pk in debt_done:
                issues.append(f"строка {row_no}: долг этому счётчику уже внесён "
                              "строкой выше — второй не начислен")
            else:
                add_opening_debt(meter, debt, on_date or timezone.localdate(),
                                 value, user)
                debt_done.add(meter.pk)
                stats["Долги за свет начислены"] += 1
                debt_total += debt

    result_stats = [[k, v] for k, v in stats.items()]
    if debt_total:
        result_stats.append(["Долги за свет, сумма ₽", f"{debt_total:.2f}"])
    return {"rows": len(rows), "stats": result_stats, "issues": issues}
