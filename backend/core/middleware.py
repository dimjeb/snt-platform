"""
Middleware: устанавливает текущую Organization в request.
Работает и с сессионной аутентификацией (админка), и с JWT (Bearer).

Про порядок выполнения: middleware отрабатывает ДО аутентификации DRF.
Django-шный AuthenticationMiddleware заполняет request.user из сессии,
а API живёт на JWT, который разбирается позже, уже внутри view. Поэтому
для API-запросов request.user здесь — AnonymousUser, и полагаться на него
нельзя: токен разбираем сами.

Если этого не делать, request.org остаётся None, и тогда IsOrgMember
отвечает 403, а OrgQuerysetMixin возвращает пустой queryset — председатель
и казначей видят ноль записей вместо своих данных.
"""
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication

from organizations.models import Organization

_jwt_auth = JWTAuthentication()


def _get_jwt_user(request):
    """
    Владелец Bearer-токена, либо None.

    authenticate() сам разбирает заголовок по настройке AUTH_HEADER_TYPES
    и молча возвращает None, когда токена нет. Невалидный токен глотаем:
    это забота DRF, он ответит 401 уже на уровне view.
    """
    try:
        result = _jwt_auth.authenticate(request)
    except Exception:
        return None
    return result[0] if result else None


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.org = None

        # Пробуем сессионного пользователя, затем JWT
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            user = _get_jwt_user(request)

        if user and user.is_authenticated:
            if user.is_superuser:
                # Суперадмин указывает организацию через заголовок
                org_id = request.headers.get("X-Org-ID")
                if org_id:
                    try:
                        request.org = Organization.objects.get(
                            pk=org_id, is_active=True
                        )
                    except Organization.DoesNotExist:
                        return JsonResponse(
                            {"detail": "Organization not found."}, status=404
                        )
                else:
                    # Одна организация в системе — берём её автоматически
                    active = Organization.objects.filter(is_active=True)
                    if active.count() == 1:
                        request.org = active.first()
            else:
                request.org = getattr(user, "organization", None)

        return self.get_response(request)
