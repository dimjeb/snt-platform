"""
Перенос оплаты между начислениями одного члена товарищества.

Нужен, когда деньги легли не туда: человек платил целевой, а платёж
закрыл членский; казначей при ручном вводе выбрал не ту строку.

Как устроено: платёж не правится и не удаляется — это история денег,
и правка задним числом потом не объясняется. Вместо этого пишутся два
новых платежа способом «перенос между начислениями»: минус на исходном
начислении и плюс на целевом, с общей меткой и комментарием, кто и
почему перенёс. Сумма по товариществу не меняется, лента остаётся
правдивой, а перенос можно отменить таким же переносом обратно.
"""
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Charge, Payment


class TransferError(Exception):
    """Перенос невозможен — текст объясняет почему."""


def _owner_ids(charge):
    """Кто платит по этому начислению: член из поля или текущие владельцы участка."""
    if charge.member_id:
        return {charge.member_id}
    return {
        o.member_id for o in charge.plot.ownerships.all() if o.date_to is None
    }


def same_payer(source, target):
    """
    Платит ли за оба начисления один и тот же человек (или группа).

    Тот же участок — да, если только оба не личные взносы разных
    совладельцев. Разные участки — да, если у них общий текущий владелец.
    """
    if source.organization_id != target.organization_id:
        return False
    if (source.member_id and target.member_id
            and source.member_id != target.member_id):
        return False
    if source.plot_id == target.plot_id:
        return True
    return bool(_owner_ids(source) & _owner_ids(target))


def transfer_targets(source):
    """
    Начисления, на которые можно перенести оплату с source.

    Того же товарищества, того же плательщика (общий участок или общий
    текущий владелец), с непогашенным остатком. Пени сюда тоже входят:
    перенести на них деньги — законная операция.
    """
    candidates = (
        Charge.objects.filter(organization=source.organization)
        .exclude(pk=source.pk)
        .select_related("charge_type", "period", "plot")
        .prefetch_related("payments", "plot__ownerships")
    )
    result = []
    for charge in candidates:
        if charge.debt > 0 and same_payer(source, charge):
            result.append(charge)
    return result


def transfer_payment(source, target, amount, *, user=None, reason=""):
    """Перенести amount ₽ оплаты с начисления source на target."""
    amount = Decimal(amount)
    if amount <= 0:
        raise TransferError("Сумма переноса должна быть больше нуля.")

    with transaction.atomic():
        # Блокируем обе строки: два казначея, переносящие с одного
        # начисления одновременно, иначе увели бы одни деньги дважды.
        locked = {
            c.pk: c for c in Charge.objects.select_for_update()
            .filter(pk__in=[source.pk, target.pk])
        }
        source, target = locked.get(source.pk), locked.get(target.pk)
        if source is None or target is None:
            raise TransferError("Начисление не найдено.")
        if not same_payer(source, target):
            raise TransferError(
                "Переносить можно только между начислениями одного "
                "плательщика: того же участка или того же владельца."
            )
        if amount > source.paid_amount:
            raise TransferError(
                f"По исходному начислению оплачено {source.paid_amount} ₽ — "
                f"перенести {amount} ₽ нельзя."
            )
        if amount > target.debt:
            raise TransferError(
                f"Остаток долга по целевому начислению {target.debt} ₽ — "
                f"перенос {amount} ₽ создал бы переплату."
            )

        mark = f"transfer-{uuid.uuid4().hex[:12]}"
        today = timezone.localdate()
        note = (f"Перенос {amount} ₽: «{source.charge_type.name}» "
                f"({source.period}) → «{target.charge_type.name}» "
                f"({target.period})")
        if reason:
            note += f". Причина: {reason}"
        common = dict(organization=source.organization, date=today,
                      method=Payment.METHOD_TRANSFER, external_ref=mark,
                      notes=note[:2000], recorded_by=user)
        out = Payment.objects.create(charge=source, amount=-amount, **common)
        into = Payment.objects.create(charge=target, amount=amount, **common)
    return out, into
