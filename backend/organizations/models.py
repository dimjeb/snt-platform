from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimestampModel

from .validators import (
    account_key_is_valid,
    validate_account_number,
    validate_bic,
    validate_inn,
    validate_kpp,
)


class Organization(TimestampModel):
    """СНТ — корневая сущность платформы (тенант)."""

    name = models.CharField("Название СНТ", max_length=255)
    # Короткое имя — для интерфейса, полное — для платёжных документов.
    # В QR-коде и платёжке получатель должен быть назван ровно так, как
    # в банке: «ТСН "Здоровье"» вместо полного наименования банк может
    # не пропустить.
    full_name = models.CharField(
        "Полное наименование (для платёжных документов)",
        max_length=500, blank=True,
        help_text='Как в реквизитах счёта, например: ТОВАРИЩЕСТВО '
                  'СОБСТВЕННИКОВ НЕДВИЖИМОСТИ "ЗДОРОВЬЕ"',
    )
    inn = models.CharField("ИНН", max_length=12, blank=True,
                           validators=[validate_inn])
    kpp = models.CharField("КПП", max_length=9, blank=True,
                           validators=[validate_kpp])
    ogrn = models.CharField("ОГРН", max_length=13, blank=True)
    legal_address = models.TextField("Юридический адрес", blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    email = models.EmailField("Email", blank=True)
    website = models.URLField("Сайт", blank=True)
    logo = models.ImageField("Логотип", upload_to="logos/", blank=True, null=True)

    # Настройки
    timezone = models.CharField("Часовой пояс", max_length=50, default="Asia/Irkutsk")
    # Периодичность членских взносов: yearly / quarterly
    fee_period = models.CharField(
        "Периодичность взносов",
        max_length=10,
        choices=[("yearly", "Ежегодно"), ("quarterly", "Ежеквартально")],
        default="yearly",
    )
    is_active = models.BooleanField("Активна", default=True)

    # ─── Банковские реквизиты: нужны для QR-кода оплаты ──────────────────
    bank_account = models.CharField(
        "Расчётный счёт", max_length=20, blank=True,
        validators=[validate_account_number],
    )
    bank_name = models.CharField("Банк", max_length=255, blank=True)
    bank_bic = models.CharField("БИК", max_length=9, blank=True,
                                validators=[validate_bic])
    bank_corr_account = models.CharField(
        "Корреспондентский счёт", max_length=20, blank=True,
        validators=[validate_account_number],
    )

    class Meta:
        verbose_name = "Организация (СНТ)"
        verbose_name_plural = "Организации (СНТ)"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """
        Сверяем контрольные ключи счетов с БИК.

        По отдельности номер счёта и БИК выглядят правдоподобно, а вместе
        могут не сходиться — именно так выявляется опечатка. Проверяем
        только когда заполнены обе части: частично заполненные реквизиты
        это нормальное промежуточное состояние.
        """
        errors = {}
        if self.bank_account and self.bank_bic:
            if not account_key_is_valid(
                self.bank_account, self.bank_bic, is_correspondent=False
            ):
                errors["bank_account"] = (
                    "Контрольный ключ расчётного счёта не сходится с БИК. "
                    "Проверьте обе цифры — где-то опечатка."
                )
        if self.bank_corr_account and self.bank_bic:
            if not account_key_is_valid(
                self.bank_corr_account, self.bank_bic, is_correspondent=True
            ):
                errors["bank_corr_account"] = (
                    "Контрольный ключ корреспондентского счёта не сходится "
                    "с БИК. Проверьте обе цифры."
                )
        if errors:
            raise ValidationError(errors)

    @property
    def payment_name(self):
        """Получатель платежа: полное наименование, если оно задано."""
        return self.full_name or self.name

    @property
    def has_bank_details(self):
        """Хватает ли реквизитов, чтобы построить платёжный QR."""
        return all([
            self.payment_name, self.bank_account, self.bank_name,
            self.bank_bic, self.bank_corr_account,
        ])
