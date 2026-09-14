"""
HTTP-слой платежей.

Разделение ответственности здесь принципиально: член СНТ обращается только
к своим начислениям и создаёт только намерение, а деньги подтверждает
вебхук провайдера. Вьюхи не создают Payment напрямую нигде.
"""
import logging
import uuid

from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Charge
from core.permissions import IsOrgMember, IsTreasurer, OrgQuerysetMixin

from .drivers import ProviderError, WebhookAuthError, get_driver
from .models import ObligatoryPayment, PaymentIntent, PaymentProvider
from .serializers import (
    ObligatoryPaymentSerializer,
    PaymentIntentSerializer,
    PaymentProviderPublicSerializer,
    PayRequestSerializer,
)
from .services import build_debt_allocation, confirm_intent, create_intent, fail_intent, PaymentError

log = logging.getLogger(__name__)


def _member_charges(request):
    """
    Неоплаченные начисления текущего пользователя.

    Опора на member текущего пользователя, а не на присланные идентификаторы:
    иначе можно было бы «оплатить» чужое начисление и закрыть чужой долг.
    """
    member = getattr(request.user, "member", None)
    if member is None:
        return Charge.objects.none()
    return (
        Charge.objects.filter(
            organization=request.org,
            plot__ownerships__member=member,
            plot__ownerships__date_to__isnull=True,
        )
        .select_related("charge_type", "period", "plot")
        .prefetch_related("payments")
        .distinct()
        .order_by("period__year", "period__month", "pk")
    )


class MyDebtView(APIView):
    """Долг текущего члена СНТ и доступность онлайн-оплаты."""

    permission_classes = [IsOrgMember]

    def get(self, request):
        charges = list(_member_charges(request))
        allocation = build_debt_allocation(charges)

        provider = PaymentProvider.objects.filter(
            organization=request.org,
            direction=PaymentProvider.DIRECTION_IN,
            is_active=True,
        ).order_by("-is_default").first()

        online_available = bool(
            provider and provider.is_configured
            and provider.kind != PaymentProvider.KIND_MANUAL
        )

        return Response({
            "total_debt": sum((amount for _, amount in allocation), start=0) or 0,
            "charges": [
                {
                    "id": charge.pk,
                    "charge_type_name": charge.charge_type.name,
                    "period_label": str(charge.period),
                    "plot_number": charge.plot.number,
                    "amount": charge.amount,
                    "paid_amount": charge.paid_amount,
                    "debt": debt,
                }
                for charge, debt in allocation
            ],
            "online_available": online_available,
            "provider": (
                PaymentProviderPublicSerializer(provider).data
                if online_available else None
            ),
        })


