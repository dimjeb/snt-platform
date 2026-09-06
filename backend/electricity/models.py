from django.db import models
from core.models import OrgModel


class EnergyTariff(OrgModel):
    """История тарифов на электроэнергию."""

    valid_from = models.DateField("Действует с")
    price_per_kwh = models.DecimalField(
        "Тариф (руб./кВт·ч)", max_digits=8, decimal_places=4
    )
    # Опционально: ночной тариф (для двухзонных счётчиков)
    price_per_kwh_night = models.DecimalField(
        "Ночной тариф (руб./кВт·ч)", max_digits=8, decimal_places=4,
        null=True, blank=True
    )
    notes = models.CharField("Примечание", max_length=200, blank=True)

    class Meta:
        verbose_name = "Тариф на электроэнергию"
        verbose_name_plural = "Тарифы на электроэнергию"
        ordering = ["-valid_from"]

    def __str__(self):
        return f"с {self.valid_from}: {self.price_per_kwh} руб./кВт·ч"


class Meter(OrgModel):
    """Счётчик электроэнергии."""

    plot = models.ForeignKey(
        "members.Plot",
        on_delete=models.CASCADE,
        related_name="meters",
        null=True,
        blank=True,
        verbose_name="Участок",
        help_text="Пусто — для главного ввода СНТ.",
    )
    serial_number = models.CharField("Серийный номер", max_length=50, blank=True)
    is_main = models.BooleanField(
        "Главный ввод",
        default=False,
        help_text="Общий счётчик на вводе СНТ.",
    )
    installed_at = models.DateField("Дата установки", null=True, blank=True)
    notes = models.TextField("Примечания", blank=True)

    class Meta:
        verbose_name = "Счётчик"
        verbose_name_plural = "Счётчики"
        ordering = ["plot__number"]

    def __str__(self):
        if self.is_main:
            return f"Главный ввод СНТ ({self.serial_number or 'б/н'})"
        return f"Счётчик уч.{self.plot.number} ({self.serial_number or 'б/н'})"


class MeterReading(OrgModel):
    """Показание счётчика."""

    meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name="readings")
    date = models.DateField("Дата снятия")
    # Однозонный счётчик — только value; двухзонный — value (день) + value_night
    value = models.DecimalField("Показание (день/общее), кВт·ч", max_digits=12, decimal_places=3)
    value_night = models.DecimalField(
        "Показание (ночь), кВт·ч", max_digits=12, decimal_places=3,
        null=True, blank=True
    )
    submitted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="submitted_readings",
    )
    photo = models.ImageField(
        "Фото показания", upload_to="meter_photos/", null=True, blank=True
    )
    notes = models.CharField("Примечание", max_length=200, blank=True)

    class Meta:
        verbose_name = "Показание счётчика"
        verbose_name_plural = "Показания счётчиков"
        ordering = ["-date"]
        unique_together = [("meter", "date")]

    def __str__(self):
        return f"{self.meter} / {self.date}: {self.value} кВт·ч"
