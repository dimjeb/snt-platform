from django.core.exceptions import ValidationError
from django.db import models

from core.models import OrgModel

from .crypto import decrypt, encrypt


class PaymentProvider(OrgModel):
    """
    Платёжный провайдер конкретного СНТ.

    У каждого товарищества свой расчётный счёт и свой мерчант, поэтому
    провайдер настраивается на уровне организации, а не платформы.
    Одно СНТ может держать несколько: например, ЮKassa для приёма взносов
    и отдельный доступ к банку для обязательных платежей.
    """

    KIND_YOOKASSA = "yookassa"
    KIND_TBANK = "tbank"
    KIND_ROBOKASSA = "robokassa"
    KIND_CLOUDPAYMENTS = "cloudpayments"
    KIND_SBP = "sbp"
    KIND_MANUAL = "manual"

    KIND_CHOICES = [
        (KIND_YOOKASSA, "ЮKassa"),
        (KIND_TBANK, "Т-Банк Эквайринг"),
        (KIND_ROBOKASSA, "Робокасса"),
        (KIND_CLOUDPAYMENTS, "CloudPayments"),
        (KIND_SBP, "СБП напрямую через банк"),
        (KIND_MANUAL, "Вручную (без онлайн-оплаты)"),
    ]

    DIRECTION_IN = "in"
    DIRECTION_OUT = "out"

    DIRECTION_CHOICES = [
        (DIRECTION_IN, "Приём взносов от членов"),
        (DIRECTION_OUT, "Обязательные платежи товарищества"),
    ]

    title = models.CharField(
        "Название", max_length=120,
        help_text="Как показывать в интерфейсе, например «ЮKassa — взносы».",
    )
    kind = models.CharField("Провайдер", max_length=20, choices=KIND_CHOICES)
    direction = models.CharField(
        "Направление", max_length=3, choices=DIRECTION_CHOICES, default=DIRECTION_IN,
        help_text="Приём денег от членов или оплата налогов и обязательных платежей.",
    )

    merchant_id = models.CharField(
        "Идентификатор мерчанта", max_length=120, blank=True,
        help_text="shopId у ЮKassa, TerminalKey у Т-Банка.",
    )
    # Секреты хранятся зашифрованными; работать через свойства secret / secret2.
    secret_encrypted = models.TextField("Секретный ключ (шифрованный)", blank=True)
    # Второй ключ нужен не всем: у Робокассы это Пароль №2 для проверки
    # уведомлений, у CloudPayments — API secret в паре с public id.
    # У ЮKassa и Т-Банка не используется.
    secret2_encrypted = models.TextField(
        "Дополнительный ключ (шифрованный)", blank=True
    )

    test_mode = models.BooleanField(
        "Тестовый режим", default=True,
        help_text="Платежи не настоящие. Снимать только после проверки приёма денег.",
    )
    is_active = models.BooleanField("Активен", default=True)
    is_default = models.BooleanField(
        "Основной", default=False,
        help_text="Используется по умолчанию для своего направления.",
    )
    notes = models.TextField("Примечания", blank=True)

    class Meta:
        verbose_name = "Платёжный провайдер"
        verbose_name_plural = "Платёжные провайдеры"
        ordering = ["organization", "direction", "-is_default", "title"]
        constraints = [
            # Основной провайдер в каждом направлении может быть только один,
            # иначе непонятно, через кого проводить платёж.
            models.UniqueConstraint(
                fields=["organization", "direction"],
                condition=models.Q(is_default=True),
                name="unique_default_provider_per_direction",
            )
        ]

    def __str__(self):
        mode = " [тест]" if self.test_mode else ""
        return f"{self.title} ({self.get_kind_display()}){mode}"

    # ------------------------------------------------------------------ #
    #  Секрет                                                             #
    # ------------------------------------------------------------------ #

    @property
    def secret(self) -> str:
        """Расшифрованный секретный ключ. Пустая строка, если не задан."""
        return decrypt(self.secret_encrypted)

    @secret.setter
    def secret(self, value: str):
        self.secret_encrypted = encrypt(value or "")

    @property
    def secret_is_set(self) -> bool:
        """Задан ли секрет и читается ли он текущим ключом шифрования."""
        return bool(self.secret)

    @property
    def secret2(self) -> str:
        """Второй ключ: Пароль №2 у Робокассы, API secret у CloudPayments."""
        return decrypt(self.secret2_encrypted)

    @secret2.setter
    def secret2(self, value: str):
        self.secret2_encrypted = encrypt(value or "")

    @property
    def secret2_is_set(self) -> bool:
        return bool(self.secret2)

    @property
    def needs_second_secret(self) -> bool:
        """Провайдеры, которым второй ключ обязателен."""
        return self.kind in (self.KIND_ROBOKASSA, self.KIND_CLOUDPAYMENTS)

    # ------------------------------------------------------------------ #
    #  Готовность к работе                                                #
    # ------------------------------------------------------------------ #

    @property
    def is_configured(self) -> bool:
        """
        Можно ли проводить через него платежи.

        Ручной способ реквизитов не требует — он и означает «онлайн-оплаты
        нет, казначей заносит платежи руками».
        """
        if self.kind == self.KIND_MANUAL:
            return True
        if not (self.merchant_id and self.secret_is_set):
            return False
        if self.needs_second_secret and not self.secret2_is_set:
            return False
        return True

    def clean(self):
        if self.kind != self.KIND_MANUAL and self.is_active:
            if not self.merchant_id:
                raise ValidationError(
                    {"merchant_id": "Для онлайн-оплаты нужен идентификатор мерчанта."}
                )
            if not self.secret_is_set:
                raise ValidationError(
                    {"secret_encrypted": "Для онлайн-оплаты нужен секретный ключ."}
                )
            if self.needs_second_secret and not self.secret2_is_set:
                raise ValidationError({
                    "secret2_encrypted": (
                        "Этому провайдеру нужен второй ключ: Пароль №2 "
                        "у Робокассы, API secret у CloudPayments."
                    )
                })


