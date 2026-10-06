"""
Импорт реестра членов СНТ из таблицы.

    docker compose exec -T backend python manage.py import_members \
        --file /app/reestr.xlsx --org 'ТСН "Здоровье"' \
        --overrides /app/data/reestr-zdorovie-overrides.json --dry-run

Имя организации подставляется как оно записано в базе, целиком. Если в нём
есть кавычки — оборачивать в одинарные, иначе шелл их проглотит. Посмотреть
точное написание: manage.py shell -c "from organizations.models import
Organization; print([o.name for o in Organization.objects.all()])"

То же самое делает кнопка «Загрузить из Excel» на странице «Члены СНТ» —
код общий (members/importing.py). Колонки узнаются по заголовкам:
    № участка | ФИО | соток | телефон | доп. телефон | email | сособственник

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

from django.core.management.base import BaseCommand, CommandError

from core.xlsx import ImportFileError, read_table, run_import

# Совместимость: эти функции раньше жили здесь, их импортируют проверки.
from members.importing import (  # noqa: F401
    COLUMNS, REQUIRED, import_members, normalize_phone, split_fio,
)


class Command(BaseCommand):
    help = "Импортировать реестр членов и участков из xlsx"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Путь к xlsx")
        parser.add_argument("--org", required=True, help="Название организации")
        parser.add_argument(
            "--overrides", default=None,
            help="JSON-файл поправок к строкам (см. описание команды)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Только показать, что будет сделано, без записи в базу",
        )

    def handle(self, *args, **options):
        from organizations.models import Organization

        try:
            org = Organization.objects.get(name=options["org"])
        except Organization.DoesNotExist:
            names = ", ".join(Organization.objects.values_list("name", flat=True))
            raise CommandError(
                f"Организация «{options['org']}» не найдена. Есть: {names or 'ни одной'}"
            )
        overrides = self._load_overrides(options["overrides"])
        try:
            with open(options["file"], "rb") as fh:
                rows = read_table(fh, COLUMNS, REQUIRED)
        except OSError as exc:
            raise CommandError(f"Не удалось прочитать файл: {exc}")
        except ImportFileError as exc:
            raise CommandError(str(exc))

        self.stdout.write(f"Организация: {org.name}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "Режим проверки: в базу ничего не записывается."))
        result = run_import(lambda: import_members(org, rows, overrides),
                            options["dry_run"])

        self.stdout.write(f"Строк с данными: {result['rows']}")
        for label, value in result["stats"]:
            self.stdout.write(f"  {label}: {value}")
        if result["issues"]:
            self.stdout.write(self.style.WARNING(
                f"\nТребуют внимания ({len(result['issues'])}):"))
            for line in result["issues"]:
                self.stdout.write(self.style.WARNING(f"  • {line}"))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "\nНичего не записано. Уберите --dry-run, чтобы применить."))
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
