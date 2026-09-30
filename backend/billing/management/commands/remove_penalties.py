"""
Снятие начисленных пеней.

Обратная операция к `apply_penalties`. Нужна, когда пени начислили
ошибочно: не тем, не на ту дату, не по той ставке. Кнопки в интерфейсе
для этого нет намеренно — снятие денег задним числом должно оставлять
след в консоли администратора, а не делаться в два клика.

Почему это не `Charge.objects.filter(...).delete()`:

  * `Payment.charge` стоит на PROTECT, и оплаченные пени просто не
    удалятся — Django бросит ProtectedError на всей пачке;
  * `apply_penalties` в конце зовёт `spend_all_credits`, поэтому у
    всех, у кого был аванс, пени погасились сразу же. Эти деньги надо
    вернуть на лицевой счёт, а не потерять;
  * пени, оплаченные настоящими деньгами (наличными, переводом), —
    это уже полученные товариществом деньги. Такие не трогаем и
    называем поимённо: разбираться с ними должен человек.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Charge, ChargeType, Payment, PlotCredit
from organizations.models import Organization


class Command(BaseCommand):
    help = "Удалить начисленные пени и вернуть зачтённый под них аванс"

    def add_arguments(self, parser):
        parser.add_argument("--org", type=int, default=None,
                            help="ID товарищества. По умолчанию — все активные.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Показать, что будет удалено, и ничего не менять.")

    def handle(self, *args, **options):
        orgs = Organization.objects.filter(is_active=True)
        if options["org"]:
            orgs = orgs.filter(pk=options["org"])
        if not orgs.exists():
            self.stdout.write(self.style.WARNING("Товарищества не найдены."))
            return

        for org in orgs:
            with transaction.atomic():
                report = self._remove(org)
                if options["dry_run"]:
                    transaction.set_rollback(True)
            self._print(org, report, dry=options["dry_run"])

    def _remove(self, org):
        penalties = list(
            Charge.objects
            .filter(organization=org,
                    charge_type__category=ChargeType.TYPE_PENALTY)
            .select_related("plot")
            .prefetch_related("payments")
        )

        deleted, returned, blocked = 0, Decimal("0"), []
        amount = Decimal("0")

        for penalty in penalties:
            live = [p for p in penalty.payments.all() if not p.is_cancelled]

            # Платёж, родившийся из аванса, помечен строкой расхода в
            # ленте лицевого счёта — там стоит ссылка на сам платёж.
            # Это надёжнее, чем смотреть на текст комментария.
            from_credit, real_money = [], []
            for payment in live:
                if PlotCredit.objects.filter(payment=payment).exists():
                    from_credit.append(payment)
                else:
                    real_money.append(payment)

            if real_money:
                blocked.append((penalty, sum(p.amount for p in real_money)))
                continue

            for payment in from_credit:
                # Возвращаем аванс: убираем строку расхода, и остаток
                # лицевого счёта снова становится прежним. Остаток
                # считается суммой ленты, отдельного поля с балансом
                # нет, поэтому больше ничего править не надо.
                spend_rows = PlotCredit.objects.filter(payment=payment)
                returned += sum(-row.amount for row in spend_rows)
                spend_rows.delete()
                Payment.objects.filter(pk=payment.pk).delete()

            # Строки аванса, ссылавшиеся на это начисление без платежа,
            # отвяжутся сами: у PlotCredit.charge стоит SET_NULL.
            amount += penalty.amount
            penalty.delete()
            deleted += 1

        return {"deleted": deleted, "amount": amount,
                "returned": returned, "blocked": blocked}

    def _print(self, org, report, *, dry):
        prefix = "[сухой прогон] " if dry else ""
        if not report["deleted"] and not report["blocked"]:
            self.stdout.write(f"{prefix}{org.name}: начисленных пеней нет")
            return

        if report["deleted"]:
            self.stdout.write(self.style.SUCCESS(
                f"{prefix}{org.name}: удалено начислений пеней — "
                f"{report['deleted']} шт. на {report['amount']} ₽"
            ))
        if report["returned"]:
            self.stdout.write(
                f"{prefix}  возвращено на лицевые счета: {report['returned']} ₽"
            )
        for penalty, paid in report["blocked"]:
            self.stdout.write(self.style.WARNING(
                f"{prefix}  уч. {penalty.plot.number}: пени на "
                f"{penalty.amount} ₽ оплачены настоящими деньгами "
                f"({paid} ₽) — не тронуты, разберитесь вручную"
            ))
