"""
Middleware: прикрепляет объект Organization к request на основе JWT-токена.
Суперадмин может переключаться между организациями через заголовок X-Org-ID.

Важно про порядок выполнения: этот middleware отрабатывает ДО аутентификации
DRF. Django-шный AuthenticationMiddleware заполняет request.user из сессии,
а API работает на JWT, который разбирается уже внутри view. Поэтому на момент
работы middleware request.user для API-запросов — это AnonymousUser, и
полагаться на него нельзя: токен нужно разобрать самостоятельно.

Если этого не делать, request.org остаётся None, и тогда IsOrgMember отвечает
403, а OrgQuerysetMixin возвращает пустой queryset — председатель и казначей
видят ноль записей вместо своих данных.
"""
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication

from organizations.models import Organization


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def _resolve_user(self, request):
        """
        Пользователь сессии (админка), а если сессии нет — владелец JWT.
        Ошибки разбора токена глотаем: невалидный токен — забота DRF,
        он ответит 401 уже на уровне view.
        """
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return user

        try:
            result = self.jwt_auth.authenticate(request)
        except Exception:
            return None
        return result[0] if result else None

    def __call__(self, request):
        request.org = None

        user = self._resolve_user(request)
        if user is not None and user.is_authenticated:
            if user.is_superuser:
                # Суперадмин указывает org через заголовок
                org_id = request.headers.get("X-Org-ID")
                if org_id:
                    try:
                        request.org = Organization.objects.get(pk=org_id)
                    except Organization.DoesNotExist:
                        return JsonResponse(
                            {"detail": "Organization not found."}, status=404
                        )
            else:
                request.org = getattr(user, "organization", None)

        return self.get_response(request)
