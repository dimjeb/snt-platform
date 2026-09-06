from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Пользователь платформы.
    Суперадмин (is_superuser=True) управляет всеми СНТ.
    Остальные привязаны к конкретной организации через поле organization.
    """

    ROLE_SUPERADMIN = "superadmin"
    ROLE_CHAIRMAN = "chairman"
    ROLE_TREASURER = "treasurer"
    ROLE_MEMBER = "member"

    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, "Суперадмин платформы"),
        (ROLE_CHAIRMAN, "Председатель"),
        (ROLE_TREASURER, "Казначей"),
        (ROLE_MEMBER, "Член СНТ"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Организация",
    )
    role = models.CharField(
        "Роль",
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
    )
    phone = models.CharField("Телефон", max_length=20, blank=True)
    # Связь с конкретным членом СНТ (может отсутствовать у председателя/казначея)
    member = models.OneToOneField(
        "members.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_account",
        verbose_name="Член СНТ",
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_chairman(self):
        return self.role in (self.ROLE_CHAIRMAN, self.ROLE_SUPERADMIN)

    @property
    def is_treasurer(self):
        return self.role in (self.ROLE_CHAIRMAN, self.ROLE_TREASURER, self.ROLE_SUPERADMIN)
