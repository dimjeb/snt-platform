from decimal import Decimal
from rest_framework import serializers

from .models import (
    ObligatoryPayment,
    PaymentIntent,
    PaymentIntentItem,
    PaymentProvider,
)


class PaymentProviderPublicSerializer(serializers.ModelSerializer):
    """
    Провайдер глазами плательщика.

    Ни merchant_id, ни тем более ключи сюда не попадают: плательщику нужно
    знать только, что онлайн-оплата доступна и как она называется.
    """

    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = PaymentProvider
        fields = ("id", "title", "kind", "kind_display", "test_mode")


class PaymentIntentItemSerializer(serializers.ModelSerializer):
    charge_type_name = serializers.CharField(
        source="charge.charge_type.name", read_only=True
    )
    period_label = serializers.CharField(source="charge.period.__str__", read_only=True)
    plot_number = serializers.CharField(source="charge.plot.number", read_only=True)

    class Meta:
        model = PaymentIntentItem
        fields = ("id", "charge", "amount", "charge_type_name",
                  "period_label", "plot_number")


class PaymentIntentSerializer(serializers.ModelSerializer):
    items = PaymentIntentItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    provider_title = serializers.CharField(source="provider.title", read_only=True)

    class Meta:
        model = PaymentIntent
        fields = (
            "id", "amount", "status", "status_display", "confirmation_url",
            "provider", "provider_title", "paid_at", "error_message",
            "items", "created_at",
        )
        read_only_fields = fields


class PayAllocationSerializer(serializers.Serializer):
    """Сколько платить за конкретное начисление."""

    charge_id = serializers.IntegerField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0")
    )


class PayRequestSerializer(serializers.Serializer):
    """
    Запрос на оплату.

    charge_ids необязателен: без него берётся весь долг.

    amount — частичная оплата одной суммой: сколько всего заплатить.
    Разносит её по начислениям сервер (build_debt_allocation), от старых
    к новым.

    allocations — разбивка, заданная человеком построчно:
    [{"charge_id": 1, "amount": "500.00"}, ...]. Нужна, когда он хочет
    сам решить, за что платит. Каждая строка проверяется отдельно:
    начисление должно принадлежать ему, а сумма не может превышать его
    долг. Нулевые строки просто выпадают.

    amount и allocations вместе не принимаются: два источника одной и
    той же суммы рано или поздно разойдутся.
    """

    charge_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=False
    )
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        min_value=Decimal("1"),
    )
    allocations = PayAllocationSerializer(many=True, required=False)

    def validate(self, attrs):
        if attrs.get("allocations") and attrs.get("amount") is not None:
            raise serializers.ValidationError(
                "Укажите либо суммы по начислениям, либо общую сумму, но не оба."
            )
        return attrs


class ObligatoryPaymentSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_left = serializers.IntegerField(read_only=True, allow_null=True)
    paid_by_name = serializers.CharField(
        source="paid_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = ObligatoryPayment
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at", "paid_by")

    def validate(self, attrs):
        # Оплаченный платёж без даты — дыра в учёте: по нему не собрать
        # отчёт за период и не понять, когда ушли деньги.
        status_value = attrs.get("status", getattr(self.instance, "status", None))
        paid_date = attrs.get("paid_date", getattr(self.instance, "paid_date", None))
        if status_value == ObligatoryPayment.STATUS_PAID and not paid_date:
            raise serializers.ValidationError(
                {"paid_date": "У оплаченного платежа должна быть дата оплаты."}
            )
        return attrs
