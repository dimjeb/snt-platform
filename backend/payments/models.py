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
    KIND_SBP = "sbp"
    KIND_MANUAL = "manual"

    KIND_CHOICES = [
        (KIND_YOOKASSA, "ЮKassa"),
        (KIND_TBANK, "Т-Банк Эквайринг"),
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
    # Секрет хранится зашифрованным; работать с ним через свойство secret.
    secret_encrypted = models.TextField("Секретный ключ (шифрованный)", blank=True)

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
        return bool(self.merchant_id) and self.secret_is_set

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
