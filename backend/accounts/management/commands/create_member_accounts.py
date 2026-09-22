"""
Массовая выдача учётных записей членам товарищества.

    python manage.py create_member_accounts --org 'ТСН "Здоровье"' --dry-run
    python manage.py create_member_accounts --org 'ТСН "Здоровье"' \
        --out /app/credentials.csv

У каждого свой случайный пароль и флаг «сменить при первом входе». Общий
стартовый пароль на всех не годится: пока человек не вошёл впервые, его
учётная запись открыта любому, кто этот пароль знает, а внутри — ФИО,
телефон, участок и долги. При 145 учётках и неделе между раздачей и
первым входом это гарантированная утечка ПДн.

Пароли НЕ печатаются в вывод команды и не попадают в журналы — только
в файл, который указан в --out. Файл создаётся с правами 600.
Раздать и удалить.

Команда идемпотентна: у кого учётка уже есть, того пропускает.
"""
import csv
import os
import secrets

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Без похожих друг на друга символов: пароль будут диктовать по телефону
# и переписывать с бумажки, а 0/O и 1/l/I в этом деле — источник звонков
# «у меня не входит».
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"

RU_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def translit(value: str) -> str:
    out = []
    for ch in (value or "").lower():
        if ch in RU_LAT:
            out.append(RU_LAT[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
    return "".join(out)


def make_password() -> str:
    """Три группы по четыре символа: xxxx-xxxx-xxxx."""
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


class Command(BaseCommand):
    help = "Завести учётные записи членам товарищества с временными паролями"

    def add_arguments(self, parser):
        parser.add_argument("--org", required=True, help="Название организации")
        parser.add_argument(
            "--out", default="member-credentials.csv",
            help="Куда выгрузить логины и пароли (файл с правами 600)",
        )
        parser.add_argument(
            "--plot", action="append", default=[], metavar="НОМЕР",
            help=(
                "Только собственникам этих участков. Можно повторять: "
                "--plot 87 --plot 88. Без него — всем членам товарищества."
            ),
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Показать, что будет сделано, без записи в базу и файл",
        )

    def handle(self, *args, **options):
        from organizations.models import Organization
        from members.models import Member
        from accounts.models import User

        try:
            org = Organization.objects.get(name=options["org"])
        except Organization.DoesNotExist:
            names = ", ".join(Organization.objects.values_list("name", flat=True))
            raise CommandError(
                f"Организация «{options['org']}» не найдена. Есть: {names or 'ни одной'}"
            )

        dry = options["dry_run"]
        members = (
            Member.objects.filter(organization=org)
            .prefetch_related("ownerships__plot")
            .order_by("last_name", "first_name", "pk")
        )

        # Точечная выдача. Нужна, чтобы проверить цепочку на одном
        # человеке, не заводя сразу полтораста учёток и не создавая файл
        # с паролями и ПДн всего товарищества раньше времени.
        wanted_plots = [p.strip() for p in options["plot"] if p.strip()]
        if wanted_plots:
            from members.models import Plot

            found = Plot.objects.filter(organization=org, number__in=wanted_plots)
            missing = set(wanted_plots) - set(found.values_list("number", flat=True))
            if missing:
                raise CommandError(
                    "Нет таких участков: " + ", ".join(sorted(missing))
                )
            members = members.filter(
                ownerships__plot__in=found,
                ownerships__date_to__isnull=True,
            ).distinct()
            if not members:
                raise CommandError(
                    "У этих участков нет текущих собственников — "
                    "заводить учётку некому."
                )

        existing = set(
            User.objects.filter(member__organization=org)
            .values_list("member_id", flat=True)
        )
        taken = set(User.objects.values_list("username", flat=True))

        rows = []
        skipped = 0
        created = 0

        for member in members:
            if member.pk in existing:
                skipped += 1
                continue

            base = translit(member.last_name) or translit(member.first_name) or "member"
            username = f"{base}-{member.pk}"
            # Подстраховка на случай, если такой логин уже занят вручную
            # заведённой учёткой: генерируем следующий свободный.
            suffix = 0
            while username in taken:
                suffix += 1
                username = f"{base}-{member.pk}-{suffix}"
            taken.add(username)

            password = make_password()
            try:
                # Пароль обязан проходить ту же политику, что и любой другой:
                # временный не значит слабый.
                validate_password(password)
            except ValidationError as exc:
                raise CommandError(
                    "Сгенерированный пароль не прошёл политику паролей: "
                    + "; ".join(exc.messages)
                )

            plots = ", ".join(p.number for p in member.plots) or "—"

            if not dry:
                user = User(
                    username=username,
                    organization=org,
                    member=member,
                    role=User.ROLE_MEMBER,
                    phone=member.phone or "",
                    must_change_password=True,
                    is_active=True,
                )
                user.set_password(password)
                rows.append((user, member.full_name, plots, username, password))
            else:
                rows.append((None, member.full_name, plots, username, password))
            created += 1

        if not dry:
            with transaction.atomic():
                User.objects.bulk_create([r[0] for r in rows])

        self.stdout.write(f"Организация: {org.name}")
        if wanted_plots:
            self.stdout.write(f"Участки: {', '.join(wanted_plots)}")
        self.stdout.write(
            f"{'Собственников' if wanted_plots else 'Членов всего'}: "
            f"{members.count()}"
        )
        self.stdout.write(f"Учётка уже есть: {skipped}")
        self.stdout.write(
            f"{'Будет заведено' if dry else 'Заведено'} учётных записей: {created}"
        )

        if dry:
            self.stdout.write(self.style.WARNING(
                "\nРежим проверки: ни база, ни файл не тронуты. "
                "Уберите --dry-run, чтобы применить."
            ))
            return

        if not rows:
            self.stdout.write("Заводить некого, файл не создавался.")
            return

        path = options["out"]
        # Права выставляем ДО записи: иначе между созданием файла и chmod
        # существует окно, в которое пароли читаемы всем.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(["ФИО", "Участок", "Логин", "Временный пароль"])
            for _, full_name, plots, username, password in rows:
                writer.writerow([full_name, plots, username, password])

        self.stdout.write(self.style.SUCCESS(f"\nЛогины и пароли: {path}"))
        self.stdout.write(self.style.WARNING(
            "В файле персональные данные и действующие пароли. "
            "Раздать и удалить: rm -f " + path
        ))
        self.stdout.write(
            "Каждому при первом входе система потребует сменить пароль — "
            "до этого API отдаёт 403 на всё, кроме профиля и смены пароля."
        )
