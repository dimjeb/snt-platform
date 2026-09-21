"""
Импорт реестра членов СНТ из таблицы.

    docker compose exec -T backend python manage.py import_members \
        --file /app/reestr.xlsx --org 'ТСН "Здоровье"' \
        --overrides /app/data/reestr-zdorovie-overrides.json --dry-run

Имя организации подставляется как оно записано в базе, целиком. Если в нём
есть кавычки — оборачивать в одинарные, иначе шелл их проглотит. Посмотреть
точное написание: manage.py shell -c "from organizations.models import
Organization; print([o.name for o in Organization.objects.all()])"

Ожидаемые столбцы (первая строка — заголовок):
    № участка | ФИО | кол-во соток | телефон | доп телефон

Команда идемпотентна: повторный запуск обновляет существующие записи,
а не создаёт вторые. Сопоставление идёт по номеру участка внутри
организации, а при его отсутствии — по ФИО.

В журнал не пишутся ни ФИО, ни телефоны: это персональные данные,
и логи — самое частое место их случайной утечки.

Файл поправок (--overrides)
---------------------------
Исходный реестр местами неполон, и часть пробелов машина восстановить
не может: из одного слова в графе ФИО не видно, фамилия это или имя,
а пустой номер участка не подсказывает, что человек — второй
собственник соседней строки. Гадать тут нельзя, поэтому поправки
задаются явно, JSON-файлом, ключ — номер строки в таблице:

    {
      "20": {"single_word_name": "first",
             "comment": "единственное слово в ФИО — имя, не фамилия"},
      "90": {"plot": "88", "co_owner": true,
             "comment": "вторая собственница участка 88"}
    }

Поля:
    single_word_name  "first" | "last" — чем считать единственное слово
                      в графе ФИО (по умолчанию "last", фамилия)
    plot              номер участка, если в таблице он не проставлен
    co_owner          true — строка добавляет ещё одного собственника
                      к участку, а не заменяет текущего
    comment           пояснение для человека, командой не читается

В файле поправок нет персональных данных — только указания, как читать
строку. Его можно держать в репозитории рядом с кодом.
"""
import json
import re
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


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
    задаётся поправкой, а не угадывается по окончанию слова — окончание
    не признак, «Кузьма» и «Кузьма» в графе фамилии выглядят одинаково.
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


