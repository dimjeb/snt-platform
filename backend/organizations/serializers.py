from rest_framework import serializers
from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class OrganizationShortSerializer(serializers.ModelSerializer):
    """Краткое представление для вложенных объектов."""
    class Meta:
        model = Organization
        fields = ("id", "name", "logo")
