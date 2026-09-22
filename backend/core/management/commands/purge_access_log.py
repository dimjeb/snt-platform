"""
Чистка журнала обращений к персональным данным.

Журнал нужен, но вечно он расти не должен: сам по себе он тоже сведения
о людях (кто и когда работал с реестром). Держим ровно столько, сколько
решено хранить, и не дольше.

    python manage.py purge_access_log --days 1095 --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Удалить записи журнала обращений к ПДн старше N дней"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=1095,
            help="Сколько дней хранить (по умолчанию 1095, три года)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Только показать, сколько записей попадёт под удаление",
        )

    def handle(self, *args, **options):
        from core.models import AccessLog

        days = options["days"]
        if days < 1:
            self.stderr.write("--days должен быть положительным")
            return
        cutoff = timezone.now() - timedelta(days=days)
        qs = AccessLog.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        total = AccessLog.objects.count()

        self.stdout.write(f"Всего записей в журнале: {total}")
        self.stdout.write(f"Старше {days} дней (до {cutoff:%d.%m.%Y}): {count}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Ничего не удалено (--dry-run)."))
            return
        if not count:
            self.stdout.write("Удалять нечего.")
            return
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Удалено записей: {count}"))
