"""
Выдача учётных записей членам товарищества.

Одна реализация на всех: и массовая команда create_member_accounts, и
кнопка «Выдать доступ» в интерфейсе зовут отсюда. Две реализации
разъедутся — в одной пароль будет проходить политику, в другой нет, и
выяснится это на живом человеке.
"""
import secrets

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

# Без похожих друг на друга символов: пароль будут диктовать по телефону
# и переписывать с бумажки, а 0/O и 1/l/I в этом деле — источник звонков
# «у меня не входит».
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"

RU_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


class ProvisioningError(Exception):
    """Учётку выдать нельзя, и причина — для человека, а не для трейсбека."""


def translit(value: str) -> str:
    out = []
    for ch in (value or "").lower():
        if ch in RU_LAT:
            out.append(RU_LAT[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
    return "".join(out)


def make_password() -> str:
    """Три группы по четыре символа: xxxx-xxxx-xxxx."""
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


def make_username(member, taken=None) -> str:
    """
    Логин: фамилия латиницей плюс номер записи в реестре.

    Номер обязателен: ни ФИО, ни телефон, ни номер участка в реестре не
    уникальны — однофамильцы и общая собственность встречаются в первом
    же товариществе.
    """
    from .models import User

    base = translit(member.last_name) or translit(member.first_name) or "member"
    username = f"{base}-{member.pk}"
    if taken is None:
        exists = lambda name: User.objects.filter(username=name).exists()  # noqa: E731
    else:
        exists = lambda name: name in taken  # noqa: E731

    suffix = 0
    while exists(username):
        suffix += 1
        username = f"{base}-{member.pk}-{suffix}"
    return username


def checked_password() -> str:
    """Пароль, прошедший ту же политику, что и любой другой в системе."""
    password = make_password()
    try:
        validate_password(password)
    except ValidationError as exc:
        raise ProvisioningError(
            "Сгенерированный пароль не прошёл политику паролей: "
            + "; ".join(exc.messages)
        )
    return password


def issue_account(member, organization=None):
    """
    Завести учётку члену и вернуть (user, пароль).

    Пароль возвращается ровно один раз — в базе лежит только его хеш.
    Показать его повторно нельзя даже администратору; если потерян,
    остаётся сбросить.
    """
    from .models import User

    if User.objects.filter(member=member).exists():
        raise ProvisioningError(
            "У этого члена СНТ учётная запись уже есть. "
            "Если пароль потерян — сбросьте его."
        )

    password = checked_password()
    user = User(
        username=make_username(member),
        organization=organization or member.organization,
        member=member,
        role=User.ROLE_MEMBER,
        phone=member.phone or "",
        must_change_password=True,
        is_active=True,
    )
    user.set_password(password)
    user.save()
    return user, password


def reset_password(user):
    """
    Выдать новый временный пароль и снова потребовать смены.

    Возвращает пароль — тоже единожды.
    """
    password = checked_password()
    user.set_password(password)
    user.must_change_password = True
    user.is_active = True
    user.save(update_fields=["password", "must_change_password", "is_active"])
    return password
