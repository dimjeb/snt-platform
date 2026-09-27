"""
Драйвер Т-Банк (Тинькофф) Эквайринг.

В отличие от ЮKassa, Т-Банк подписывает и запросы, и уведомления: подпись
Token — SHA-256 от конкатенации значений корневых параметров, отсортированных
по имени ключа, с добавлением пароля терминала. Поэтому подлинность
уведомления проверяется подписью, без обратного запроса к API.

Важно про суммы: Т-Банк принимает и возвращает копейки целым числом.
Рубли с копейками сюда передавать нельзя — платёж уйдёт в сто раз меньше.
"""
import hashlib
import hmac
import json
import logging
from decimal import Decimal

import requests

from .drivers import (
    BaseDriver,
    CreatedPayment,
    ProviderError,
    WebhookAuthError,
    WebhookEvent,
    register,
)

log = logging.getLogger(__name__)

# Статусы Т-Банка → статусы PaymentIntent.
STATUS_MAP = {
    "CONFIRMED": "succeeded",
    "AUTHORIZED": "pending",      # деньги захолдированы, но не списаны
    "REJECTED": "failed",
    "CANCELED": "canceled",
    "REVERSED": "canceled",
    "REFUNDED": "canceled",
    "NEW": "pending",
    "FORM_SHOWED": "pending",
    "DEADLINE_EXPIRED": "canceled",
}


def make_token(params: dict, password: str) -> str:
    """
    Подпись Т-Банка.

    Берутся только корневые параметры — вложенные объекты (Receipt, DATA)
    в подпись не входят. Значения сортируются по имени ключа, склеиваются
    и хешируются SHA-256. Пароль участвует как параметр Password.
    """
    payload = {
        key: value for key, value in params.items()
        if not isinstance(value, (dict, list)) and value is not None
    }
    payload.pop("Token", None)
    payload["Password"] = password
    joined = "".join(str(payload[key]) for key in sorted(payload))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@register("tbank")
class TBankDriver(BaseDriver):
    API_ROOT = "https://securepay.tinkoff.ru/v2"
    TIMEOUT = 20

    def create_payment(self, intent, return_url: str) -> CreatedPayment:
        if not self.provider.merchant_id or not self.provider.secret:
            raise ProviderError(
                "У провайдера не заданы TerminalKey или пароль терминала."
            )

        params = {
            "TerminalKey": self.provider.merchant_id,
            # Копейки целым числом: рубли здесь означали бы платёж
            # в сто раз меньше нужного.
            "Amount": int((intent.amount * 100).to_integral_value()),
            "OrderId": str(intent.pk),
            "Description": f"{intent.organization.name}: взносы"[:250],
            "SuccessURL": return_url,
            "FailURL": return_url,
        }
        params["Token"] = make_token(params, self.provider.secret)

        data = self._post("/Init", params)
        if not data.get("Success"):
            raise ProviderError(
                f"Т-Банк отклонил создание платежа: "
                f"{data.get('Message') or data.get('Details') or 'без пояснения'}"
            )

        payment_id = str(data.get("PaymentId") or "")
        if not payment_id:
            raise ProviderError("Т-Банк не вернул PaymentId.")

        return CreatedPayment(
            provider_payment_id=payment_id,
            confirmation_url=data.get("PaymentURL", ""),
            raw=data,
        )

    def parse_webhook(self, request) -> WebhookEvent:
        try:
            body = json.loads(request.body or b"{}")
        except (ValueError, TypeError):
            raise WebhookAuthError("Тело уведомления не разбирается как JSON.")

        received = body.get("Token")
        if not received:
            raise WebhookAuthError("В уведомлении нет подписи Token.")

        expected = make_token(body, self.provider.secret)
        # Сравнение постоянного времени: обычное == даёт побочный канал,
        # по которому подпись подбирается побайтно.
        if not hmac.compare_digest(str(received), expected):
            raise WebhookAuthError("Подпись уведомления Т-Банка не сошлась.")

        raw_status = str(body.get("Status", ""))
        status = STATUS_MAP.get(raw_status)
        if status is None:
            raise ProviderError(f"Неизвестный статус Т-Банка: {raw_status!r}")

        amount = None
        if body.get("Amount") is not None:
            try:
                # Обратно из копеек в рубли.
                amount = Decimal(str(body["Amount"])) / Decimal("100")
            except (ValueError, ArithmeticError):
                amount = None

        return WebhookEvent(
            provider_payment_id=str(body.get("PaymentId") or ""),
            status=status,
            amount=amount,
            raw=body,
        )

    def _post(self, path, params):
        try:
            response = requests.post(
                f"{self.API_ROOT}{path}", json=params, timeout=self.TIMEOUT
            )
        except requests.RequestException as exc:
            raise ProviderError(f"Т-Банк недоступен: {exc}") from exc

        if response.status_code >= 400:
            log.warning("Т-Банк %s -> %s: %s", path, response.status_code,
                        response.text[:500])
            raise ProviderError(f"Т-Банк отклонил запрос (HTTP {response.status_code}).")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("Т-Банк вернул не JSON.") from exc
