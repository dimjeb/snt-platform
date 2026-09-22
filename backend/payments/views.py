"""
HTTP-слой платежей.

Разделение ответственности здесь принципиально: член СНТ обращается только
к своим начислениям и создаёт только намерение, а деньги подтверждает
вебхук провайдера. Вьюхи не создают Payment напрямую нигде.
"""
import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Charge, ChargeType
from core.audit import record_access
from core.models import AccessLog
from core.permissions import (
    IsOrgMember, IsTreasurer, OrgQuerysetMixin, require_org,
)

from .drivers import ProviderError, WebhookAuthError, get_driver
from .qr import QRError, build_payment_payload, build_purpose, render_png
from .models import ObligatoryPayment, PaymentIntent, PaymentProvider
from .serializers import (
    ObligatoryPaymentSerializer,
    PaymentIntentSerializer,
    PaymentProviderPublicSerializer,
    PayRequestSerializer,
)
from .services import (
    build_debt_allocation,
    build_explicit_allocation,
    confirm_intent,
    create_intent,
    fail_intent,
    ForeignChargeError,
    PaymentError,
)

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


def _member_meters(request):
    """
    Счётчики участков члена с последним переданным показанием.

    Нужно, чтобы в кабинете было видно основание начисления за свет:
    сумма без показания, из которого она получена, у человека доверия
    не вызывает и заканчивается звонком казначею.
    """
    from electricity.models import Meter

    member = getattr(request.user, "member", None)
    if member is None:
        return []

    meters = (
        Meter.objects.filter(
            organization=request.org,
            is_main=False,
            plot__ownerships__member=member,
            plot__ownerships__date_to__isnull=True,
        )
        .select_related("plot")
        .prefetch_related("readings")
        .distinct()
    )

    result = []
    for meter in meters:
        # Показания подтянуты prefetch-ем, поэтому максимум берём в памяти:
        # .order_by().first() здесь сходил бы в базу на каждый счётчик.
        last = max(meter.readings.all(), key=lambda r: r.date, default=None)
        result.append({
            "plot_number": meter.plot.number if meter.plot else None,
            "serial_number": meter.serial_number,
            "last_reading_date": last.date if last else None,
            "last_reading_value": last.value if last else None,
            # Показание могло быть не снято, а рассчитано по среднему.
            # Показывать такое как своё — значит уверять человека, что
            # он его сдавал, и оставлять без объяснения, откуда сумма.
            "last_reading_estimated": bool(last and last.is_estimated),
        })
    return result


class MyDebtView(APIView):
    """Долг текущего члена СНТ и доступность онлайн-оплаты."""

    permission_classes = [IsOrgMember]

    def get(self, request):
        member = getattr(request.user, "member", None)
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

        rows = []
        electricity_debt = Decimal("0")
        other_debt = Decimal("0")
        for charge, debt in allocation:
            category = charge.charge_type.category
            is_power = category == ChargeType.TYPE_ELECTRICITY
            if is_power:
                electricity_debt += debt
            else:
                other_debt += debt
            rows.append({
                "id": charge.pk,
                "charge_type_name": charge.charge_type.name,
                # Делить на группы по категории, а не по названию: название
                # задаёт казначей, и «Электричество» вместо «Электроэнергия»
                # молча увело бы сумму не в ту колонку.
                "category": category,
                "period_label": str(charge.period),
                "plot_number": charge.plot.number,
                "amount": charge.amount,
                "paid_amount": charge.paid_amount,
                "debt": debt,
                # Основание начисления за свет: сколько кВт·ч и по какому тарифу.
                "kwh": charge.kwh,
                "tariff": charge.tariff,
            })

        # Аванс: деньги, которые человек уже заплатил вперёд. Показать
        # их обязательно — иначе он видит долг при том, что деньги
        # товарищество получило, и идёт разбираться к казначею.
        from billing.credits import credit_balance

        advance = sum(
            (credit_balance(plot) for plot in member.plots), Decimal("0")
        ) if member else Decimal("0")

        return Response({
            "total_debt": electricity_debt + other_debt,
            "electricity_debt": electricity_debt,
            "other_debt": other_debt,
            "advance": advance,
            "charges": rows,
            "meters": _member_meters(request),
            "online_available": online_available,
            "provider": (
                PaymentProviderPublicSerializer(provider).data
                if online_available else None
            ),
        })


