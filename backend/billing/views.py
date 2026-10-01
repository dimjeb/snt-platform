from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.permissions import (
    IsTreasurer, OrgQuerysetMixin, require_org,
)
from .models import ChargeType, BillingPeriod, Charge, Payment
from .serializers import (
    ChargeTypeSerializer, BillingPeriodSerializer, ChargeSerializer,
    PaymentSerializer, BulkMembershipChargeSerializer, BulkTargetChargeSerializer,
)
from django.db.models import Count

from .models import BankStatement, BankTransaction
from .serializers import (
    BankStatementListSerializer,
    BankStatementSerializer,
    BankTransactionSerializer,
)
from .services import (
    apply_penalties,
    create_membership_charges,
    create_target_charges,
    get_debt_summary,
)
from .statement import StatementError
from .statement_service import (
    StatementImportError,
    apply_statement,
    import_statement,
    statement_summary,
)


class ChargeTypeViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = ChargeType.objects.all()
    serializer_class = ChargeTypeSerializer
    permission_classes = [IsTreasurer]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))


class BillingPeriodViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = BillingPeriod.objects.all()
    serializer_class = BillingPeriodSerializer
    permission_classes = [IsTreasurer]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))

    # Все три операции относятся к конкретному расчётному периоду, поэтому
    # маршруты detail: период берётся из URL, а не из тела запроса. Раньше
    # они были объявлены detail=False, и фронт, зовущий
    # /billing/periods/<id>/debt_summary/, получал 404 — страница начислений
    # не работала целиком.
    @action(detail=True, methods=["get"])
    def debt_summary(self, request, pk=None):
        """Сводка долгов по участкам за этот расчётный период."""
        period = self.get_object()
        return Response(get_debt_summary(require_org(request), period=period))

    @action(detail=True, methods=["post"])
    def create_membership_charges(self, request, pk=None):
        """Массовое создание членских взносов за этот период."""
        period = self.get_object()
        s = BulkMembershipChargeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(create_membership_charges(
            period,
            amount=s.validated_data["amount"],
            description=s.validated_data["description"],
            basis=s.validated_data["basis"],
            rate=s.validated_data["rate"],
            due_date=s.validated_data["due_date"],
            penalty_percent=s.validated_data["penalty_percent"],
        ))

    @action(detail=True, methods=["post"])
    def create_target_charges(self, request, pk=None):
        """Создание целевых взносов за этот период."""
        period = self.get_object()
        s = BulkTargetChargeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        org = require_org(request)
        try:
            charge_type = ChargeType.objects.get(
                pk=s.validated_data["charge_type_id"], organization=org
            )
        except ChargeType.DoesNotExist:
            # Вид начисления из другого СНТ или удалённый: без явной
            # обработки запрос падал с 500 внутри ORM.
            return Response(
                {"detail": "Вид начисления не найден в этом товариществе."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(create_target_charges(
            period, charge_type,
            amount=s.validated_data["amount"],
            plot_ids=s.validated_data.get("plot_ids"),
            scope=s.validated_data["scope"],
            description=s.validated_data["description"],
            basis=s.validated_data["basis"],
            rate=s.validated_data["rate"],
            due_date=s.validated_data["due_date"],
            penalty_percent=s.validated_data["penalty_percent"],
        ))


class ChargeViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    # pk в конце — чтобы порядок строк одного участка не зависел от
    # того, как PostgreSQL сегодня разложил их на диске. Без него
    # страница из 500 строк при большем числе начислений набиралась
    # каждый раз немного по-разному.
    queryset = Charge.objects.select_related(
        "period", "plot", "charge_type"
    ).prefetch_related("payments").order_by(
        "-period__year", "-period__month", "plot__number", "pk"
    )
    serializer_class = ChargeSerializer
    filterset_fields = ["period", "plot", "charge_type"]

    # Раньше list и retrieve были открыты любому члену товарищества
    # (IsOrgMember), и через API он читал начисления всех соседей: номера
    # участков, суммы, долги, а с появлением взносов «за члена» — ещё и
    # чьи они. Интерфейсу члена этот список не нужен: свой долг кабинет
    # берёт из /payments/my-debt/, где выборка идёт от его собственных
    # участков. Страница «Начисления» открыта только правлению.
    permission_classes = [IsTreasurer]

    def perform_create(self, serializer):
        serializer.save(organization=require_org(self.request))

    @action(detail=True, methods=["get"])
    def transfer_targets(self, request, pk=None):
        """Куда можно перенести оплату с этого начисления."""
        from .transfers import transfer_targets

        source = self.get_object()
        return Response([
            {
                "id": c.pk,
                "label": f"{c.charge_type.name} · {c.period} · уч. {c.plot.number}",
                "debt": c.debt,
            }
            for c in transfer_targets(source)
        ])

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        """
        Перенести часть оплаты с этого начисления на другое того же
        плательщика. Тело: {"target": id, "amount": "500.00", "reason": "..."}.
        """
        from decimal import Decimal, InvalidOperation

        from .transfers import TransferError, transfer_payment

        source = self.get_object()
        try:
            target = self.get_queryset().get(pk=request.data.get("target"))
        except (Charge.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Целевое начисление не найдено."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(str(request.data.get("amount", "")).replace(",", "."))
        except InvalidOperation:
            return Response({"detail": "Сумма указана неверно."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            transfer_payment(source, target, amount, user=request.user,
                             reason=str(request.data.get("reason", ""))[:500])
        except TransferError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"moved": amount})

    @action(detail=False, methods=["post"])
    def apply_penalties(self, request):
        """
        Начислить пени по всем просроченным начислениям товарищества.

        Кнопка на случай, когда команду по расписанию ещё не поставили
        или казначей хочет закрыть просрочку прямо сейчас. Повторное
        нажатие ничего не задваивает.
        """
        result = apply_penalties(require_org(request), user=request.user)
        return Response(result)


class PaymentViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("charge__plot", "recorded_by")
    serializer_class = PaymentSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["charge", "method", "is_cancelled"]

    def perform_create(self, serializer):
        serializer.save(
            organization=require_org(self.request),
            recorded_by=self.request.user,
        )


class BankStatementViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    """
    Банковские выписки: загрузка, разбор, проведение.

    Только казначею и председателю: здесь создаются платежи, то есть
    закрываются чужие долги.
    """

    queryset = BankStatement.objects.prefetch_related(
        "transactions__plot", "transactions__member"
    )
    permission_classes = [IsTreasurer]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return BankStatementListSerializer
        return BankStatementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list":
            return qs.annotate(rows_count=Count("transactions"))
        return qs

    def create(self, request, *args, **kwargs):
        """Загрузить файл выписки. Разбирает и сопоставляет, но не проводит."""
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Файл не передан."},
                            status=status.HTTP_400_BAD_REQUEST)
        if upload.size > 10 * 1024 * 1024:
            return Response({"detail": "Файл больше 10 МБ — это не выписка."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            statement, stats = import_statement(
                require_org(request), raw=upload.read(), file_name=upload.name,
                user=request.user,
            )
        except (StatementError, StatementImportError) as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        data = BankStatementSerializer(statement).data
        data["stats"] = stats
        data["summary"] = statement_summary(statement)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Провести выписку: создать платежи по опознанным строкам."""
        statement = self.get_object()
        if statement.status == BankStatement.STATUS_APPLIED:
            return Response({"detail": "Эта выписка уже проведена."},
                            status=status.HTTP_400_BAD_REQUEST)
        result = apply_statement(statement, user=request.user)
        return Response({
            **result,
            "statement": BankStatementSerializer(statement).data,
        })

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        return Response(statement_summary(self.get_object()))


class BankTransactionViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    """
    Строки выписки. Правится только привязка к участку.

    Суммы и даты приходят из банка: правка их создала бы расхождение с
    выпиской, которое потом никто не объяснит.
    """

    queryset = BankTransaction.objects.select_related("plot", "member")
    serializer_class = BankTransactionSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["statement", "status", "match_kind"]
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        # Ручная привязка помечается отдельно: по журналу должно быть
        # видно, где сработал автомат, а где решил человек.
        instance = serializer.save()
        if "plot" in serializer.validated_data:
            instance.match_kind = BankTransaction.MATCH_MANUAL
            instance.save(update_fields=["match_kind", "updated_at"])
