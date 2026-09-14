"""
Бизнес-логика платежей.

Здесь деньги, поэтому два правила важнее удобства:

1. Payment создаётся только при подтверждении провайдером. Член СНТ может
   создать намерение, но не платёж — иначе любой пометил бы долг оплаченным.
2. Подтверждение идемпотентно. Провайдеры повторяют вебхуки при сетевых
   сбоях и по таймауту; повторная доставка не должна зачислять деньги дважды.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


class PaymentError(Exception):
    """Платёж провести нельзя — с понятной причиной для пользователя."""


def build_debt_allocation(charges):
    """
    Раскладывает долг по начислениям: от старых к новым.

    Возвращает список пар (начисление, сумма к оплате), пропуская всё,
    что уже закрыто. Порядок важен: гасить сначала старое — обычная
    практика и меньше поводов для спора.
    """
    allocation = []
    for charge in charges:
        debt = charge.debt
        if debt > 0:
            allocation.append((charge, debt))
    return allocation


@transaction.atomic
def create_intent(*, organization, provider, allocation, member=None,
                  created_by=None, idempotency_key):
    """
    Создаёт намерение оплаты и строки разнесения.

    allocation — список пар (начисление, сумма). Сумма намерения считается
    из строк, а не приходит от клиента: клиенту нельзя доверять выбор суммы,
    иначе долг закрывался бы копеечным платежом.
    """
    from .models import PaymentIntent, PaymentIntentItem

    if not allocation:
        raise PaymentError("Нечего оплачивать: задолженности нет.")

    # Повтор по тому же ключу возвращает прежнее намерение, а не заводит
    # второе: две вкладки или двойное нажатие не должны создавать два платежа.
    existing = PaymentIntent.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        return existing

    total = sum((amount for _, amount in allocation), Decimal("0"))
    if total <= 0:
        raise PaymentError("Сумма к оплате должна быть больше нуля.")

    intent = PaymentIntent.objects.create(
        organization=organization,
        provider=provider,
        member=member,
        amount=total,
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    PaymentIntentItem.objects.bulk_create([
        PaymentIntentItem(intent=intent, charge=charge, amount=amount)
        for charge, amount in allocation
    ])
    return intent


def confirm_intent(intent_id, *, event=None):
    """
    Подтверждает оплату: помечает намерение и создаёт Payment по каждой строке.

    Идемпотентна. Строка намерения блокируется select_for_update, поэтому
    два одновременных вебхука не создадут два комплекта платежей: второй
    дождётся первого и увидит уже подтверждённое намерение.

    Возвращает (intent, created) — created False, если подтверждение уже
    было обработано раньше.
    """
    from billing.models import Payment
    from .models import PaymentIntent

    with transaction.atomic():
        intent = (
            PaymentIntent.objects
            .select_for_update()
            .select_related("provider")
            .get(pk=intent_id)
        )

        if intent.status == PaymentIntent.STATUS_SUCCEEDED:
            # Повторная доставка вебхука — нормальная ситуация, не ошибка.
            if event is not None:
                intent.last_event = event
                intent.save(update_fields=["last_event", "updated_at"])
            return intent, False

        method = _method_for(intent.provider)
        today = timezone.localdate()

        payments = [
            Payment(
                organization=intent.organization,
                charge=item.charge,
                date=today,
                amount=item.amount,
                method=method,
                external_ref=intent.provider_payment_id,
                notes=f"Онлайн-оплата, намерение #{intent.pk}",
            )
            for item in intent.items.select_related("charge")
        ]
        Payment.objects.bulk_create(payments)

        intent.status = PaymentIntent.STATUS_SUCCEEDED
        intent.paid_at = timezone.now()
        intent.error_message = ""
        if event is not None:
            intent.last_event = event
        intent.save(update_fields=[
            "status", "paid_at", "error_message", "last_event", "updated_at"
        ])
        return intent, True


def fail_intent(intent_id, *, status, reason="", event=None):
    """Помечает намерение отменённым или ошибочным. Payment не создаётся."""
    from .models import PaymentIntent

    with transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(pk=intent_id)
        # Уже оплаченное намерение не отменяем: деньги получены, и отмена
        # здесь означала бы расхождение с реальностью.
        if intent.status == PaymentIntent.STATUS_SUCCEEDED:
            return intent, False
        intent.status = status
        intent.error_message = (reason or "")[:500]
        if event is not None:
            intent.last_event = event
        intent.save(update_fields=[
            "status", "error_message", "last_event", "updated_at"
        ])
        return intent, True


def _method_for(provider):
    """Способ оплаты для записи Payment по виду провайдера."""
    from billing.models import Payment
    from .models import PaymentProvider

    if provider.kind == PaymentProvider.KIND_SBP:
        return Payment.METHOD_SBP
    # ЮKassa и Т-Банк дают и карты, и СБП; какой именно способ выбрал
    # плательщик, видно в last_event. По умолчанию считаем картой.
    return Payment.METHOD_CARD
