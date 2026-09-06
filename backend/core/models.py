"""
Базовая абстрактная модель для всех сущностей платформы.
Каждая модель привязана к организации (СНТ) — это обеспечивает изоляцию тенантов.
"""
from django.db import models


class OrgModel(models.Model):
    """
    Абстрактный предок: добавляет org и временные метки.
    Все модели, относящиеся к конкретному СНТ, наследуются от OrgModel.
    """
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TimestampModel(models.Model):
    """Только временные метки, без org (для системных объектов)."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
