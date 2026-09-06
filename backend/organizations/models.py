from django.db import models
from core.models import TimestampModel


class Organization(TimestampModel):
    """СНТ — корневая сущность платформы (тенант)."""

    name = models.CharField("Название СНТ", max_length=255)
    inn = models.CharField("ИНН", max_length=12, blank=True)
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

    class Meta:
        verbose_name = "Организация (СНТ)"
        verbose_name_plural = "Организации (СНТ)"
        ordering = ["name"]

    def __str__(self):
        return self.name
