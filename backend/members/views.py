from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from accounts.provisioning import (
    ProvisioningError, issue_account, reset_password,
)
from core.audit import AccessLoggedMixin, record_access
from core.models import AccessLog
from core.permissions import (
    IsChairman, IsTreasurer, IsOrgMember, OrgQuerysetMixin, require_org,
)
from .models import Member, Plot, PlotOwnership
from .serializers import (
    MemberSerializer,
    MemberShortSerializer,
    PlotSerializer,
    PlotOwnershipSerializer,
)


class MemberViewSet(AccessLoggedMixin, OrgQuerysetMixin, viewsets.ModelViewSet):
    # Реестр членов — ФИО, телефоны, email. Каждое чтение попадает в журнал
    # обращений к ПДн: оператор обязан уметь сказать, кто и когда их видел.
    audit_resource = "реестр членов"
    # Сериализатор отдаёт current_plots, поэтому владения с участками
    # подтягиваем сразу — иначе запрос на каждого члена.
    queryset = Member.objects.prefetch_related("ownerships__plot").select_related("user_account")
    serializer_class = MemberSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["last_name", "first_name", "patronymic", "phone", "email"]
    ordering_fields = ["last_name", "joined_at"]

    # Действия, которым нужна не общая строгость вьюсета, а своя.
    # Выдача доступа — это заведение учётной записи с паролем, дело
    # председателя: казначей ведёт деньги, а не людей.
    CHAIRMAN_ONLY = ("grant_access", "reset_password_action")

    def get_permissions(self):
        # Реестр членов — только председателю и казначею. Роутер фронтенда
        # закрывает раздел «Члены» для роли member, но это защита лишь на
        # клиенте: с токеном рядового члена список выгружался запросом
        # напрямую, вместе с телефонами и email (152-ФЗ).
        #
        # Список действий перечислен явно, а не взят из permission_classes
        # самого @action: этот метод переопределён и молча затирал бы их
        # строгость. Так уже было — казначей мог выдать доступ.
        if self.action in self.CHAIRMAN_ONLY:
            return [IsChairman()]
        return [IsTreasurer()]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))

    @action(detail=True, methods=["post"], url_path="grant-access",
            permission_classes=[IsChairman])
    def grant_access(self, request, pk=None):
        """
        Завести члену учётную запись и один раз показать пароль.

        Пароль возвращается только здесь: в базе лежит его хеш, и
        повторно показать его нельзя даже председателю. Потерялся —
        сбрасывать.
        """
        member = self.get_object()
        try:
            user, password = issue_account(member, organization=member.organization)
        except ProvisioningError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        record_access(request, "выдача доступа", AccessLog.ACTION_DETAIL,
                      object_id=str(member.pk))
        return Response({
            "username": user.username,
            "password": password,
            "full_name": member.full_name,
            "plots": [p.number for p in member.plots],
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="reset-password",
            permission_classes=[IsChairman])
    def reset_password_action(self, request, pk=None):
        """Новый временный пароль взамен потерянного."""
        member = self.get_object()
        # Обратная сторона OneToOne: при отсутствии связи Django бросает
        # исключение, унаследованное от AttributeError, поэтому getattr с
        # умолчанием здесь работает как надо.
        user = getattr(member, "user_account", None)
        if user is None:
            return Response(
                {"detail": "У этого члена СНТ нет учётной записи — сначала выдайте доступ."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            password = reset_password(user)
        except ProvisioningError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        record_access(request, "сброс пароля", AccessLog.ACTION_DETAIL,
                      object_id=str(member.pk))
        return Response({
            "username": user.username,
            "password": password,
            "full_name": member.full_name,
            "plots": [p.number for p in member.plots],
        })

    @action(detail=False, methods=["get"], url_path="short")
    def short(self, request):
        """Компактный список членов для select/autocomplete (без пагинации)."""
        qs = self.get_queryset().order_by("last_name", "first_name")
        search = request.query_params.get("search", "")
        if search:
            qs = qs.filter(last_name__icontains=search) | qs.filter(first_name__icontains=search)
        serializer = MemberShortSerializer(qs[:200], many=True)
        return Response(serializer.data)


class PlotViewSet(AccessLoggedMixin, OrgQuerysetMixin, viewsets.ModelViewSet):
    # В выдаче участков есть ФИО собственников — это тоже персональные данные.
    audit_resource = "участки"
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
        serializer.save(organization=require_org(self.request))


class PlotOwnershipViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = PlotOwnership.objects.select_related("plot", "member")
    serializer_class = PlotOwnershipSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["plot", "member"]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))
