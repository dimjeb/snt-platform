from rest_framework import serializers

from .models import PaymentIntent, PaymentIntentItem, PaymentProvider


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


class PayRequestSerializer(serializers.Serializer):
    """
    Запрос на оплату.

    charge_ids необязателен: без него оплачивается весь долг. Сумму клиент
    не передаёт вовсе — она считается на сервере по фактическим долгам,
    иначе долг закрывался бы копеечным платежом.
    """

    charge_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=False
    )