class PaymentIntent(OrgModel):
    """
    Намерение оплатить: член нажал «оплатить», платёж ещё не подтверждён.

    Ключевое разделение: запись Payment создаётся ТОЛЬКО когда провайдер
    подтвердил поступление денег. Член может создать намерение, но не может
    создать платёж — иначе любой пометил бы свой долг оплаченным.
    """

    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_CANCELED = "canceled"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает оплаты"),
        (STATUS_SUCCEEDED, "Оплачено"),
        (STATUS_CANCELED, "Отменено"),
        (STATUS_FAILED, "Ошибка"),
    ]

    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT, related_name="intents",
        verbose_name="Провайдер",
    )
    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="payment_intents",
        null=True, blank=True, verbose_name="Плательщик",
    )
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    status = models.CharField(
        "Статус", max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    # Ключ идемпотентности: защищает от двойного списания, если член
    # дважды нажал кнопку или клиент повторил запрос.
    idempotency_key = models.CharField("Ключ идемпотентности", max_length=64)
    # Идентификатор платежа на стороне провайдера — по нему находим
    # намерение, когда приходит вебхук.
    provider_payment_id = models.CharField(
        "ID платежа у провайдера", max_length=120, blank=True, db_index=True
    )
    confirmation_url = models.URLField("Ссылка на оплату", max_length=500, blank=True)

    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_payment_intents",
    )
    paid_at = models.DateTimeField("Оплачено", null=True, blank=True)
    # Последнее событие от провайдера — чтобы разбирать спорные случаи
    # по факту, а не по памяти.
    last_event = models.JSONField("Последнее событие провайдера", null=True, blank=True)
    error_message = models.CharField("Причина ошибки", max_length=500, blank=True)

    class Meta:
        verbose_name = "Намерение оплаты"
        verbose_name_plural = "Намерения оплаты"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="unique_intent_idempotency_key",
            ),
        ]

    def __str__(self):
        return f"{self.amount} ₽ / {self.get_status_display()}"

    @property
    def is_final(self) -> bool:
        """Достигло ли намерение конечного состояния."""
        return self.status in (self.STATUS_SUCCEEDED, self.STATUS_CANCELED,
                               self.STATUS_FAILED)


class PaymentIntentItem(models.Model):
    """
    Разнесение суммы намерения по конкретным начислениям.

    Отдельная сущность, потому что один платёж может закрывать несколько
    начислений: «оплатить весь долг» — это членский взнос плюс целевой
    плюс электроэнергия. По каждой строке при подтверждении создаётся
    свой Payment, иначе долг по отдельному начислению не сойдётся.
    """

    intent = models.ForeignKey(
        PaymentIntent, on_delete=models.CASCADE, related_name="items"
    )
    charge = models.ForeignKey(
        "billing.Charge", on_delete=models.PROTECT, related_name="intent_items"
    )
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Строка намерения оплаты"
        verbose_name_plural = "Строки намерения оплаты"
        constraints = [
            models.UniqueConstraint(
                fields=["intent", "charge"], name="unique_charge_per_intent"
            ),
        ]

    def __str__(self):
        return f"{self.charge} — {self.amount} ₽"