class PayView(APIView):
    """Создать намерение оплаты и вернуть ссылку на форму провайдера."""

    permission_classes = [IsOrgMember]

    def post(self, request):
        serializer = PayRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = getattr(request.user, "member", None)
        if member is None:
            return Response(
                {"detail": "Учётная запись не связана с членом СНТ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        charges = list(_member_charges(request))
        requested = serializer.validated_data.get("charge_ids")
        if requested:
            allowed = {c.pk for c in charges}
            unknown = set(requested) - allowed
            if unknown:
                # Не «не найдено», а именно отказ: начисление существует,
                # но принадлежит не этому человеку.
                return Response(
                    {"detail": "Среди выбранных начислений есть чужие."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            charges = [c for c in charges if c.pk in set(requested)]

        allocation = build_debt_allocation(charges)
        if not allocation:
            return Response(
                {"detail": "Задолженности нет."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = PaymentProvider.objects.filter(
            organization=request.org,
            direction=PaymentProvider.DIRECTION_IN,
            is_active=True,
        ).order_by("-is_default").first()
        if provider is None:
            return Response(
                {"detail": "В этом СНТ не настроен приём онлайн-оплаты."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Повторное нажатие не должно плодить платежи: если по тому же
        # набору начислений уже есть неоплаченное намерение со ссылкой,
        # возвращаем его.
        wanted = {(charge.pk, amount) for charge, amount in allocation}
        for existing in PaymentIntent.objects.filter(
            organization=request.org, member=member,
            status=PaymentIntent.STATUS_PENDING,
        ).prefetch_related("items"):
            if existing.confirmation_url and {
                (i.charge_id, i.amount) for i in existing.items.all()
            } == wanted:
                return Response(PaymentIntentSerializer(existing).data)

        try:
            intent = create_intent(
                organization=request.org,
                provider=provider,
                allocation=allocation,
                member=member,
                created_by=request.user,
                idempotency_key=uuid.uuid4().hex,
            )
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Возврат именно на дашборд: раздел /billing члену СНТ закрыт
        # роутером, человек попал бы на редирект вместо результата оплаты.
        # Идентификатор намерения — чтобы страница показала исход.
        return_url = request.build_absolute_uri(f"/dashboard?payment={intent.pk}")
        try:
            created = get_driver(provider).create_payment(intent, return_url)
        except ProviderError as exc:
            # Намерение остаётся в базе помеченным как ошибочное: так видно,
            # что попытка была, и есть за что зацепиться при разборе.
            fail_intent(intent.pk, status=PaymentIntent.STATUS_FAILED,
                        reason=str(exc))
            return Response({"detail": str(exc)},
                            status=status.HTTP_502_BAD_GATEWAY)

        intent.provider_payment_id = created.provider_payment_id
        intent.confirmation_url = created.confirmation_url
        intent.last_event = created.raw or None
        intent.save(update_fields=[
            "provider_payment_id", "confirmation_url", "last_event", "updated_at"
        ])
        return Response(PaymentIntentSerializer(intent).data)


class MyIntentViewSet(OrgQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """История платежей текущего члена — для страницы возврата с оплаты."""

    queryset = PaymentIntent.objects.select_related("provider").prefetch_related(
        "items__charge__charge_type", "items__charge__period", "items__charge__plot"
    )
    serializer_class = PaymentIntentSerializer
    permission_classes = [IsOrgMember]

    def get_queryset(self):
        qs = super().get_queryset()
        member = getattr(self.request.user, "member", None)
        # Казначей и председатель видят все намерения своего СНТ, член — свои.
        if getattr(self.request.user, "role", None) == "member":
            qs = qs.filter(member=member) if member else qs.none()
        return qs


@method_decorator(csrf_exempt, name="dispatch")
class WebhookView(APIView):
    """
    Приёмник уведомлений провайдера.

    Открыт без аутентификации — провайдер не носит наших токенов. Подлинность
    доказывает драйвер: подписью или обратным запросом к API. Адрес включает
    идентификатор провайдера, чтобы знать, чьими ключами проверять; секретом
    он не является и безопасность на него не опирается.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, provider_id):
        provider = PaymentProvider.objects.filter(
            pk=provider_id, is_active=True
        ).first()
        if provider is None:
            return Response({"detail": "Unknown provider."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            event = get_driver(provider).parse_webhook(request)
        except WebhookAuthError as exc:
            # Подделка или сбой проверки: отвечаем 400, чтобы попытка была
            # видна в логах провайдера, и ничего не меняем.
            log.warning("Вебхук провайдера %s не прошёл проверку: %s",
                        provider.pk, exc)
            return Response({"detail": "Signature check failed."},
                            status=status.HTTP_400_BAD_REQUEST)
        except ProviderError as exc:
            log.warning("Вебхук провайдера %s не разобран: %s", provider.pk, exc)
            return Response({"detail": "Cannot process event."},
                            status=status.HTTP_400_BAD_REQUEST)

        intent = self._find_intent(provider, event)
        if intent is None:
            # 404, а не 200: провайдер повторит, и это попадёт в его журнал.
            log.warning("Вебхук провайдера %s: намерение не найдено (%s)",
                        provider.pk, event.provider_payment_id)
            return Response({"detail": "Intent not found."},
                            status=status.HTTP_404_NOT_FOUND)

        if event.status == "succeeded":
            confirm_intent(intent.pk, event=event.raw)
        elif event.status in ("canceled", "failed"):
            fail_intent(
                intent.pk,
                status=(PaymentIntent.STATUS_CANCELED
                        if event.status == "canceled"
                        else PaymentIntent.STATUS_FAILED),
                reason="Платёж не завершён на стороне провайдера.",
                event=event.raw,
            )
        # pending и прочее просто фиксируем, ничего не меняя.

        return Response({"ok": True})

    @staticmethod
    def _find_intent(provider, event):
        qs = PaymentIntent.objects.filter(provider=provider)
        if event.provider_payment_id:
            intent = qs.filter(
                provider_payment_id=event.provider_payment_id
            ).first()
            if intent is not None:
                return intent
            # Робокасса присылает наш же InvId, он же первичный ключ.
            if str(event.provider_payment_id).isdigit():
                found = qs.filter(pk=int(event.provider_payment_id)).first()
                if found is not None:
                    return found
        # ЮKassa кладёт идентификатор намерения в metadata — запасной путь,
        # если provider_payment_id не успел сохраниться из-за обрыва связи.
        meta = (event.raw or {}).get("metadata") or {}
        intent_id = meta.get("intent_id")
        if intent_id and str(intent_id).isdigit():
            return qs.filter(pk=int(intent_id)).first()
        return None


class ObligatoryPaymentViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    """
    Реестр обязательных платежей товарищества.

    Только председатель и казначей: это расходы организации, рядовому члену
    они не адресованы. Направление исходящее — деньги уходят со счёта СНТ.
    """

    queryset = ObligatoryPayment.objects.select_related("provider", "paid_by")
    serializer_class = ObligatoryPaymentSerializer
    permission_classes = [IsTreasurer]
    filterset_fields = ["status", "kind"]
    search_fields = ["title", "recipient", "notes"]
    ordering_fields = ["due_date", "amount", "status"]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)

    def perform_update(self, serializer):
        # Кто провёл платёж, фиксируем автоматически: вручную это поле
        # заполняют неохотно, а при разборе расхождений оно нужнее всего.
        if serializer.validated_data.get("status") == ObligatoryPayment.STATUS_PAID:
            serializer.save(paid_by=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """
        Ближайшие и просроченные — то, ради чего реестр и нужен.

        Просроченные идут первыми: пропущенный срок важнее предстоящего.
        """
        from django.utils import timezone

        horizon = timezone.localdate() + timezone.timedelta(days=30)
        qs = self.get_queryset().filter(
            status=ObligatoryPayment.STATUS_PLANNED, due_date__lte=horizon
        ).order_by("due_date")
        return Response(self.get_serializer(qs, many=True).data)
