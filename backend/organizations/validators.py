"""
Проверка банковских реквизитов.

Опечатка в номере счёта — это деньги, ушедшие не туда, и узнать об этом
можно через недели. Контрольный ключ ловит почти любую одиночную ошибку
сразу при вводе, поэтому проверяем на уровне модели, а не надеемся на
внимательность казначея.

Методика — Положение Банка России о порядке расчёта контрольного ключа.
"""
import re

from django.core.exceptions import ValidationError

# Весовые коэффициенты для 23 разрядов (3 разряда префикса + 20 счёта).
_WEIGHTS = [7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1]


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def account_key_is_valid(account: str, bic: str, *, is_correspondent: bool) -> bool:
    """
    Сходится ли контрольный ключ счёта.

    Префикс берётся из БИК и зависит от вида счёта: для расчётного это
    последние три цифры БИК, для корреспондентского — «0» плюс пятый и
    шестой разряды. Перепутать их местами — типичная ошибка, поэтому вид
    счёта здесь обязательный именованный аргумент.
    """
    account = _digits_only(account)
    bic = _digits_only(bic)
    if len(account) != 20 or len(bic) != 9:
        return False
    prefix = ("0" + bic[4:6]) if is_correspondent else bic[6:9]
    total = sum(int(d) * w for d, w in zip(prefix + account, _WEIGHTS))
    return total % 10 == 0


def validate_bic(value):
    digits = _digits_only(value)
    if len(digits) != 9:
        raise ValidationError("БИК состоит из 9 цифр.")


def validate_account_number(value):
    digits = _digits_only(value)
    if len(digits) != 20:
        raise ValidationError("Номер счёта состоит из 20 цифр.")


def validate_inn(value):
    """ИНН юридического лица: 10 цифр с контрольной."""
    digits = _digits_only(value)
    if len(digits) != 10:
        raise ValidationError("ИНН организации состоит из 10 цифр.")
    weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    control = sum(int(d) * w for d, w in zip(digits[:9], weights)) % 11 % 10
    if control != int(digits[9]):
        raise ValidationError("Контрольная цифра ИНН не сходится — проверьте номер.")


def validate_kpp(value):
    digits = _digits_only(value)
    if len(digits) != 9:
        raise ValidationError("КПП состоит из 9 цифр.")
