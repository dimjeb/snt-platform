from rest_framework import viewsets, permissions
from core.permissions import IsSuperAdmin, IsChairman
from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    Управление организациями (СНТ).
    Суперадмин — полный доступ. Председатель — только своя org (read/update).
    """
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def get_permissions(self):
        if self.action in ("list", "create", "destroy"):
            return [IsSuperAdmin()]
        return [IsChairman()]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(pk=self.request.org.pk)
