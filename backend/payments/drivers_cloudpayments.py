"""
Драйвер CloudPayments.

Подлинность уведомления подтверждается заголовком Content-HMAC:
HMAC-SHA256 от СЫРОГО тела запроса на API secret, в base64. Считать подпись
нужно именно от неразобранного тела — пересобранный из словаря JSON даст
другие байты (порядок ключей, пробелы) и подпись не сойдётся.

Реквизиты: public id магазина в merchant_id, API secret в secret2. Первый
секрет здесь не используется, но валидация модели его требует — кладите
туда тот же API secret либо оставьте пометку в примечании.
"""
import base64
import hashlib
import hmac
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

STATUS_MAP = {
    "Completed": "succeeded",
    "Authorized": "pending",
    "Cancelled": "canceled",
    "Declined": "failed",
}


@register("cloudpayments")
class CloudPaymentsDriver(BaseDriver):
    API_ROOT = "https://api.cloudpayments.ru"
    TIMEOUT = 20

    def _api_secret(self) -> str:
        """API secret: основной — во втором поле, с откатом на первое."""
        return self.provider.secret2 or self.provider.secret

    def create_payment(self, intent, return_url: str) -> CreatedPayment:
        if not self.provider.merchant_id or not self._api_secret():
            raise ProviderError(
                "У провайдера не заданы public id или API secret CloudPayments."
            )

        payload = {
            "Amount": float(intent.amount),
            "Currency": "RUB",
            "Description": f"{intent.organization.name}: взносы"[:250],
            "InvoiceId": str(intent.pk),
            "SuccessRedirectUrl": return_url,
            "FailRedirectUrl": return_url,
            "JsonData": {"intent_id": str(intent.pk)},
        }
        data = self._post("/orders/create", payload)

        if not data.get("Success"):
            raise ProviderError(
                f"CloudPayments отклонил создание счёта: "
                f"{data.get('Message') or 'без пояснения'}"
            )
        model = data.get("Model") or {}
        order_id = str(model.get("Id") or intent.pk)
        return CreatedPayment(
            provider_payment_id=order_id,
            confirmation_url=model.get("Url", ""),
            raw=data,
        )

    def parse_webhook(self, request) -> WebhookEvent:
        received = request.headers.get("Content-HMAC") or request.headers.get(
            "X-Content-HMAC"
        )
        if not received:
            raise WebhookAuthError("В уведомлении нет заголовка Content-HMAC.")

        secret = self._api_secret()
        if not secret:
            raise ProviderError(
                "Не задан API secret — проверить уведомление CloudPayments нечем."
            )

        # Подпись считается от сырого тела: пересобранный JSON даст другие байты.
        digest = hmac.new(
            secret.encode("utf-8"), request.body or b"", hashlib.sha256
        ).digest()
        expected = base64.b64encode(digest).decode("ascii")
        if not hmac.compare_digest(received, expected):
            raise WebhookAuthError("Подпись уведомления CloudPayments не сошлась.")

        data = request.POST.dict() if request.POST else {}
        if not data:
            try:
                data = json.loads(request.body or b"{}")
            except (ValueError, TypeError):
                data = {}

        raw_status = str(data.get("Status", "Completed"))
        status = STATUS_MAP.get(raw_status)
        if status is None:
            raise ProviderError(f"Неизвестный статус CloudPayments: {raw_status!r}")

        amount = None
        if data.get("Amount") is not None:
            try:
                amount = Decimal(str(data["Amount"]))
            except (ValueError, ArithmeticError):
                amount = None

        return WebhookEvent(
            provider_payment_id=str(data.get("InvoiceId") or data.get("TransactionId") or ""),
            status=status,
            amount=amount,
            raw=data,
        )

    def _post(self, path, payload):
        try:
            response = requests.post(
                f"{self.API_ROOT}{path}",
                json=payload,
                auth=HTTPBasicAuth(self.provider.merchant_id, self._api_secret()),
                timeout=self.TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"CloudPayments недоступен: {exc}") from exc

        if response.status_code >= 400:
            log.warning("CloudPayments %s -> %s: %s", path,
                        response.status_code, response.text[:500])
            raise ProviderError(
                f"CloudPayments отклонил запрос (HTTP {response.status_code})."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("CloudPayments вернул не JSON.") from exc
