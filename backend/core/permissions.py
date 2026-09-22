"""
Разрешения DRF, специфичные для платформы.
"""
from rest_framework.exceptions import APIException
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
        user = request.user
        if not (user and user.is_authenticated):
            return False
        # Суперадмин без выбранного СНТ видит всё — ровно так же, как это
        # уже устроено в OrgQuerysetMixin. Без этой ветки он получал 403
        # на участках: организаций больше одной, автоподстановка в
        # middleware не срабатывает, request.org пуст.
        if user.is_superuser:
            return True
        return request.org is not None


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


class OrgNotSelected(APIException):
    """Операция требует конкретного СНТ, а оно не выбрано."""

    status_code = 400
    default_detail = (
        "Не выбрано СНТ. Выберите товарищество в переключателе вверху."
    )
    default_code = "org_not_selected"


def require_org(request):
    """
    Организация, в которой выполняется операция.

    Обычному пользователю её ставит middleware по его профилю, а
    суперадмин работает сразу со всеми и выбирает СНТ переключателем.
    Если он этого не сделал, писать данные некуда.

    Бросаем APIException, а не DRF-ную ValidationError: та отдаёт тело
    списком (["текст"]), а весь фронт читает ошибку как
    response.data.detail строкой. Так ответ 400 с понятным текстом
    получается сам по себе в любой вьюхе, и не нужно обёртывать каждый
    вызов в try. Без этой проверки запрос падал с 500 где-то внутри
    ORM, и по ответу было не понять, что всего-то не выбрано СНТ.
    """
    org = getattr(request, "org", None)
    if org is None:
        raise OrgNotSelected()
    return org
