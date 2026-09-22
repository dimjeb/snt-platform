from decimal import Decimal
from django.db import models
from core.models import OrgModel


class ChargeType(OrgModel):
    """Вид начисления: членский взнос, целевой взнос, электроэнергия, вода и т.д."""

    TYPE_MEMBERSHIP = "membership"
    TYPE_TARGET = "target"
    TYPE_ELECTRICITY = "electricity"
    TYPE_WATER = "water"
    TYPE_GARBAGE = "garbage"
    TYPE_SECURITY = "security"
    TYPE_OTHER = "other"

    CATEGORY_CHOICES = [
        (TYPE_MEMBERSHIP, "Членский взнос"),
        (TYPE_TARGET, "Целевой взнос"),
        (TYPE_ELECTRICITY, "Электроэнергия"),
        (TYPE_WATER, "Водоснабжение"),
        (TYPE_GARBAGE, "Вывоз мусора"),
        (TYPE_SECURITY, "Охрана"),
        (TYPE_OTHER, "Прочее"),
    ]

    name = models.CharField("Название", max_length=255)
    category = models.CharField("Категория", max_length=20, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Вид начисления"
        verbose_name_plural = "Виды начислений"
        ordering = ["name"]

    def __str__(self):
        return self.name


class BillingPeriod(OrgModel):
    """Расчётный период: месяц или квартал."""

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Открыт"),
        (STATUS_CLOSED, "Закрыт"),
    ]

    year = models.PositiveIntegerField("Год")
    # Месяц 1–12 или квартал 1–4 (в зависимости от настроек org)
    month = models.PositiveSmallIntegerField("Месяц/квартал", null=True, blank=True)
    status = models.CharField(
        "Статус", max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    notes = models.TextField("Примечания", blank=True)

    class Meta:
        verbose_name = "Расчётный период"
        verbose_name_plural = "Расчётные периоды"
        ordering = ["-year", "-month"]
        unique_together = [("organization", "year", "month")]

    def __str__(self):
        if self.month:
            return f"{self.year}-{self.month:02d}"
        return str(self.year)


class Charge(OrgModel):
    """
    Начисление: сумма, которую должен оплатить владелец участка за период.
    """

    period = models.ForeignKey(
        BillingPeriod, on_delete=models.PROTECT, related_name="charges"
    )
    plot = models.ForeignKey(
        "members.Plot", on_delete=models.PROTECT, related_name="charges"
    )
    charge_type = models.ForeignKey(
        ChargeType, on_delete=models.PROTECT, related_name="charges"
    )
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    description = models.CharField("Описание", max_length=500, blank=True)
    # Для электроэнергии: фиксируем расчётные данные
    kwh = models.DecimalField("кВт·ч", max_digits=10, decimal_places=3, null=True, blank=True)
    tariff = models.DecimalField(
        "Тариф (руб./кВт)", max_digits=8, decimal_places=4, null=True, blank=True
    )

    class Meta:
        verbose_name = "Начисление"
        verbose_name_plural = "Начисления"
        ordering = ["-period__year", "-period__month", "plot__number"]

    def __str__(self):
        return f"{self.plot} / {self.charge_type} / {self.period}: {self.amount} ₽"

    @property
    def paid_amount(self):
        # Когда платежи подтянуты через prefetch_related, считаем в памяти:
        # aggregate() всегда идёт в базу, и на списке из сотни начислений
        # это оборачивалось сотней запросов поверх уже загруженных данных.
        if "payments" in getattr(self, "_prefetched_objects_cache", {}):
            return sum(
                (p.amount for p in self.payments.all() if not p.is_cancelled),
                Decimal("0"),
            )
        return self.payments.filter(
            is_cancelled=False
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    @property
    def debt(self):
        return self.amount - self.paid_amount


class Payment(OrgModel):
    """Фактическая оплата начисления."""

    METHOD_CASH = "cash"
    METHOD_BANK = "bank"
    METHOD_SBP = "sbp"
    METHOD_CARD = "card"
    METHOD_OTHER = "other"

    METHOD_CHOICES = [
        (METHOD_CASH, "Наличные"),
        (METHOD_BANK, "Банковский перевод"),
        (METHOD_SBP, "СБП"),
        (METHOD_CARD, "Карта"),
        (METHOD_OTHER, "Прочее"),
    ]

    charge = models.ForeignKey(
        Charge, on_delete=models.PROTECT, related_name="payments"
    )
    date = models.DateField("Дата оплаты")
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    method = models.CharField(
        "Способ оплаты", max_length=10, choices=METHOD_CHOICES, default=METHOD_CASH
    )
    # Для онлайн-оплаты: ID транзакции в агрегаторе
    external_ref = models.CharField("Внешний ID транзакции", max_length=100, blank=True)
    is_cancelled = models.BooleanField("Отменён", default=False)
    notes = models.TextField("Примечания", blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.charge.plot} / {self.date} / {self.amount} ₽ ({self.get_method_display()})"


class BankStatement(OrgModel):
    """
    Загруженная банковская выписка.

    Разбор и проведение разделены намеренно: сначала казначей видит, что
    система поняла, и только потом нажимает «Провести». Автоматическое
    зачисление по догадке — это чужой долг, закрытый чужими деньгами,
    и обнаруживается такое через месяцы.
    """

    STATUS_PARSED = "parsed"
    STATUS_APPLIED = "applied"

    STATUS_CHOICES = [
        (STATUS_PARSED, "Разобрана"),
        (STATUS_APPLIED, "Проведена"),
    ]

    file_name = models.CharField("Файл", max_length=255)
    account = models.CharField("Расчётный счёт", max_length=20, blank=True)
    date_from = models.DateField("Период с", null=True, blank=True)
    date_to = models.DateField("Период по", null=True, blank=True)
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES,
                              default=STATUS_PARSED)
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Загрузил",
    )
    applied_at = models.DateTimeField("Проведена", null=True, blank=True)
    notes = models.TextField("Примечания", blank=True)

    class Meta:
        verbose_name = "Банковская выписка"
        verbose_name_plural = "Банковские выписки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file_name} ({self.date_from} – {self.date_to})"


