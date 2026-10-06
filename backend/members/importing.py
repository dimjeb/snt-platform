"""
Загрузка реестра членов и участков из Excel.

Один код и для кнопки «Загрузить из Excel» на сайте, и для консольной
команды import_members. Повторная загрузка того же файла ничего не
задваивает: член ищется по ФИО, участок — по номеру, владение — по паре.

В отчёт и журнал не попадают ни ФИО, ни телефоны: ссылаемся на номер
строки в Excel, его человек найдёт сам.
"""
import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import timezone

from core.xlsx import cell_flag, cell_text

# Порядок важен: узкие ключи раньше широких («доп. телефон» содержит
# «телефон», «сособственник» — «собственник»).
# «Площадь участка» содержит «участ», поэтому площадь проверяется раньше.
COLUMNS = {
    "area": ("сот", "площад"),
    "plot": ("участ", "№"),
    "co_owner": ("сособств", "совладел"),
    "fio": ("фио", "член", "собственник", "владелец"),
    "phone2": ("доп", "второй тел", "телефон 2"),
    "phone": ("телефон", "тел."),
    "email": ("почт", "email", "e-mail"),
}
REQUIRED = {"plot", "fio"}

TEMPLATE_HEADER = ["№ участка", "ФИО", "Соток", "Телефон", "Доп. телефон",
                   "Email", "Сособственник"]
TEMPLATE_EXAMPLES = [
    ["12", "Иванов Иван Иванович", 6, "+7 900 000-00-00", "", "", ""],
    ["12", "Иванова Мария Петровна", 6, "", "", "", "да"],
    ["13", "Петров Пётр", 8.5, "", "", "", ""],
]
TEMPLATE_NOTES = [
    "Загрузка реестра членов СНТ. Первая строка листа «Данные» — заголовки.",
    "Обязательны колонки «№ участка» и «ФИО», остальные — по желанию.",
    "Порядок колонок неважен, лишние колонки (улица, примечания) не мешают.",
    "",
    "ФИО — «Фамилия Имя Отчество». Одно слово считается фамилией.",
    "Соток — площадь участка, можно с запятой: 6,5.",
    "Сособственник — «да», если человек ВТОРОЙ владелец того же участка.",
    "  Без отметки участок, уже записанный за другим, не перепишется — сайт",
    "  покажет такую строку в списке «Требуют внимания».",
    "",
    "Повторная загрузка того же файла ничего не задвоит: обновятся телефоны",
    "и площади, новые люди и участки добавятся.",
    "Сначала нажмите «Проверить» — сайт покажет, что будет сделано, ничего",
    "не записывая.",
]

PHONE_MAX = 20


def normalize_phone(value) -> str:
    """
    Телефон к единому виду.

    Шестизначные номера — городские иркутские, они остаются как есть:
    приводить их к мобильному формату значило бы придумать несуществующий код.
    """
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return ""
    if len(digits) == 11 and digits[0] in "78":
        d = digits
        return f"+7 ({d[1:4]}) {d[4:7]}-{d[7:9]}-{d[9:11]}"
    if len(digits) == 10:
        return f"+7 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
    return str(value).strip()


def split_fio(value, single_word="last"):
    """
    ФИО -> (фамилия, имя, отчество). Недостающие части остаются пустыми.

    single_word говорит, чем считать единственное слово. По умолчанию —
    фамилией: так записано большинство неполных строк. Обратный случай
    задаётся поправкой, а не угадывается по окончанию слова.
    """
    parts = [p for p in str(value or "").replace("\xa0", " ").split() if p]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        if single_word == "first":
            return "", parts[0], ""
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def import_members(org, rows, overrides=None):
    """
    rows — [(номер строки, {ключ из COLUMNS: значение})].
    overrides — поправки консольной команды {«номер строки»: {...}}.

    Возвращает {"rows", "stats": [[подпись, число]], "issues": [...]}.
    """
    from .models import Member, Plot, PlotOwnership

    overrides = overrides or {}
    stats = {
        "Члены: новые": 0, "Члены: уже были": 0,
        "Участки: новые": 0, "Участки: уже были": 0,
        "Владения записаны": 0, "Сособственники добавлены": 0,
        "Без участка": 0,
    }
    issues = []
    used = set()
    for row_no, values in rows:
        fix = overrides.get(str(row_no), {})
        if fix:
            used.add(str(row_no))
        _import_row(row_no, values, fix, org, Member, Plot, PlotOwnership,
                    stats, issues)

    unused = set(overrides) - used - {"_comment"}
    if unused:
        # Поправка, не нашедшая своей строки, — молча потерянная правка.
        issues.append("поправки не легли ни на одну строку: "
                      + ", ".join(sorted(unused)))
    return {"rows": len(rows), "stats": [[k, v] for k, v in stats.items()],
            "issues": issues}


