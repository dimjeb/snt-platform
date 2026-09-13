from django.db import models
from core.models import OrgModel


class Member(OrgModel):
    """Член садоводческого товарищества."""

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_HEIR = "heir"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Действующий"),
        (STATUS_INACTIVE, "Выбывший"),
        (STATUS_HEIR, "Наследник"),
    ]

    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    email = models.EmailField("Email", blank=True)
    joined_at = models.DateField("Дата вступления", null=True, blank=True)
    status = models.CharField(
        "Статус", max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    notes = models.TextField("Примечания", blank=True)

    class Meta:
        verbose_name = "Член СНТ"
        verbose_name_plural = "Члены СНТ"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        parts = [self.last_name, self.first_name]
        if self.patronymic:
            parts.append(self.patronymic)
        return " ".join(parts)

    @property
    def full_name(self):
        return str(self)

    @property
    def plots(self):
        """
        Текущие участки члена.

        Список, а не queryset: обход подтянутых ownerships позволяет
        вьюсету снять N+1 через prefetch_related("ownerships__plot").
        Отдельный запрос на каждого члена превращал страницу реестра
        из 50 строк в полсотни лишних обращений к базе.
        """
        return [o.plot for o in self.ownerships.all() if o.date_to is None]


class Plot(OrgModel):
    """Земельный участок."""

    number = models.CharField("Номер участка", max_length=20)
    area_sotok = models.DecimalField(
        "Площадь (соток)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    cadastral_number = models.CharField("Кадастровый номер", max_length=50, blank=True)
    notes = models.TextField("Примечания", blank=True)

    class Meta:
        verbose_name = "Участок"
        verbose_name_plural = "Участки"
        ordering = ["number"]
        unique_together = [("organization", "number")]

    def __str__(self):
        return f"Участок №{self.number}"

    @property
    def current_owner(self):
        # Фильтруем в памяти, а не через .filter(): тот создаёт новый
        # queryset и ходит в базу отдельно на каждый участок, сводя на нет
        # prefetch_related("ownerships__member") во вьюсете. На странице
        # из 50 участков это давало сотню лишних запросов.
        # Порядок ownerships — "-date_from", поэтому первое открытое
        # владение и есть текущее.
        for ownership in self.ownerships.all():
            if ownership.date_to is None:
                return ownership.member
        return None


class PlotOwnership(OrgModel):
    """
    История владения участком.
    date_to=None означает текущего владельца.
    """

    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="ownerships")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="ownerships")
    date_from = models.DateField("Дата начала")
    date_to = models.DateField("Дата окончания", null=True, blank=True)
    notes = models.TextField("Основание", blank=True)

    class Meta:
        verbose_name = "Владение участком"
        verbose_name_plural = "История владений"
        ordering = ["-date_from"]

    def __str__(self):
        end = self.date_to or "н.в."
        return f"{self.plot} → {self.member} ({self.date_from} – {end})"
