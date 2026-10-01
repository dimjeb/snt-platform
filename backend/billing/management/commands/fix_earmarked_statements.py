"""
Исправление раскладки выписок, проведённых до того, как целевые деньги
перестали уходить в чужие начисления.

Что было: платёж с назначением «целевой взнос», а целевого начисления
у участка нет — и остаток уходил «в остальные начисления», то есть в
членский. Целевые деньги закрывали членские взносы. Разница с суммой
членского ложилась общим авансом и потом зачитывалась во что угодно —
в пени, в свет.

Что делает команда, по каждой проведённой строке выписки с категорией:
  1. платежи этой строки в начисления другой категории сторнируются
     (минусовой платёж способом «перенос», исходный не правится и не
     удаляется), а деньги кладутся авансом с назначением — ждать
     начислений своей категории;
  2. общий аванс, родившийся из этой строки, получает то же назначение;
  3. если общий аванс участка после этого уходит в минус — значит, эти
     деньги уже были зачтены во что-то другое. Такие зачёты (строки
     «Зачтено из аванса») отменяются с самых поздних, пока общий аванс
     не перестанет быть отрицательным;
  4. всё, что осталось или освободилось, снова зачитывается по
     правилам: целевой аванс — только в целевые начисления.

Запускать сначала с --dry-run: он считает по-настоящему и откатывает.

После исправления долги по членским у этих участков вернутся — они
и правда не оплачены. Пени, начисленные до исправления, считались от
неверного остатка: их стоит снять (remove_penalties) и начислить заново.
"""
import uuid
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from billing.credits import credit_balance, spend_all_credits
from billing.models import BankTransaction, Payment, PlotCredit
from billing.statement_service import CATEGORY_LABELS
from organizations.models import Organization


class Command(BaseCommand):
    help = "Вернуть целевые (и др. назначенные) деньги из чужих начислений"

    def add_arguments(self, parser):
        parser.add_argument("--org", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        orgs = Organization.objects.filter(is_active=True)
        if options["org"]:
            orgs = orgs.filter(pk=options["org"])
        for org in orgs:
            with transaction.atomic():
                report = self._fix(org)
                if options["dry_run"]:
                    transaction.set_rollback(True)
            self._print(org, report, dry=options["dry_run"])

    # ------------------------------------------------------------------

    def _row_payments(self, row):
        """Платежи, созданные проведением этой строки."""
        legacy = Q(bank_transaction__isnull=True,
                   external_ref=row.doc_number, date=row.date,
                   method=Payment.METHOD_BANK,
                   notes=f"Выписка {row.statement.file_name}",
                   charge__plot=row.plot)
        return (Payment.objects
                .filter(organization=row.organization, is_cancelled=False,
                        amount__gt=0)
                .filter(Q(bank_transaction=row) | legacy)
                .select_related("charge__charge_type"))

    def _fix(self, org):
        report = {"rows": 0, "moved": Decimal("0"), "relabelled": Decimal("0"),
                  "undone": Decimal("0"), "manual": [], "plots": set()}
        rows = (BankTransaction.objects
                .filter(organization=org, status=BankTransaction.STATUS_APPLIED,
                        plot__isnull=False)
                .exclude(category="")
                .select_related("statement", "plot"))

        for row in rows:
            if row.allocation:
                # Разделённые вручную строки проведены по частям, и что
                # из них «не туда» — решает человек, а не команда.
                report["manual"].append(row)
                continue
            label = CATEGORY_LABELS.get(row.category, row.category)
            mark = f"fix-{uuid.uuid4().hex[:12]}"
            moved_here = Decimal("0")

            # Чистая сумма строки по каждому начислению: исходные платежи
            # минус уже сделанные исправления. Без этого повторный запуск
            # сторнировал бы тот же платёж ещё раз — исходный ведь не
            # удаляется.
            net = defaultdict(Decimal)
            charges = {}
            for payment in self._row_payments(row):
                net[payment.charge_id] += payment.amount
                charges[payment.charge_id] = payment.charge
            for fixed in Payment.objects.filter(
                    bank_transaction=row, method=Payment.METHOD_TRANSFER,
                    amount__lt=0):
                net[fixed.charge_id] += fixed.amount

            for charge_id, amount in net.items():
                charge = charges.get(charge_id)
                if charge is None or amount <= 0:
                    continue
                if charge.charge_type.category == row.category:
                    continue
                Payment.objects.create(
                    organization=org, charge=charge,
                    date=row.date, amount=-amount,
                    method=Payment.METHOD_TRANSFER, external_ref=mark,
                    bank_transaction=row,
                    notes=(f"Исправление: деньги с назначением «{label}» "
                           f"были разнесены в «{charge.charge_type.name}». "
                           f"Отложены авансом на {label} взнос."),
                )
                PlotCredit.objects.create(
                    organization=org, plot=row.plot, date=row.date,
                    amount=amount, category=row.category,
                    transaction=row, source=PlotCredit.SOURCE_STATEMENT,
                    notes=f"Ждёт начислений «{label}» — исправление раскладки",
                )
                moved_here += amount

            relabel = PlotCredit.objects.filter(
                transaction=row, category="", amount__gt=0)
            relabelled_here = sum((r.amount for r in relabel), Decimal("0"))
            relabel.update(category=row.category)

            if moved_here or relabelled_here:
                report["rows"] += 1
                report["moved"] += moved_here
                report["relabelled"] += relabelled_here
                report["plots"].add(row.plot)
                row.note = (row.note or "") + (
                    f" Раскладка исправлена: {moved_here + relabelled_here} ₽ "
                    f"отложено на {label} взнос.")
                row.save(update_fields=["note", "updated_at"])

        # Общий аванс ушёл в минус — значит, переназначенные деньги уже
        # были зачтены во что-то. Отменяем зачёты с самых поздних.
        for plot in report["plots"]:
            spends = (PlotCredit.objects
                      .filter(plot=plot, category="", amount__lt=0,
                              payment__isnull=False)
                      .order_by("-date", "-pk"))
            for spend in spends:
                if credit_balance(plot, "") >= 0:
                    break
                payment = spend.payment
                report["undone"] += -spend.amount
                spend.delete()
                payment.delete()

        spend_all_credits(org)
        return report

    def _print(self, org, report, *, dry):
        prefix = "[сухой прогон] " if dry else ""
        if not report["rows"] and not report["manual"]:
            self.stdout.write(f"{prefix}{org.name}: исправлять нечего")
            return
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{org.name}: исправлено строк выписки — {report['rows']}, "
            f"участков — {len(report['plots'])}"))
        self.stdout.write(
            f"{prefix}  возвращено из чужих начислений: {report['moved']} ₽")
        self.stdout.write(
            f"{prefix}  общий аванс переназначен: {report['relabelled']} ₽")
        if report["undone"]:
            self.stdout.write(
                f"{prefix}  отменено зачётов из аванса: {report['undone']} ₽")
        for row in report["manual"]:
            self.stdout.write(self.style.WARNING(
                f"{prefix}  уч. {row.plot.number}, док. {row.doc_number}: "
                f"строка разделена вручную — проверьте раскладку сами"))
        self.stdout.write(
            f"{prefix}  Пени, начисленные до исправления, считались от неверного "
            f"остатка: снимите их (remove_penalties) и начислите заново.")
