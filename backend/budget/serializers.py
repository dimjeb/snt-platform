from decimal import Decimal

from rest_framework import serializers

from .models import Budget, BudgetItem, Expense
from .services import as_json, fee_calc, item_amount


class BudgetItemSerializer(serializers.ModelSerializer):
    section_display = serializers.CharField(source="get_section_display", read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2,
                                      min_value=Decimal("0"), required=False)

    class Meta:
        model = BudgetItem
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")

    def validate_budget(self, budget):
        org = getattr(self.context.get("request"), "org", None)
        if org is not None and budget.organization_id != org.id:
            raise serializers.ValidationError("Смета не найдена.")
        return budget

    def validate(self, attrs):
        budget = attrs.get("budget") or (self.instance and self.instance.budget)
        if budget and budget.is_approved:
            raise serializers.ValidationError(
                "Смета утверждена собранием — статьи не меняются. Если собрание "
                "приняло изменения, верните смету в черновик и поправьте.")
        if self.instance is not None and "budget" in attrs \
                and attrs["budget"].pk != self.instance.budget_id:
            raise serializers.ValidationError({"budget": "Статью не переносят в другую смету."})
        q = attrs.get("quantity", getattr(self.instance, "quantity", None))
        p = attrs.get("unit_price", getattr(self.instance, "unit_price", None))
        a = attrs.get("amount", getattr(self.instance, "amount", None))
        amount = item_amount(q, p, a)
        if amount is None:
            raise serializers.ValidationError(
                {"amount": "Укажите сумму или количество и цену."})
        attrs["amount"] = amount
        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = BudgetItemSerializer(many=True, read_only=True)
    calc = serializers.SerializerMethodField()
    copy_from = serializers.IntegerField(write_only=True, required=False,
                                         help_text="Год сметы, статьи которой перенести")

    class Meta:
        model = Budget
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at", "status", "approved_at",
                            "protocol_number")

    def get_calc(self, obj):
        calc = fee_calc(obj)
        calc.pop("areas", None)
        return as_json(calc)

    def validate_year(self, year):
        if self.instance is not None and year != self.instance.year:
            raise serializers.ValidationError("Год сметы не меняется.")
        if not 2000 <= year <= 2100:
            raise serializers.ValidationError("Год вне разумных пределов.")
        org = getattr(self.context.get("request"), "org", None)
        if self.instance is None and org is not None \
                and Budget.objects.filter(organization=org, year=year).exists():
            raise serializers.ValidationError(f"Смета на {year} год уже есть.")
        return year

    def validate(self, attrs):
        if self.instance is not None and self.instance.is_approved \
                and set(attrs) - {"notes"}:
            raise serializers.ValidationError(
                "Смета утверждена собранием — менять её нельзя. Если собрание "
                "приняло изменения, верните смету в черновик.")
        return attrs


class ExpenseSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True, default=None)
    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name",
                                             read_only=True, default=None)

    class Meta:
        model = Expense
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at", "recorded_by")

    def validate_item(self, item):
        org = getattr(self.context.get("request"), "org", None)
        if item is not None and org is not None and item.organization_id != org.id:
            raise serializers.ValidationError("Статья не найдена.")
        return item

    def validate(self, attrs):
        item = attrs.get("item", getattr(self.instance, "item", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        if item is not None and date is not None and item.budget.year != date.year:
            raise serializers.ValidationError(
                {"item": f"Статья из сметы на {item.budget.year} год, а расход — "
                         f"{date.year} года."})
        return attrs


class ApproveSerializer(serializers.Serializer):
    approved_at = serializers.DateField()
    protocol_number = serializers.CharField(max_length=50, required=False, allow_blank=True)


class ChargeMembershipSerializer(serializers.Serializer):
    due_date = serializers.DateField(required=False, allow_null=True)
    penalty_percent = serializers.DecimalField(max_digits=5, decimal_places=2,
                                               min_value=Decimal("0"),
                                               max_value=Decimal("100"),
                                               required=False, allow_null=True)
