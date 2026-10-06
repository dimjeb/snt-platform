import uuid

from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from core.permissions import IsChairman, IsSuperAdmin, require_org
from .models import Organization
from .serializers import OrganizationSerializer, OrganizationShortSerializer
from .setup import SetupSerializer, create_snt

LOGO_MAX_BYTES = 2 * 1024 * 1024
LOGO_FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


class LogoUploadSerializer(serializers.Serializer):
    logo = serializers.ImageField()

    def validate_logo(self, f):
        if f.size > LOGO_MAX_BYTES:
            raise serializers.ValidationError(
                "Файл больше 2 МБ — уменьшите картинку.")
        # Формат берём у Pillow, а не из расширения или Content-Type: их
        # подделать проще всего. SVG сюда не пройдёт вовсе — в нём бывает
        # скрипт, а лежит логотип в публичной /media/.
        fmt = getattr(getattr(f, "image", None), "format", None)
        if fmt not in LOGO_FORMATS:
            raise serializers.ValidationError(
                "Подойдёт PNG, JPG или WEBP.")
        f.logo_ext = LOGO_FORMATS[fmt]
        return f


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    Управление организациями (СНТ).
    Суперадмин — полный доступ. Председатель — только своя org (read/update).
    """
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def get_permissions(self):
        if self.action in ("list", "create", "destroy", "setup"):
            return [IsSuperAdmin()]
        if self.action == "current":
            return [permissions.IsAuthenticated()]
        return [IsChairman()]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(pk=self.request.org.pk)

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Имя и логотип своего СНТ — для шапки, видно всем его людям."""
        org = require_org(request)
        return Response(OrganizationShortSerializer(
            org, context={"request": request}).data)

    @action(detail=False, methods=["post", "delete"], url_path="current/logo",
            parser_classes=[MultiPartParser, FormParser])
    def logo(self, request):
        """Загрузить (POST, поле logo) или убрать (DELETE) логотип своего СНТ."""
        org = require_org(request)
        if request.method == "DELETE":
            if org.logo:
                org.logo.delete(save=False)
            org.logo = None
            org.save(update_fields=["logo", "updated_at"])
            return Response(status=status.HTTP_204_NO_CONTENT)

        s = LogoUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        f = s.validated_data["logo"]
        old = org.logo.name if org.logo else None
        # Новое имя на каждую загрузку: иначе браузер покажет старую
        # картинку из кеша.
        org.logo.save(f"org{org.pk}-{uuid.uuid4().hex[:8]}.{f.logo_ext}", f,
                      save=False)
        org.save(update_fields=["logo", "updated_at"])
        if old and old != org.logo.name:
            org.logo.storage.delete(old)
        return Response(OrganizationShortSerializer(
            org, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def setup(self, request):
        """
        Мастер нового садоводства: товарищество + председатель (+ казначей)
        одной транзакцией. Временные пароли — в ответе, один раз.
        """
        from core.audit import record_access
        from core.models import AccessLog

        s = SetupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        org, accounts = create_snt(s.validated_data)
        record_access(request, "мастер нового садоводства: выдача доступа",
                      AccessLog.ACTION_DETAIL, object_id=org.pk,
                      records=len(accounts))
        return Response({
            "organization": OrganizationSerializer(org).data,
            "accounts": accounts,
        }, status=status.HTTP_201_CREATED)
