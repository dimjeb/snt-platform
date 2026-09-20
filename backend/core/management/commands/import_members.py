"""
Импорт реестра членов СНТ из таблицы.

    docker compose exec -T backend python manage.py import_members \
        --file /tmp/reestr.xlsx --org "СНТ «Здоровье»" --dry-run

Ожидаемые столбцы (первая строка — заголовок):
    № участка | ФИО | кол-во соток | телефон | доп телефон

Команда идемпотентна: повторный запуск обновляет существующие записи,
а не создаёт вторые. Сопоставление идёт по номеру участка внутри
организации, а при его отсутствии — по ФИО.

В журнал не пишутся ни ФИО, ни телефоны: это персональные данные,
и логи — самое частое место их случайной утечки.
"""
import re
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


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


def split_fio(value):
    """ФИО -> (фамилия, имя, отчество). Недостающие части остаются пустыми."""
    parts = [p for p in str(value or "").replace("\xa0", " ").split() if p]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
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

        wb = openpyxl.load_workbook(options["file"], data_only=True)
        ws = wb[options["sheet"]] if options["sheet"] else wb[wb.sheetnames[0]]

        rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if any(r)]
        self.stdout.write(f"Организация: {org.name}")
        self.stdout.write(f"Строк с данными: {len(rows)}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "Режим проверки: в базу ничего не записывается."
            ))

        stats = {
            "члены создано": 0, "члены обновлено": 0,
            "участки создано": 0, "участки обновлено": 0,
            "владения создано": 0, "без участка": 0,
        }
        issues = []

        try:
            with transaction.atomic():
                for idx, row in enumerate(rows, start=2):
                    self._import_row(idx, row, org, Member, Plot, PlotOwnership,
                                     stats, issues)
                if options["dry_run"]:
                    raise _DryRun()
        except _DryRun:
            pass

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

    def _import_row(self, idx, row, org, Member, Plot, PlotOwnership, stats, issues):
        raw_number, raw_fio, raw_area, raw_tel, raw_tel2 = (list(row) + [None] * 5)[:5]

        last_name, first_name, patronymic = split_fio(raw_fio)
        if not last_name:
            # Строку без ФИО пропускаем: член без имени не имеет смысла,
            # а придумывать за источник нельзя.
            issues.append(f"строка {idx}: нет ФИО, строка пропущена")
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
        if not number:
            # Участок не выдумываем: член заводится без него, и это видно в отчёте.
            stats["без участка"] += 1
            issues.append(
                f"строка {idx}: нет номера участка — член заведён без участка"
            )
            return

        area = None
        if raw_area is not None:
            try:
                area = Decimal(str(raw_area).replace(",", ".")).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                issues.append(f"строка {idx}: площадь «{raw_area}» не число, пропущена")

        plot, plot_created = Plot.objects.get_or_create(
            organization=org, number=number, defaults={"area_sotok": area},
        )
        if plot_created:
            stats["участки создано"] += 1
        else:
            if area is not None and plot.area_sotok != area:
                plot.area_sotok = area
                plot.save(update_fields=["area_sotok", "updated_at"])
            stats["участки обновлено"] += 1

        current = plot.ownerships.filter(date_to__isnull=True).first()
        if current is None:
            from django.utils import timezone
            PlotOwnership.objects.create(
                organization=org, plot=plot, member=member,
                date_from=timezone.localdate(),
                notes="Импорт реестра",
            )
            stats["владения создано"] += 1
        elif current.member_id != member.pk:
            issues.append(
                f"строка {idx}: участок {number} уже числится за другим членом — "
                "владелец не изменён, проверьте вручную"
            )


class _DryRun(Exception):
    """Служебное исключение для отката транзакции в режиме проверки."""
