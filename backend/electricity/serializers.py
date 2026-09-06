from rest_framework import serializers
from .models import EnergyTariff, Meter, MeterReading


class EnergyTariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnergyTariff
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")


class MeterSerializer(serializers.ModelSerializer):
    plot_number = serializers.CharField(source="plot.number", read_only=True)

    class Meta:
        model = Meter
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")


class MeterReadingSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(
        source="submitted_by.get_full_name", read_only=True
    )
    meter_label = serializers.CharField(source="meter.__str__", read_only=True)

    class Meta:
        model = MeterReading
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at", "submitted_by")


class CalculateElectricitySerializer(serializers.Serializer):
    """Запрос на расчёт электроэнергии за период."""
    billing_period_id = serializers.IntegerField()
    period_date = serializers.DateField(help_text="Дата окончания расчётного периода (последнее показание).")
