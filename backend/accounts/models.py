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
    must_change_password = models.BooleanField(
        "Требуется сменить пароль", default=False,
        help_text=(
            "Учётная запись заведена с временным паролем. Пока флаг стоит, "
            "API отдаёт 403 на всё, кроме профиля и смены пароля."
        ),
    )
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

    def normalize_role(self):
        """
        Роль «суперадмин» и флаг is_superuser — одно и то же, и должны
        совпадать. Права платформы проверяются по флагу, а интерфейс и часть
        прав СНТ — по роли. Когда они расходились (флаг сняли в админке,
        роль осталась), человек видел меню администратора платформы, а
        сервер ему же отказывал.

        Сняли флаг — роль администратора уходит: учётка, привязанная к СНТ,
        остаётся председателем этого СНТ (так это и бывает: администратор
        был ещё и председателем), не привязанная — рядовой.
        """
        if self.is_superuser:
            self.role = self.ROLE_SUPERADMIN
        elif self.role == self.ROLE_SUPERADMIN:
            self.role = self.ROLE_CHAIRMAN if self.organization_id else self.ROLE_MEMBER

    def save(self, *args, **kwargs):
        before = self.role
        self.normalize_role()
        fields = kwargs.get("update_fields")
        if fields is not None and self.role != before and "role" not in fields:
            kwargs["update_fields"] = list(fields) + ["role"]
        super().save(*args, **kwargs)

    @property
    def is_chairman(self):
        return self.role in (self.ROLE_CHAIRMAN, self.ROLE_SUPERADMIN)

    @property
    def is_treasurer(self):
        return self.role in (self.ROLE_CHAIRMAN, self.ROLE_TREASURER, self.ROLE_SUPERADMIN)
