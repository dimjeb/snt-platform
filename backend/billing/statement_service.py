"""
Загрузка выписки и разнесение поступлений по начислениям.

Разделено на два шага, и это главное решение здесь:

  import_statement — разбирает файл, сопоставляет строки с участками,
                     НО денег не трогает;
  apply_statement  — создаёт платежи по подтверждённым строкам.

Между шагами казначей смотрит, что система поняла. Автоматическое
зачисление по догадке — это чужой долг, закрытый чужими деньгами;
находится такое через месяцы и разбирается тяжело.
"""
import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .credits import add_credit
from .matching import MATCH_NONE, MATCH_PLOT, match_documents
from .models import BankStatement, BankTransaction, Charge, Payment
from .statement import parse_1c_statement

log = logging.getLogger(__name__)


class StatementImportError(Exception):
    pass


def import_statement(organization, *, raw: bytes, file_name: str, user=None):
    """Разобрать файл и сохранить строки. Деньги не трогаются."""
    from members.models import Member, Plot

    parsed = parse_1c_statement(raw, our_account=organization.bank_account)

    if organization.bank_account and parsed.account:
        ours = "".join(ch for ch in organization.bank_account if ch.isdigit())
        theirs = "".join(ch for ch in parsed.account if ch.isdigit())
        if ours != theirs:
            # Чужая выписка в чужую организацию — это платежи, разнесённые
            # не тем людям. Лучше отказать, чем разбираться потом.
            raise StatementImportError(
                f"Выписка по счёту {parsed.account}, а у организации "
                f"{organization.bank_account}. Проверьте файл."
            )

    plots = {
        p.number.strip().lower(): p
        for p in Plot.objects.filter(organization=organization)
        .prefetch_related("ownerships__member")
    }
    members = list(
        Member.objects.filter(organization=organization)
        .prefetch_related("ownerships__plot")
    )

    statement = BankStatement.objects.create(
        organization=organization,
        file_name=file_name[:255],
        account=parsed.account[:20],
        date_from=parsed.date_from,
        date_to=parsed.date_to,
        uploaded_by=user,
    )

    created, duplicates = 0, 0
    for doc, plot, member, kind in match_documents(
        parsed.documents, plots=plots, members=members
    ):
        try:
            with transaction.atomic():
                BankTransaction.objects.create(
                    organization=organization,
                    statement=statement,
                    doc_number=doc.number[:50],
                    date=doc.doc_date,
                    amount=doc.amount,
                    payer_name=doc.payer_name[:255],
                    payer_account=doc.payer_account[:34],
                    purpose=doc.purpose,
                    plot=plot,
                    member=member,
                    match_kind=kind,
                )
                created += 1
        except IntegrityError:
            # Этот платёж уже загружали — периоды выписок обычно
            # перекрываются, и это нормальная ситуация, а не ошибка.
            duplicates += 1

    return statement, {"loaded": created, "duplicates": duplicates}


def apply_statement(statement, *, user=None):
    """
    Провести выписку: создать платежи по опознанным строкам.

    Сумма строки разносится по начислениям участка от старых к новым,
    ровно как при онлайн-оплате. Переплата не теряется: остаток
    записывается в комментарий, чтобы казначей увидел и разобрался.
    """
    applied, skipped = 0, 0
    total = Decimal("0")

    with transaction.atomic():
        rows = (
            statement.transactions.select_related("plot")
            .filter(status=BankTransaction.STATUS_NEW)
            # of=("self",) обязателен: plot — необязательное поле, из-за
            # него select_related даёт LEFT JOIN, а PostgreSQL запрещает
            # FOR UPDATE на висячей стороне внешнего соединения. Без
            # уточнения «блокировать только сами строки выписки» запрос
            # падает с NotSupportedError. SQLite select_for_update
            # игнорирует целиком, поэтому на нём это не воспроизводится.
            .select_for_update(of=("self",))
        )
        for row in rows:
            if row.plot is None:
                skipped += 1
                continue

            charges = list(
                Charge.objects.filter(
                    organization=statement.organization, plot=row.plot
                )
                .select_related("charge_type", "period")
                .prefetch_related("payments")
                .order_by("period__year", "period__month", "pk")
            )
            remaining = row.amount
            for charge in charges:
                if remaining <= 0:
                    break
                debt = charge.debt
                if debt <= 0:
                    continue
                take = min(debt, remaining)
                Payment.objects.create(
                    organization=statement.organization,
                    charge=charge,
                    date=row.date,
                    amount=take,
                    method=Payment.METHOD_BANK,
                    external_ref=row.doc_number,
                    notes=f"Выписка {statement.file_name}",
                    recorded_by=user,
                )
                remaining -= take

            row.status = BankTransaction.STATUS_APPLIED
            if remaining > 0:
                # Заплатили больше, чем начислено — обычное дело, когда
                # платят вперёд за сезон. Кладём остаток на лицевой счёт
                # участка: он зачтётся сам, как только появятся новые
                # начисления. Просто оставить деньги «нигде» нельзя —
                # они чужие.
                add_credit(
                    row.plot, amount=remaining, date=row.date,
                    organization=statement.organization,
                    transaction_row=row,
                    notes=f"Переплата по выписке {statement.file_name}",
                )
                row.note = (
                    f"{remaining} ₽ зачислено авансом — начислений не хватило."
                )
                log.info(
                    "Выписка %s: по участку %s зачислено авансом %s ₽",
                    statement.pk, row.plot.number, remaining,
                )
            row.save(update_fields=["status", "note", "updated_at"])
            applied += 1
            total += row.amount - max(remaining, Decimal("0"))

        statement.status = BankStatement.STATUS_APPLIED
        statement.applied_at = timezone.now()
        statement.save(update_fields=["status", "applied_at", "updated_at"])

    return {"applied": applied, "skipped": skipped, "total": total}


def statement_summary(statement):
    rows = statement.transactions.all()
    return {
        "total_rows": rows.count(),
        "matched": rows.exclude(match_kind=MATCH_NONE).exclude(plot=None).count(),
        "by_plot": rows.filter(match_kind=MATCH_PLOT).count(),
        "unmatched": rows.filter(plot=None).count(),
        "total_amount": sum((r.amount for r in rows), Decimal("0")),
    }
