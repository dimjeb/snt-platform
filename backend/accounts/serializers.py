from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "phone", "role", "organization", "member",
            "is_active", "date_joined",
        )
        read_only_fields = ("date_joined",)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "phone", "role", "password")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.organization = self.context["request"].org
        user.set_password(password)
        user.save()
        return user


class MeSerializer(serializers.ModelSerializer):
    """Профиль текущего пользователя."""
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    # Личный кабинет члена стартует с me.member_id: без этого поля страница
    # показаний выходит на первой же строке и счётчик не находится никогда.
    member_id = serializers.IntegerField(source="member.id", read_only=True, default=None)
    # Фронт по этому флагу уводит на принудительную смену пароля.
    must_change_password = serializers.BooleanField(read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "phone", "role", "organization", "organization_name", "member_id",
            "must_change_password",
        )
        read_only_fields = (
            "organization", "organization_name", "member_id",
            "must_change_password",
        )

    def get_role(self, obj):
        """
        Роль, согласованная с тем, как решает бэкенд.

        Суперадмина здесь определяют по is_superuser: так ветвятся и
        OrganizationMiddleware, и OrgQuerysetMixin, и IsOrgMember. Фронт же
        смотрит на role, а createsuperuser её не выставляет — из-за чего
        суперадмин выглядел в интерфейсе рядовым членом: без переключателя
        СНТ, без раздела управления, с личным кабинетом на дашборде.
        """
        if obj.is_superuser:
            return User.ROLE_SUPERADMIN
        return obj.role


class ChangePasswordSerializer(serializers.Serializer):
    """
    Смена собственного пароля.

    Старый пароль спрашиваем всегда, даже когда он временный: иначе
    оставленная без присмотра открытая вкладка позволяет посторонему
    закрепить за собой чужую учётную запись.
    """

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Текущий пароль указан неверно.")
        return value

    def validate_new_password(self, value):
        user = self.context["request"].user
        # Та же политика, что и везде: минимум 10 символов, не словарный,
        # не из одних цифр, не похож на логин и ФИО.
        validate_password(value, user)
        return value

    def validate(self, attrs):
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "Новый пароль должен отличаться от текущего."}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user
