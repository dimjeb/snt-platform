from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.permissions import IsTreasurer, IsOrgMember, OrgQuerysetMixin
from .models import Member, Plot, PlotOwnership
from .serializers import (
    MemberSerializer,
    MemberShortSerializer,
    PlotSerializer,
    PlotOwnershipSerializer,
)


class MemberViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["last_name", "first_name", "patronymic", "phone", "email"]
    ordering_fields = ["last_name", "joined_at"]

    def get_permissions(self):
        # Реестр членов — только председателю и казначею. Роутер фронтенда
        # закрывает раздел «Члены» для роли member, но это защита лишь на
        # клиенте: с токеном рядового члена список выгружался запросом
        # напрямую, вместе с телефонами и email (152-ФЗ).
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)

    @action(detail=False, methods=["get"], url_path="short")
    def short(self, request):
        """Компактный список членов для select/autocomplete (без пагинации)."""
        qs = self.get_queryset().order_by("last_name", "first_name")
        search = request.query_params.get("search", "")
        if search:
            qs = qs.filter(last_name__icontains=search) | qs.filter(first_name__icontains=search)
        serializer = MemberShortSerializer(qs[:200], many=True)
        return Response(serializer.data)


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

    def get_queryset(self):
        """
        Участки, доступные текущему пользователю.

        В filter_backends нет DjangoFilterBackend, поэтому ?member= раньше
        молча игнорировался: личный кабинет запрашивал свои участки, а получал
        первые попавшиеся по СНТ и брал results[0] — то есть участок №1.
        Член мог передать показания в чужой счётчик.

        Связь участка с членом идёт через PlotOwnership, прямого FK нет,
        поэтому фильтр собран вручную по открытому владению.
        """
        qs = super().get_queryset()
        user = self.request.user

        # Член СНТ видит только свои участки: в выдаче есть current_owner
        # с ФИО, и раскрывать его всему товариществу не следует.
        if getattr(user, "role", None) == user.ROLE_MEMBER:
            if user.member_id:
                qs = qs.filter(
                    ownerships__member_id=user.member_id,
                    ownerships__date_to__isnull=True,
                )
            else:
                qs = qs.none()

        member = self.request.query_params.get("member")
        if member:
            try:
                member_id = int(member)
            except (TypeError, ValueError):
                return qs.none()
            qs = qs.filter(
                ownerships__member_id=member_id,
                ownerships__date_to__isnull=True,
            )

        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class PlotOwnershipViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = PlotOwnership.objects.select_related("plot", "member")
    serializer_class = PlotOwnershipSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["plot", "member"]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)
