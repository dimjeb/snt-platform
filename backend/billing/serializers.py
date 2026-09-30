from rest_framework import serializers
from .services import BASIS_FLAT, BASIS_PER_SOTKA
from .models import BankStatement, BankTransaction, ChargeType, BillingPeriod, Charge, Payment


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


class BulkChargeBasisMixin(serializers.Serializer):
    """
    Общая часть запросов на массовое начисление: чем считаем.

    flat — одна сумма на участок, per_sotka — ставка за сотку.
    Поля amount и rate необязательны по отдельности, но ровно одно из
    них обязано прийти: проверяет validate. Иначе при опечатке во фронте
    ушло бы начисление на нулевую сумму по всем участкам, и заметили бы
    это уже по жалобам садоводов.
    """
    basis = serializers.ChoiceField(
        choices=[(BASIS_FLAT, "Фиксированная сумма"),
                 (BASIS_PER_SOTKA, "Ставка за сотку")],
        required=False, default=BASIS_FLAT,
    )
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    rate = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    description = serializers.CharField(max_length=500, required=False, default="")

    def validate(self, data):
        basis = data.get("basis", BASIS_FLAT)
        if basis == BASIS_PER_SOTKA:
            if not data.get("rate") or data["rate"] <= 0:
                raise serializers.ValidationError(
                    {"rate": "Укажите ставку за сотку больше нуля."}
                )
            data["amount"] = None
        else:
            if data.get("amount") is None or data["amount"] <= 0:
                raise serializers.ValidationError(
                    {"amount": "Укажите сумму взноса больше нуля."}
                )
            data["rate"] = None
        return data


class BulkMembershipChargeSerializer(BulkChargeBasisMixin):
    """Запрос на массовое создание членских взносов. Период — из URL."""


class BulkTargetChargeSerializer(BulkChargeBasisMixin):
    """Запрос на создание целевых взносов. Период — из URL."""
    charge_type_id = serializers.IntegerField()
    plot_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_null=True
    )


class BankTransactionSerializer(serializers.ModelSerializer):
    plot_number = serializers.CharField(source="plot.number", read_only=True,
                                        default=None)
    member_name = serializers.CharField(source="member.full_name",
                                        read_only=True, default=None)
    match_kind_display = serializers.CharField(source="get_match_kind_display",
                                               read_only=True)
    status_display = serializers.CharField(source="get_status_display",
                                           read_only=True)

    class Meta:
        model = BankTransaction
        exclude = ("organization",)
        # Менять руками можно только привязку к участку: суммы и даты
        # приходят из банка, и правка их означала бы расхождение с
        # выпиской, которое потом никто не объяснит.
        read_only_fields = (
            "statement", "doc_number", "date", "amount", "payer_name",
            "payer_account", "purpose", "status", "created_at", "updated_at",
        )


class BankStatementSerializer(serializers.ModelSerializer):
    transactions = BankTransactionSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display",
                                           read_only=True)
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = BankStatement
        exclude = ("organization",)
        read_only_fields = ("status", "applied_at", "uploaded_by")


class BankStatementListSerializer(serializers.ModelSerializer):
    """Без строк — список выписок не должен тащить тысячи платежей."""
    status_display = serializers.CharField(source="get_status_display",
                                           read_only=True)
    rows_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BankStatement
        fields = ("id", "file_name", "account", "date_from", "date_to",
                  "status", "status_display", "applied_at", "created_at",
                  "rows_count")
