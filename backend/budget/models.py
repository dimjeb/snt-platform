"""
Приходно-расходная смета, финансово-экономическое обоснование и
фактические расходы товарищества.

По 217-ФЗ (ст. 14 ч. 8) размер взносов определяется сметой и
финансово-экономическим обоснованием, которые утверждает общее
собрание. Здесь они ведутся как данные, а документы для собрания и
ревизионной комиссии собираются из них (budget/documents.py).
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import OrgModel


class Budget(OrgModel):
    """Смета на год."""

    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Черновик"),
        (STATUS_APPROVED, "Утверждена"),
    ]
    BASIS_FLAT = "flat"
    BASIS_PER_SOTKA = "per_sotka"
    BASIS_CHOICES = [
        (BASIS_FLAT, "Поровну с участка"),
        (BASIS_PER_SOTKA, "По площади (за сотку)"),
    ]

    year = models.PositiveIntegerField("Год")
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES,
                              default=STATUS_DRAFT)
    basis = models.CharField("Как делится членский взнос", max_length=10,
                             choices=BASIS_CHOICES, default=BASIS_FLAT)
    approved_at = models.DateField("Дата общего собрания", null=True, blank=True)
    protocol_number = models.CharField("Номер протокола", max_length=50, blank=True)
    notes = models.TextField("Примечания", blank=True)

    class Meta:
        verbose_name = "Смета"
        verbose_name_plural = "Сметы"
        ordering = ["-year"]
        unique_together = [("organization", "year")]

    def __str__(self):
        return f"Смета на {self.year} год"

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED


class BudgetItem(OrgModel):
    """
    Статья сметы.

    Сумма либо задаётся напрямую, либо считается как количество × цена —
    это и есть строка финансово-экономического обоснования («12 мес ×
    15 000 ₽»). Пояснение — обоснование словами: договор, счёт, расчёт.
    """

    SECTION_MEMBERSHIP = "membership"
    SECTION_TARGET = "target"
    SECTION_CHOICES = [
        (SECTION_MEMBERSHIP, "За счёт членских взносов"),
        (SECTION_TARGET, "За счёт целевых взносов"),
    ]

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="items")
    section = models.CharField("Источник", max_length=12, choices=SECTION_CHOICES,
                               default=SECTION_MEMBERSHIP)
    name = models.CharField("Статья", max_length=255)
    quantity = models.DecimalField("Количество", max_digits=12, decimal_places=3,
                                   null=True, blank=True,
                                   validators=[MinValueValidator(Decimal("0"))])
    unit = models.CharField("Единица", max_length=30, blank=True)
    unit_price = models.DecimalField("Цена за единицу", max_digits=12, decimal_places=2,
                                     null=True, blank=True,
                                     validators=[MinValueValidator(Decimal("0"))])
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0"))])
    justification = models.TextField("Обоснование", blank=True)
    position = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Статья сметы"
        verbose_name_plural = "Статьи сметы"
        ordering = ["section", "position", "pk"]

    def __str__(self):
        return self.name


class Expense(OrgModel):
    """Фактический расход: из чего потом складывается исполнение сметы."""

    date = models.DateField("Дата")
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    item = models.ForeignKey(BudgetItem, on_delete=models.SET_NULL, null=True,
                             blank=True, related_name="expenses",
                             verbose_name="Статья сметы")
    counterparty = models.CharField("Кому", max_length=255, blank=True)
    document = models.CharField("Документ", max_length=255, blank=True,
                                help_text="Номер и дата счёта, договора, чека")
    description = models.CharField("Описание", max_length=500, blank=True)
    recorded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")

    class Meta:
        verbose_name = "Расход"
        verbose_name_plural = "Расходы"
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.date}: {self.amount}"