class MyPaymentQRView(APIView):
    """
    Платёжный QR по ГОСТ для оплаты переводом на счёт товарищества.

    Нужен там, где эквайринга нет: человек сканирует код в приложении
    своего банка, реквизиты и сумма подставляются сами. Товарищество
    за это не платит ничего — это обычный перевод, а не эквайринг.
    """

    permission_classes = [IsOrgMember]

    def get(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response(
                {"detail": "Учётная запись не связана с членом СНТ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_amount = request.query_params.get("amount")
        amount = None
        if raw_amount:
            try:
                amount = Decimal(str(raw_amount))
            except (InvalidOperation, ValueError):
                return Response({"detail": "Сумма указана неверно."},
                                status=status.HTTP_400_BAD_REQUEST)
            charges = list(_member_charges(request))
            total = sum((c.debt for c in charges), Decimal("0"))
            if amount > total:
                return Response(
                    {"detail": f"Сумма больше задолженности: "
                               f"к оплате доступно {total} ₽."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        plot_numbers = [plot.number for plot in member.plots]
        purpose = build_purpose(request.org, plot_numbers=plot_numbers)

        try:
            payload = build_payment_payload(
                request.org,
                amount=amount,
                purpose=purpose,
                pers_acc=plot_numbers[0] if plot_numbers else "",
            )
        except QRError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        record_access(request, "платёжный QR", AccessLog.ACTION_DETAIL)

        return Response({
            "payload": payload,
            "amount": amount,
            "purpose": purpose,
            # Реквизиты отдаём отдельно: не у всех под рукой сканер, и
            # переписать их руками должно быть можно.
            "requisites": {
                "name": request.org.payment_name,
                "inn": request.org.inn,
                "kpp": request.org.kpp,
                "account": request.org.bank_account,
                "bank": request.org.bank_name,
                "bic": request.org.bank_bic,
                "corr_account": request.org.bank_corr_account,
            },
        })


class MyPaymentQRImageView(APIView):
    """Тот же QR картинкой — чтобы фронт не тянул генератор кодов."""

    permission_classes = [IsOrgMember]

    def get(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return HttpResponse(status=400)

        raw_amount = request.query_params.get("amount")
        amount = None
        if raw_amount:
            try:
                amount = Decimal(str(raw_amount))
            except (InvalidOperation, ValueError):
                return HttpResponse(status=400)

        plot_numbers = [plot.number for plot in member.plots]
        try:
            payload = build_payment_payload(
                request.org,
                amount=amount,
                purpose=build_purpose(request.org, plot_numbers=plot_numbers),
                pers_acc=plot_numbers[0] if plot_numbers else "",
            )
        except QRError:
            return HttpResponse(status=400)

        response = HttpResponse(render_png(payload), content_type="image/png")
        # QR содержит сумму долга конкретного человека — в общий кеш ему
        # попадать незачем.
        response["Cache-Control"] = "private, max-age=0, no-store"
        return response


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

        explicit = serializer.validated_data.get("allocations")
        try:
            if explicit:
                allocation = build_explicit_allocation(charges, explicit)
            else:
                allocation = build_debt_allocation(
                    charges, amount=serializer.validated_data.get("amount")
                )
        except ForeignChargeError as exc:
            # Не «не найдено», а именно отказ: начисление существует,
            # но принадлежит не этому человеку.
            return Response({"detail": str(exc)},
                            status=status.HTTP_403_FORBIDDEN)
        except PaymentError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
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
        serializer.save(organization=require_org(self.request))

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