class BankTransaction(OrgModel):
    """Одна строка выписки — поступление на счёт товарищества."""

    MATCH_PLOT = "plot"
    MATCH_NAME = "name"
    MATCH_NONE = "none"
    MATCH_MANUAL = "manual"

    MATCH_CHOICES = [
        (MATCH_PLOT, "По номеру участка"),
        (MATCH_NAME, "По ФИО плательщика"),
        (MATCH_NONE, "Не опознан"),
        (MATCH_MANUAL, "Указан вручную"),
    ]

    STATUS_NEW = "new"
    STATUS_APPLIED = "applied"
    STATUS_SKIPPED = "skipped"

    STATUS_CHOICES = [
        (STATUS_NEW, "Ожидает проведения"),
        (STATUS_APPLIED, "Проведён"),
        (STATUS_SKIPPED, "Пропущен"),
    ]

    statement = models.ForeignKey(
        BankStatement, on_delete=models.CASCADE, related_name="transactions",
        verbose_name="Выписка",
    )
    doc_number = models.CharField("Номер документа", max_length=50, blank=True)
    date = models.DateField("Дата")
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    payer_name = models.CharField("Плательщик", max_length=255, blank=True)
    payer_account = models.CharField("Счёт плательщика", max_length=34, blank=True)
    purpose = models.TextField("Назначение платежа", blank=True)

    plot = models.ForeignKey(
        "members.Plot", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Участок",
    )
    member = models.ForeignKey(
        "members.Member", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Член СНТ",
    )
    match_kind = models.CharField("Как опознан", max_length=10,
                                  choices=MATCH_CHOICES, default=MATCH_NONE)
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES,
                              default=STATUS_NEW)
    note = models.CharField("Комментарий", max_length=255, blank=True)

    class Meta:
        verbose_name = "Строка выписки"
        verbose_name_plural = "Строки выписки"
        ordering = ["date", "pk"]
        constraints = [
            # Повторная загрузка того же файла не должна задваивать деньги.
            # Ключ — организация, дата, сумма, номер документа и счёт
            # плательщика: полного совпадения всего этого у двух разных
            # платежей практически не бывает.
            models.UniqueConstraint(
                fields=["organization", "date", "amount", "doc_number",
                        "payer_account"],
                name="unique_bank_transaction",
            )
        ]

    def __str__(self):
        return f"{self.date} {self.amount} ₽ от {self.payer_name or 'неизвестно'}"
