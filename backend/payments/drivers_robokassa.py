"""
Драйвер Робокассы.

Робокасса устроена иначе остальных: платёж не создаётся запросом к API,
плательщик просто уходит на их форму по собранной ссылке. Поэтому
provider_payment_id — это наш собственный номер счёта (InvId), а не выданный
провайдером идентификатор.

Два пароля не взаимозаменяемы:
  Пароль №1 подписывает ссылку на оплату
  Пароль №2 проверяет уведомление (ResultURL)
Перепутать их — значит либо не пускать плательщиков, либо принимать
поддельные уведомления. Второй хранится в secret2.

Подпись — MD5, так устроен их протокол. Криптостойкость здесь обеспечивается
не алгоритмом, а секретностью пароля.
"""
import hashlib
import hmac
from decimal import Decimal
from urllib.parse import urlencode

from .drivers import (
    BaseDriver,
    CreatedPayment,
    ProviderError,
    WebhookAuthError,
    WebhookEvent,
    register,
)


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


@register("robokassa")
class RobokassaDriver(BaseDriver):
    PAY_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"

    def create_payment(self, intent, return_url: str) -> CreatedPayment:
        if not self.provider.merchant_id or not self.provider.secret:
            raise ProviderError(
                "У провайдера не заданы логин магазина или Пароль №1."
            )

        login = self.provider.merchant_id
        out_sum = f"{intent.amount:.2f}"
        inv_id = str(intent.pk)

        signature = _md5(f"{login}:{out_sum}:{inv_id}:{self.provider.secret}")
        params = {
            "MerchantLogin": login,
            "OutSum": out_sum,
            "InvId": inv_id,
            "Description": f"{intent.organization.name}: взносы"[:100],
            "SignatureValue": signature,
            "Culture": "ru",
        }
        if self.provider.test_mode:
            params["IsTest"] = "1"

        return CreatedPayment(
            # Робокасса не выдаёт свой идентификатор заранее: счётом
            # служит наш InvId, по нему же придёт уведомление.
            provider_payment_id=inv_id,
            confirmation_url=f"{self.PAY_URL}?{urlencode(params)}",
            raw={"params": {k: v for k, v in params.items()
                            if k != "SignatureValue"}},
        )

    def parse_webhook(self, request) -> WebhookEvent:
        data = request.POST if request.method == "POST" else request.GET
        out_sum = data.get("OutSum")
        inv_id = data.get("InvId")
        received = (data.get("SignatureValue") or "").lower()

        if not (out_sum and inv_id and received):
            raise WebhookAuthError(
                "В уведомлении Робокассы нет OutSum, InvId или подписи."
            )

        if not self.provider.secret2:
            raise ProviderError(
                "Не задан Пароль №2 — проверить уведомление Робокассы нечем."
            )

        expected = _md5(f"{out_sum}:{inv_id}:{self.provider.secret2}")
        if not hmac.compare_digest(received, expected):
            raise WebhookAuthError("Подпись уведомления Робокассы не сошлась.")

        try:
            amount = Decimal(str(out_sum))
        except (ValueError, ArithmeticError):
            amount = None

        # ResultURL Робокасса вызывает только по факту успешной оплаты:
        # уведомлений об отмене там нет, отменённое просто не приходит.
        return WebhookEvent(
            provider_payment_id=str(inv_id),
            status="succeeded",
            amount=amount,
            raw=dict(data.items()),
        )
