from datetime import date
from rest_framework import serializers
from .models import Member, Plot, PlotOwnership


class MemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    current_plots = serializers.SerializerMethodField()

    class Meta:
        model = Member
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")

    def get_current_plots(self, obj):
        return [
            {"id": p.id, "number": p.number}
            for p in obj.plots
        ]

    def to_internal_value(self, data):
        # Пустая строка в незаполненной необязательной дате — обычный идиом
        # HTML-формы, но DateField в DRF её отвергает с 400. Приводим к null,
        # чтобы это не было тонкостью, которую обязан знать каждый клиент.
        if hasattr(data, "get") and data.get("joined_at") == "":
            data = data.copy()
            data["joined_at"] = None
        return super().to_internal_value(data)


class MemberShortSerializer(serializers.ModelSerializer):
    """Компактное представление для списков выбора (select)."""
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Member
        fields = ("id", "full_name", "status")


class PlotSerializer(serializers.ModelSerializer):
    # current_owner — первый собственник, оставлен для клиентов, которым
    # достаточно одного имени. Полный состав — в current_owners.
    current_owner = serializers.SerializerMethodField(read_only=True)
    current_owners = serializers.SerializerMethodField(read_only=True)
    # write-only: состав собственников целиком. Пустой список снимает всех.
    current_owner_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False,
        allow_empty=True,
    )
    # write-only, для одного собственника. Ровно то же самое, что
    # current_owner_ids=[id]: значение задаёт состав целиком, а не
    # добавляет ещё одного.
    current_owner_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Plot
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")

    def get_current_owner(self, obj):
        owner = obj.current_owner
        if owner:
            return {"id": owner.id, "full_name": owner.full_name}
        return None

    def get_current_owners(self, obj):
        return [
            {"id": m.id, "full_name": m.full_name} for m in obj.current_owners
        ]

    def _set_owners(self, plot, owner_ids):
        """
        Приводит состав текущих собственников участка к заданному.

        Владения тех, кого в списке нет, закрываются сегодняшней датой —
        история владения сохраняется. Тем, кто уже числится, ничего не
        меняем: иначе каждое сохранение формы плодило бы в истории
        владение длиной в ноль дней.
        """
        target = set(owner_ids or [])
        current = list(plot.ownerships.filter(date_to__isnull=True))
        for ownership in current:
            if ownership.member_id not in target:
                ownership.date_to = date.today()
                ownership.save(update_fields=["date_to", "updated_at"])
        existing = {o.member_id for o in current}
        for member_id in target - existing:
            PlotOwnership.objects.create(
                plot=plot,
                member_id=member_id,
                organization=plot.organization,
                date_from=date.today(),
            )

    def _owner_ids_from_input(self, validated_data):
        """
        Достаёт состав собственников из запроса.

        Возвращает (передан ли состав, список id). Клиент может прислать
        либо current_owner_ids (список), либо current_owner_id (одно
        значение или null) — второе оставлено для совместимости.
        """
        owner_ids = validated_data.pop("current_owner_ids", None)
        owner_id = validated_data.pop("current_owner_id", None)
        if "current_owner_ids" in self.initial_data:
            return True, list(owner_ids or [])
        if "current_owner_id" in self.initial_data:
            return True, [owner_id] if owner_id is not None else []
        return False, []

    def create(self, validated_data):
        given, owner_ids = self._owner_ids_from_input(validated_data)
        plot = super().create(validated_data)
        if given and owner_ids:
            self._set_owners(plot, owner_ids)
        return plot

    def update(self, instance, validated_data):
        given, owner_ids = self._owner_ids_from_input(validated_data)
        plot = super().update(instance, validated_data)
        if given:
            self._set_owners(plot, owner_ids)
        return plot


class PlotOwnershipSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    plot_number = serializers.CharField(source="plot.number", read_only=True)

    class Meta:
        model = PlotOwnership
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")
