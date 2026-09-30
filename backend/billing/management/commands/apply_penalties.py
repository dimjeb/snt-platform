"""
Начисление пеней по просроченным взносам.

Ставится в cron раз в сутки: пени должны появляться на следующий день
после срока, а не тогда, когда казначей вспомнит нажать кнопку.

    0 6 * * *  docker compose exec -T backend python manage.py apply_penalties

Запуск без аргументов проходит по всем активным товариществам.
Повторный запуск в тот же день ничего не задваивает.
"""
from django.core.management.base import BaseCommand

from billing.services import apply_penalties
from organizations.models import Organization


class Command(BaseCommand):
    help = "Начислить пени по начислениям с истёкшим сроком оплаты"

    def add_arguments(self, parser):
        parser.add_argument(
            "--org", type=int, default=None,
            help="ID товарищества. По умолчанию — все активные.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Показать, что будет начислено, и ничего не записывать.",
        )

    def handle(self, *args, **options):
        from django.db import transaction

        orgs = Organization.objects.filter(is_active=True)
        if options["org"]:
            orgs = orgs.filter(pk=options["org"])
        if not orgs.exists():
            self.stdout.write(self.style.WARNING("Товарищества не найдены."))
            return

        for org in orgs:
            if options["dry_run"]:
                # Считаем по-настоящему и откатываем: так видно ровно то,
                # что запишется, а не приблизительную оценку по другой
                # ветке кода. Вторая ветка рано или поздно разойдётся с
                # основной, и «показало одно, начислило другое» —
                # худшее, что может случиться с деньгами.
                with transaction.atomic():
                    result = apply_penalties(org)
                    transaction.set_rollback(True)
                prefix = "[сухой прогон] "
            else:
                result = apply_penalties(org)
                prefix = ""

            if result["created"]:
                self.stdout.write(self.style.SUCCESS(
                    f"{prefix}{org.name}: начислено пеней — "
                    f"{result['created']} шт. на {result['total']} ₽"
                ))
            else:
                self.stdout.write(f"{prefix}{org.name}: просроченных начислений нет")
