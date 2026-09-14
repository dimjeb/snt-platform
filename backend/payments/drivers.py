"""
Драйверы платёжных провайдеров.

Провайдеры отличаются двумя вещами: как создать платёж и как доказать,
что вебхук пришёл действительно от них. Всё остальное — разнесение по
начислениям, идемпотентность, создание Payment — общее и живёт в services.

Добавить провайдера = написать класс с двумя методами и повесить
@register("ключ"). Ни модели, ни вьюхи при этом не меняются.

Ключи регистрации совпадают с PaymentProvider.KIND_*. Строки, а не ссылки
на модель, намеренно: иначе получается circular import, а тащить сюда
модели ради двух констант незачем.
"""
from dataclasses import dataclass, field
from decimal import Decimal


# --------------------------------------------------------------------------- #
#  Общие типы                                                                  #
# --------------------------------------------------------------------------- #

@dataclass
class CreatedPayment:
    """Результат создания платежа на стороне провайдера."""

    provider_payment_id: str
    confirmation_url: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """Разобранное событие вебхука, приведённое к общему виду."""

    provider_payment_id: str
    # succeeded / canceled / failed / pending — терминология PaymentIntent
    status: str
    amount: Decimal | None = None
    raw: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Провайдер отказал или ответил неожиданным образом."""


class WebhookAuthError(Exception):
    """Вебхук не прошёл проверку подлинности — обрабатывать его нельзя."""


# --------------------------------------------------------------------------- #
#  Реестр                                                                      #
# --------------------------------------------------------------------------- #

DRIVERS = {}


def register(kind):
    """Регистрирует драйвер под ключ вида провайдера (PaymentProvider.KIND_*)."""
    def wrapper(cls):
        DRIVERS[kind] = cls
        return cls
    return wrapper


def get_driver(provider):
    """Драйвер для провайдера; ProviderError, если вид не поддержан."""
    driver_cls = DRIVERS.get(provider.kind)
    if driver_cls is None:
        raise ProviderError(
            f"Провайдер «{provider.get_kind_display()}» пока не поддержан."
        )
    return driver_cls(provider)


# --------------------------------------------------------------------------- #
#  Драйверы                                                                    #
# --------------------------------------------------------------------------- #

class BaseDriver:
    """Общий интерфейс драйвера."""

    def __init__(self, provider):
        self.provider = provider

    def create_payment(self, intent, return_url: str) -> CreatedPayment:
        """Создать платёж у провайдера и вернуть ссылку для плательщика."""
        raise NotImplementedError

    def parse_webhook(self, request) -> WebhookEvent:
        """
        Проверить подлинность вебхука и привести его к WebhookEvent.

        Обязана поднять WebhookAuthError, если подлинность не доказана:
        необработанный вебхук безопаснее, чем платёж, зачисленный по
        чужому запросу.
        """
        raise NotImplementedError


@register("manual")
class ManualDriver(BaseDriver):
    """
    Провайдер без онлайн-оплаты: казначей заносит платежи руками.

    Создать платёж через него нельзя — это не заглушка «на потом», а явный
    способ сказать «в этом СНТ онлайн-оплаты нет». Попытка провести платёж
    падает заметно, а не оставляет висящее намерение.
    """

    def create_payment(self, intent, return_url: str) -> CreatedPayment:
        raise ProviderError(
            "У этого СНТ не подключена онлайн-оплата: провайдер работает "
            "в ручном режиме, платежи заносит казначей."
        )

    def parse_webhook(self, request) -> WebhookEvent:
        raise WebhookAuthError("Ручной провайдер не принимает вебхуки.")
