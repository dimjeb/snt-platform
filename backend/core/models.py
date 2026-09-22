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


class AccessLog(models.Model):
    """
    Журнал обращений к персональным данным.

    152-ФЗ и приказ ФСТЭК №21 требуют регистрации событий безопасности:
    оператор должен уметь ответить, кто и когда видел реестр членов.
    Без такого журнала на проверке нечего предъявить, а при утечке
    невозможно очертить круг.

    Сам журнал персональных данных не содержит: в нём логин, что именно
    смотрели и сколько записей отдали, но не ФИО и не телефоны. Иначе
    средство защиты само стало бы второй базой ПДн.
    """

    ACTION_LIST = "list"
    ACTION_DETAIL = "detail"
    ACTION_EXPORT = "export"

    ACTION_CHOICES = [
        (ACTION_LIST, "Просмотр списка"),
        (ACTION_DETAIL, "Просмотр записи"),
        (ACTION_EXPORT, "Выгрузка файла"),
    ]

    created_at = models.DateTimeField("Когда", auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        "accounts.User", verbose_name="Пользователь",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    # Снимок логина: учётку могут удалить, а журнал должен остаться читаемым.
    username = models.CharField("Логин", max_length=150, blank=True)
    organization = models.ForeignKey(
        "organizations.Organization", verbose_name="СНТ",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    resource = models.CharField("Что смотрели", max_length=50)
    action = models.CharField("Действие", max_length=10, choices=ACTION_CHOICES)
    object_id = models.CharField("Идентификатор записи", max_length=50, blank=True)
    records = models.PositiveIntegerField("Записей отдано", default=0)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    path = models.CharField("Запрос", max_length=255, blank=True)

    class Meta:
        verbose_name = "Обращение к персональным данным"
        verbose_name_plural = "Журнал обращений к персональным данным"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.created_at:%d.%m.%Y %H:%M} {self.username} → {self.resource}"