class Command(BaseCommand):
    help = "Импортировать реестр членов и участков из xlsx"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Путь к xlsx")
        parser.add_argument("--org", required=True, help="Название организации")
        parser.add_argument("--sheet", default=None, help="Лист (по умолчанию первый)")
        parser.add_argument(
            "--overrides", default=None,
            help="JSON-файл поправок к строкам (см. описание команды)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Только показать, что будет сделано, без записи в базу",
        )

    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("Нужен openpyxl: он есть в requirements проекта.")

        from organizations.models import Organization
        from members.models import Member, Plot, PlotOwnership

        try:
            org = Organization.objects.get(name=options["org"])
        except Organization.DoesNotExist:
            names = ", ".join(Organization.objects.values_list("name", flat=True))
            raise CommandError(
                f"Организация «{options['org']}» не найдена. Есть: {names or 'ни одной'}"
            )

        overrides = self._load_overrides(options["overrides"])

        wb = openpyxl.load_workbook(options["file"], data_only=True)
        ws = wb[options["sheet"]] if options["sheet"] else wb[wb.sheetnames[0]]

        # Номер строки берём у самой ячейки, а не из enumerate: пустые
        # строки в середине таблицы иначе сбивают нумерацию, и поправка,
        # выписанная по номеру строки в Excel, попадёт не туда.
        rows = []
        for cells in ws.iter_rows(min_row=2):
            values = [c.value for c in cells]
            if any(v is not None and str(v).strip() != "" for v in values):
                rows.append((cells[0].row, values))

        self.stdout.write(f"Организация: {org.name}")
        self.stdout.write(f"Строк с данными: {len(rows)}")
        fixes_count = len([k for k in overrides if k != "_comment"])
        if fixes_count:
            self.stdout.write(f"Поправок загружено: {fixes_count}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "Режим проверки: в базу ничего не записывается."
            ))

        stats = {
            "члены создано": 0, "члены обновлено": 0,
            "участки создано": 0, "участки обновлено": 0,
            "владения создано": 0, "сособственники добавлены": 0,
            "без участка": 0,
        }
        issues = []
        used_overrides = set()

        try:
            with transaction.atomic():
                for row_no, values in rows:
                    fix = overrides.get(str(row_no), {})
                    if fix:
                        used_overrides.add(str(row_no))
                    self._import_row(row_no, values, fix, org,
                                     Member, Plot, PlotOwnership, stats, issues)
                if options["dry_run"]:
                    raise _DryRun()
        except _DryRun:
            pass

        unused = set(overrides) - used_overrides - {"_comment"}
        if unused:
            # Поправка, не нашедшая своей строки, — это молча потерянная
            # правка. Лучше сказать вслух, чем оставить человека в
            # уверенности, что она применилась.
            issues.append(
                "поправки не легли ни на одну строку: "
                + ", ".join(sorted(unused))
            )

        self.stdout.write("")
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value}")

        if issues:
            self.stdout.write(self.style.WARNING(
                f"\nТребуют внимания ({len(issues)}):"
            ))
            for line in issues:
                self.stdout.write(self.style.WARNING(f"  • {line}"))

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "\nНичего не записано. Уберите --dry-run, чтобы применить."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("\nИмпорт завершён."))

    def _load_overrides(self, path):
        if not path:
            return {}
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except OSError as exc:
            raise CommandError(f"Не удалось прочитать файл поправок: {exc}")
        except json.JSONDecodeError as exc:
            raise CommandError(f"Файл поправок — не валидный JSON: {exc}")
        if not isinstance(data, dict):
            raise CommandError("Файл поправок должен быть объектом {строка: поправка}")
        known = {"single_word_name", "plot", "co_owner", "comment"}
        for key, value in data.items():
            if key == "_comment":
                continue
            if not isinstance(value, dict):
                raise CommandError(f"Поправка для строки {key} — не объект")
            unknown = set(value) - known
            if unknown:
                raise CommandError(
                    f"Поправка для строки {key}: неизвестные поля "
                    f"{', '.join(sorted(unknown))}. Допустимы: "
                    f"{', '.join(sorted(known))}"
                )
        return data

    def _import_row(self, row_no, row, fix, org, Member, Plot, PlotOwnership,
                    stats, issues):
        raw_number, raw_fio, raw_area, raw_tel, raw_tel2 = (list(row) + [None] * 5)[:5]

        last_name, first_name, patronymic = split_fio(
            raw_fio, single_word=fix.get("single_word_name", "last")
        )
        if not (last_name or first_name):
            # Строку без ФИО пропускаем: член без имени не имеет смысла,
            # а придумывать за источник нельзя.
            issues.append(f"строка {row_no}: нет ФИО, строка пропущена")
            return

        phone = normalize_phone(raw_tel)
        phone2 = normalize_phone(raw_tel2)
        notes = f"Доп. телефон: {phone2}" if phone2 else ""

        member, created = Member.objects.get_or_create(
            organization=org,
            last_name=last_name, first_name=first_name, patronymic=patronymic,
            defaults={"phone": phone, "notes": notes, "status": Member.STATUS_ACTIVE},
        )
        if created:
            stats["члены создано"] += 1
        else:
            changed = []
            if phone and member.phone != phone:
                member.phone = phone
                changed.append("phone")
            if notes and member.notes != notes:
                member.notes = notes
                changed.append("notes")
            if changed:
                member.save(update_fields=changed + ["updated_at"])
            stats["члены обновлено"] += 1

        number = "" if raw_number is None else str(raw_number).strip()
        if not number and fix.get("plot"):
            number = str(fix["plot"]).strip()
        if not number:
            # Участок не выдумываем: член заводится без него, и это видно в отчёте.
            stats["без участка"] += 1
            issues.append(
                f"строка {row_no}: нет номера участка — член заведён без участка"
            )
            return

        area = None
        if raw_area is not None:
            try:
                area = Decimal(str(raw_area).replace(",", ".")).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                issues.append(
                    f"строка {row_no}: площадь «{raw_area}» не число, пропущена"
                )

        plot, plot_created = Plot.objects.get_or_create(
            organization=org, number=number, defaults={"area_sotok": area},
        )
        if plot_created:
            stats["участки создано"] += 1
        else:
            # Площадь сособственника не перетирает площадь участка: в
            # реестре у второй строки та же цифра, а если не та — верна
            # первая, и расхождение лучше показать, чем тихо заменить.
            if area is not None and plot.area_sotok != area:
                if fix.get("co_owner"):
                    issues.append(
                        f"строка {row_no}: площадь сособственника ({area}) не "
                        f"совпадает с площадью участка {number} "
                        f"({plot.area_sotok}) — оставлена прежняя"
                    )
                else:
                    plot.area_sotok = area
                    plot.save(update_fields=["area_sotok", "updated_at"])
            stats["участки обновлено"] += 1

        owners = plot.ownerships.filter(date_to__isnull=True)
        if owners.filter(member=member).exists():
            return  # уже числится за ним, повторный запуск ничего не плодит

        if not owners.exists():
            PlotOwnership.objects.create(
                organization=org, plot=plot, member=member,
                date_from=timezone.localdate(),
                notes="Импорт реестра",
            )
            stats["владения создано"] += 1
        elif fix.get("co_owner"):
            # Общая собственность: участок числится сразу за несколькими.
            PlotOwnership.objects.create(
                organization=org, plot=plot, member=member,
                date_from=timezone.localdate(),
                notes="Импорт реестра: сособственник",
            )
            stats["сособственники добавлены"] += 1
        else:
            issues.append(
                f"строка {row_no}: участок {number} уже числится за другим членом — "
                "владелец не изменён, проверьте вручную. Если это общая "
                "собственность, добавьте в файл поправок "
                f'"{row_no}": {{"co_owner": true}}'
            )


class _DryRun(Exception):
    """Служебное исключение для отката транзакции в режиме проверки."""
