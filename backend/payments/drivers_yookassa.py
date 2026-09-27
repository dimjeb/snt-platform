"""
Драйвер ЮKassa.

Тестовый и боевой режим различаются только реквизитами магазина: адрес API
один и тот же, отдельный тестовый магазин выдаётся в личном кабинете.
Поэтому флаг test_mode у провайдера — пометка для людей, а не переключатель
адреса.

Про подлинность вебхука. ЮKassa уведомления НЕ подписывает: в документации
предлагается сверять исходящий IP со списком их сетей. Список меняется, его
нужно поддерживать, и ошибка в нём либо ломает приём платежей, либо
открывает дыру. Поэтому здесь выбран другой путь: телу уведомления не
доверяем вовсе, берём из него только идентификатор платежа и перезапрашиваем
состояние у API своими ключами. Подделать уведомление бессмысленно — статус
всё равно придёт от ЮKassa. Проверку по IP при желании можно добавить
сверху как второй рубеж, но безопасность на неё не завязана.
"""
import json
import logging
from decimal import Decimal

import requests
from requests.auth import HTTPBasicAuth

from .drivers import (
    BaseDriver,
    CreatedPayment,
    ProviderError,
    WebhookAuthError,
    WebhookEvent,
    register,
)

log = logging.getLogger(__name__)

# Статусы ЮKassa → статусы PaymentIntent.
# waiting_for_capture возможен только при двухстадийной оплате; мы просим
# capture=true, но обрабатываем его как «ещё не деньги» на случай, если
# магазин настроен иначе.
STATUS_MAP = {
    "succeeded": "succeeded",
    "canceled": "canceled",
    "pending": "pending",
    "waiting_for_capture": "pending",
}


@register("yookassa")
class YooKassaDriver(BaseDriver):
    API_ROOT = "https://api.yookassa.ru/v3"
    TIMEOUT = 20  # секунд: платёжный путь не должен висеть бесконечно

    # ------------------------------------------------------------------ #
    #  Создание платежа                                                   #
    # ------------------------------------------------------------------ #

    def create_payment(self, intent, return_url: str) -> CreatedPayment:
        payload = {
            "amount": {"value": f"{intent.amount:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": self._description(intent),
            # metadata возвращается в уведомлении и в ответе API — по ней
            # находим намерение, даже если provider_payment_id не успел
            # сохраниться из-за обрыва связи.
            "metadata": {
                "intent_id": str(intent.pk),
                "organization_id": str(intent.organization_id),
            },
        }
        data = self._request(
            "POST", "/payments", payload,
            # Ключ идемпотентности намерения передаём и в ЮKassa: повторный
            # запрос вернёт тот же платёж, а не создаст второй.
            idempotence_key=intent.idempotency_key,
        )

        payment_id = data.get("id")
        if not payment_id:
            raise ProviderError("ЮKassa не вернула идентификатор платежа.")

        confirmation = data.get("confirmation") or {}
        return CreatedPayment(
            provider_payment_id=payment_id,
            confirmation_url=confirmation.get("confirmation_url", ""),
            raw=data,
        )

    # ------------------------------------------------------------------ #
    #  Вебхук                                                             #
    # ------------------------------------------------------------------ #

    def parse_webhook(self, request) -> WebhookEvent:
        try:
            body = json.loads(request.body or b"{}")
        except (ValueError, TypeError):
            raise WebhookAuthError("Тело уведомления не разбирается как JSON.")

        obj = body.get("object") or {}
        payment_id = obj.get("id")
        if not payment_id:
            raise WebhookAuthError("В уведомлении нет идентификатора платежа.")

        # Здесь и заключается проверка подлинности: состояние платежа
        # берём не из присланного тела, а из API по своим ключам.
        actual = self._request("GET", f"/payments/{payment_id}")

        raw_status = actual.get("status", "")
        status = STATUS_MAP.get(raw_status)
        if status is None:
            raise ProviderError(f"Неизвестный статус платежа ЮKassa: {raw_status!r}")

        amount = None
        value = (actual.get("amount") or {}).get("value")
        if value is not None:
            try:
                amount = Decimal(str(value))
            except (ValueError, ArithmeticError):
                amount = None

        return WebhookEvent(
            provider_payment_id=payment_id,
            status=status,
            amount=amount,
            raw=actual,
        )

    # ------------------------------------------------------------------ #
    #  Транспорт                                                          #
    # ------------------------------------------------------------------ #

    def _description(self, intent) -> str:
        """Назначение платежа — его видит плательщик и казначей в выписке."""
        org = intent.organization.name
        if intent.member_id:
            return f"{org}: взносы, {intent.member}"[:128]
        return f"{org}: взносы"[:128]

    def _request(self, method: str, path: str, payload=None, idempotence_key=None):
        if not self.provider.merchant_id or not self.provider.secret:
            raise ProviderError(
                "У провайдера не заданы shopId или секретный ключ. "
                "Проверьте настройки СНТ в админке."
            )

        headers = {"Content-Type": "application/json"}
        if idempotence_key:
            headers["Idempotence-Key"] = idempotence_key

        try:
            response = requests.request(
                method,
                f"{self.API_ROOT}{path}",
                json=payload,
                headers=headers,
                auth=HTTPBasicAuth(self.provider.merchant_id, self.provider.secret),
                timeout=self.TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"ЮKassa недоступна: {exc}") from exc

        if response.status_code >= 400:
            # Тело ошибки логируем, но пользователю его не показываем:
            # там бывают детали интеграции.
            log.warning(
                "ЮKassa %s %s -> %s: %s",
                method, path, response.status_code, response.text[:500],
            )
            raise ProviderError(
                f"ЮKassa отклонила запрос (HTTP {response.status_code})."
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("ЮKassa вернула не JSON.") from exc
