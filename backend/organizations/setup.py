"""
Мастер нового садоводства: товарищество, председатель и казначей —
одной транзакцией.

Одной — потому что пол-садоводства хуже, чем ни одного: организация без
председателя висит в списке, и войти в неё некому, а повторный запуск
мастера плодит дубль.

Председатель и казначей заводятся членами СНТ, а не голыми учётками:
у них есть участки и долги, как у всех, и личный кабинет им нужен так
же. Когда потом загрузится реестр, их участки привяжутся к этим же
записям — член ищется по ФИО.
"""
from django.db import transaction
from rest_framework import serializers

from .models import Organization
from .serializers import OrganizationSerializer

ORG_FIELDS = (
    "name", "full_name", "inn", "kpp", "ogrn", "legal_address", "phone",
    "email", "website", "timezone", "fee_period",
    "bank_account", "bank_name", "bank_bic", "bank_corr_account",
)


class PersonSerializer(serializers.Serializer):
    last_name = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=100)
    patronymic = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)


class SetupSerializer(serializers.Serializer):
    organization = serializers.DictField()
    chairman = PersonSerializer()
    treasurer = PersonSerializer(required=False, allow_null=True)

    def validate_organization(self, data):
        unknown = set(data) - set(ORG_FIELDS)
        if unknown:
            raise serializers.ValidationError(
                f"Неизвестные поля: {', '.join(sorted(unknown))}")
        s = OrganizationSerializer(data={k: v for k, v in data.items() if v not in (None,)})
        s.is_valid(raise_exception=True)
        name = s.validated_data["name"].strip()
        if Organization.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError(
                {"name": f"Товарищество «{name}» уже есть на платформе."})
        return s.validated_data

    def validate(self, attrs):
        t = attrs.get("treasurer")
        c = attrs["chairman"]
        if t and all(t.get(k, "").strip().lower() == c.get(k, "").strip().lower()
                     for k in ("last_name", "first_name", "patronymic")):
            raise serializers.ValidationError(
                {"treasurer": "Казначей совпадает с председателем. Если это один "
                              "человек — не заполняйте казначея: председателю и "
                              "так доступно всё, что казначею."})
        return attrs


@transaction.atomic
def create_snt(data):
    """Создать СНТ и учётки. Пароли возвращаются один раз — в базе их нет."""
    from accounts.models import User
    from accounts.provisioning import issue_account
    from members.models import Member

    org = Organization.objects.create(**data["organization"])
    accounts = []
    for role, person in ((User.ROLE_CHAIRMAN, data["chairman"]),
                         (User.ROLE_TREASURER, data.get("treasurer"))):
        if not person:
            continue
        member = Member.objects.create(
            organization=org,
            last_name=person["last_name"].strip(),
            first_name=person["first_name"].strip(),
            patronymic=person.get("patronymic", "").strip(),
            phone=person.get("phone", "").strip(),
            email=person.get("email", "").strip(),
            status=Member.STATUS_ACTIVE,
        )
        user, password = issue_account(member, organization=org)
        user.role = role
        user.first_name = member.first_name
        user.last_name = member.last_name
        user.email = member.email
        user.save(update_fields=["role", "first_name", "last_name", "email"])
        accounts.append({
            "role": role,
            "role_display": dict(User.ROLE_CHOICES)[role],
            "full_name": " ".join(p for p in (member.last_name, member.first_name,
                                              member.patronymic) if p),
            "username": user.username,
            "password": password,
        })
    return org, accounts
