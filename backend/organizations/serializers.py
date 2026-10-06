from rest_framework import serializers
from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"
        # Логотип — только через organizations/current/logo/: там проверка
        # формата и размера.
        read_only_fields = ("created_at", "updated_at", "logo")

    # Поля, которые председатель своего СНТ менять не может: включать и
    # выключать товарищество на платформе — решение администратора.
    PLATFORM_ONLY = ("is_active",)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if not (request and request.user.is_authenticated and request.user.is_superuser):
            for name in self.PLATFORM_ONLY:
                fields[name].read_only = True
        return fields


class OrganizationShortSerializer(serializers.ModelSerializer):
    """Краткое представление для вложенных объектов."""
    # Путь от корня сайта, а не полный адрес: за Caddy бэкенд не знает
    # внешнего имени, и полный адрес вышел бы http://backend:8000/...
    logo = serializers.SerializerMethodField()

    def get_logo(self, obj):
        return obj.logo.url if obj.logo else None

    class Meta:
        model = Organization
        fields = ("id", "name", "logo")
