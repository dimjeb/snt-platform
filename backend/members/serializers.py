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


class PlotSerializer(serializers.ModelSerializer):
    current_owner = serializers.SerializerMethodField()

    class Meta:
        model = Plot
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")

    def get_current_owner(self, obj):
        owner = obj.current_owner
        if owner:
            return {"id": owner.id, "full_name": owner.full_name}
        return None


class PlotOwnershipSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    plot_number = serializers.CharField(source="plot.number", read_only=True)

    class Meta:
        model = PlotOwnership
        exclude = ("organization",)
        read_only_fields = ("created_at", "updated_at")
