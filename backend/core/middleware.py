"""
Middleware: прикрепляет объект Organization к request на основе JWT-токена.
Суперадмин может переключаться между организациями через заголовок X-Org-ID.
"""
from django.http import JsonResponse
from organizations.models import Organization


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.org = None

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
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
