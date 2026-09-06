from rest_framework import serializers
from .models import ChargeType, BillingPeriod, Charge, Payment


class ChargeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChargeType
        exclude = ("organization",)


class BillingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPeriod
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")


class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(
        source="recorded_by.get_full_name", read_only=True
    )

    class Meta:
        model = Payment
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at", "recorded_by")


class ChargeSerializer(serializers.ModelSerializer):
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    debt = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    charge_type_name = serializers.CharField(source="charge_type.name", read_only=True)
    plot_number = serializers.CharField(source="plot.number", read_only=True)
    period_label = serializers.CharField(source="period.__str__", read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Charge
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")


class BulkMembershipChargeSerializer(serializers.Serializer):
    """Запрос на массовое создание членских взносов."""
    period_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    description = serializers.CharField(max_length=500, required=False, default="")


class BulkTargetChargeSerializer(serializers.Serializer):
    """Запрос на создание целевых взносов."""
    period_id = serializers.IntegerField()
    charge_type_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    plot_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_null=True
    )
    description = serializers.CharField(max_length=500, required=False, default="")
