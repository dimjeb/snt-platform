from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.permissions import IsTreasurer, IsOrgMember, OrgQuerysetMixin
from .models import Member, Plot, PlotOwnership
from .serializers import MemberSerializer, PlotSerializer, PlotOwnershipSerializer


class MemberViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["last_name", "first_name", "patronymic", "phone", "email"]
    ordering_fields = ["last_name", "joined_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsOrgMember()]
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class PlotViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Plot.objects.prefetch_related("ownerships__member")
    serializer_class = PlotSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["number", "cadastral_number"]
    ordering_fields = ["number", "area_sotok"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsOrgMember()]
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class PlotOwnershipViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = PlotOwnership.objects.select_related("plot", "member")
    serializer_class = PlotOwnershipSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["plot", "member"]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)
