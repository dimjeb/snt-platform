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


class MemberShortSerializer(serializers.ModelSerializer):
    """Компактное представление для списков выбора (select)."""
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Member
        fields = ("id", "full_name", "status")


class PlotSerializer(serializers.ModelSerializer):
    current_owner = serializers.SerializerMethodField(read_only=True)
    # write-only: передаётся при создании/редактировании для назначения владельца
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

    def _set_owner(self, plot, owner_id):
        """Устанавливает текущего владельца участка через PlotOwnership."""
        current = plot.ownerships.filter(date_to__isnull=True).first()
        if owner_id is None:
            # Снять владельца: закрыть текущее владение
            if current:
                current.date_to = date.today()
                current.save()
            return
        # Проверяем, нужно ли что-то менять
        if current and current.member_id == owner_id:
            return  # уже этот владелец — ничего не делаем
        # Закрываем предыдущее владение
        if current:
            current.date_to = date.today()
            current.save()
        # Создаём новое владение
        PlotOwnership.objects.create(
            plot=plot,
            member_id=owner_id,
            organization=plot.organization,
            date_from=date.today(),
        )

    def create(self, validated_data):
        owner_id = validated_data.pop("current_owner_id", None)
        plot = super().create(validated_data)
        if owner_id is not None:
            self._set_owner(plot, owner_id)
        return plot

    def update(self, instance, validated_data):
        owner_id = validated_data.pop("current_owner_id", None)
        plot = super().update(instance, validated_data)
        # owner_id передан явно клиентом (None = снять, число = назначить/сменить)
        if "current_owner_id" in self.initial_data:
            self._set_owner(plot, owner_id)
        return plot


class PlotOwnershipSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    plot_number = serializers.CharField(source="plot.number", read_only=True)

    class Meta:
        model = PlotOwnership
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")
