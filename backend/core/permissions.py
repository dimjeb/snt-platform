"""
Разрешения DRF, специфичные для платформы.
"""
from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Только суперадмин платформы."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsChairman(BasePermission):
    """Председатель своего СНТ."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in ("chairman", "superadmin")
        )


class IsTreasurer(BasePermission):
    """Казначей или председатель."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in ("chairman", "treasurer", "superadmin")
        )


class IsOrgMember(BasePermission):
    """Любой аутентифицированный пользователь, относящийся к организации."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.org is not None
        )


class OrgQuerysetMixin:
    """
    Миксин для ViewSet: автоматически фильтрует queryset по organization.
    Суперадмин без X-Org-ID видит все объекты (для отладки).
    """
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.org:
            qs = qs.filter(organization=self.request.org)
        elif not self.request.user.is_superuser:
            qs = qs.none()
        return qs