def _import_row(row_no, values, fix, org, Member, Plot, PlotOwnership,
                stats, issues):
    words = cell_text(values.get("fio")).split()
    last_name, first_name, patronymic = split_fio(
        values.get("fio"), single_word=fix.get("single_word_name", "last"))
    if not (last_name or first_name):
        # Член без имени не имеет смысла, а придумывать за источник нельзя.
        issues.append(f"строка {row_no}: нет ФИО — строка пропущена")
        return
    if len(words) == 1 and not fix.get("single_word_name"):
        issues.append(f"строка {row_no}: в ФИО одно слово — записано как фамилия, "
                      "имя допишите в карточке члена")

    phone = normalize_phone(values.get("phone"))
    phone2 = normalize_phone(values.get("phone2"))
    if len(phone) > PHONE_MAX:
        issues.append(f"строка {row_no}: телефон не распознан — не записан, "
                      "впишите в карточке")
        phone = ""
    notes = f"Доп. телефон: {phone2}" if phone2 else ""
    email = cell_text(values.get("email"))
    if email:
        try:
            validate_email(email)
        except DjangoValidationError:
            issues.append(f"строка {row_no}: email не похож на адрес — не записан")
            email = ""

    member, created = Member.objects.get_or_create(
        organization=org,
        last_name=last_name, first_name=first_name, patronymic=patronymic,
        defaults={"phone": phone, "notes": notes, "email": email,
                  "status": Member.STATUS_ACTIVE},
    )
    if created:
        stats["Члены: новые"] += 1
    else:
        changed = []
        for field, value in (("phone", phone), ("notes", notes), ("email", email)):
            if value and getattr(member, field) != value:
                setattr(member, field, value)
                changed.append(field)
        if changed:
            member.save(update_fields=changed + ["updated_at"])
        stats["Члены: уже были"] += 1

    number = cell_text(values.get("plot"))
    if not number and fix.get("plot"):
        number = str(fix["plot"]).strip()
    if not number:
        # Участок не выдумываем: член заводится без него, и это видно в отчёте.
        stats["Без участка"] += 1
        issues.append(f"строка {row_no}: нет номера участка — член заведён без участка")
        return
    if len(number) > Plot._meta.get_field("number").max_length:
        issues.append(f"строка {row_no}: номер участка слишком длинный — строка пропущена")
        return

    area = None
    raw_area = values.get("area")
    if raw_area is not None and cell_text(raw_area) != "":
        try:
            area = Decimal(cell_text(raw_area).replace(",", ".")).quantize(Decimal("0.01"))
            if area < 0 or area >= Decimal("10000"):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            issues.append(f"строка {row_no}: площадь «{cell_text(raw_area)}» "
                          "не число — не записана")
            area = None

    co_owner = bool(fix.get("co_owner")) or cell_flag(values.get("co_owner"))

    plot, plot_created = Plot.objects.get_or_create(
        organization=org, number=number, defaults={"area_sotok": area},
    )
    if plot_created:
        stats["Участки: новые"] += 1
    else:
        # Площадь сособственника не перетирает площадь участка: в реестре у
        # второй строки та же цифра, а если не та — верна первая.
        if area is not None and plot.area_sotok != area:
            if co_owner:
                issues.append(f"строка {row_no}: площадь у сособственника не совпадает "
                              f"с площадью участка {number} — оставлена прежняя")
            else:
                plot.area_sotok = area
                plot.save(update_fields=["area_sotok", "updated_at"])
        stats["Участки: уже были"] += 1

    owners = plot.ownerships.filter(date_to__isnull=True)
    if owners.filter(member=member).exists():
        return  # уже числится за ним — повторная загрузка ничего не плодит

    if not owners.exists():
        PlotOwnership.objects.create(
            organization=org, plot=plot, member=member,
            date_from=timezone.localdate(), notes="Загрузка реестра",
        )
        stats["Владения записаны"] += 1
    elif co_owner:
        PlotOwnership.objects.create(
            organization=org, plot=plot, member=member,
            date_from=timezone.localdate(), notes="Загрузка реестра: сособственник",
        )
        stats["Сособственники добавлены"] += 1
    else:
        issues.append(
            f"строка {row_no}: участок {number} уже записан за другим членом — "
            "владелец не изменён. Если это общая собственность, поставьте в "
            "колонке «Сособственник» «да»; если участок продан — смените "
            "владельца в карточке участка.")
