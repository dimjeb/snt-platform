"""
Шифрование реквизитов платёжных провайдеров.

Ключи мерчанта лежат в базе, поэтому хранятся зашифрованными: утёкший дамп
или украденная резервная копия не должны давать доступ к приёму денег.
От компрометации самого сервера это не спасает — ключ шифрования лежит
рядом, — но закрывает самый частый сценарий утечки.

Ключ берётся из настройки PAYMENTS_ENCRYPTION_KEY. Она отдельная, а не
общий SECRET_KEY, намеренно: ротация SECRET_KEY не должна превращать
реквизиты всех СНТ в нечитаемый мусор. Если настройка пуста, ключ
выводится из SECRET_KEY — это позволяет запуститься без дополнительной
конфигурации, но тогда смена SECRET_KEY потребует ввести реквизиты заново.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _build_key() -> bytes:
    """Ключ Fernet: либо готовый из настроек, либо выведенный из строки."""
    raw = (getattr(settings, "PAYMENTS_ENCRYPTION_KEY", "") or "").strip()
    source = raw or settings.SECRET_KEY

    if raw:
        # Настройку могли задать уже готовым ключом Fernet — тогда берём как есть.
        try:
            Fernet(raw.encode())
            return raw.encode()
        except (ValueError, TypeError):
            pass

    digest = hashlib.sha256(source.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(value: str) -> str:
    """Строку — в токен Fernet. Пустое значение остаётся пустым."""
    if not value:
        return ""
    return Fernet(_build_key()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """
    Токен — обратно в строку.

    Нечитаемый токен (сменился ключ, испорченная запись) не роняет страницу:
    возвращаем пустую строку, а вызывающий код трактует это как
    «реквизиты не заданы» и не пытается проводить платёж.
    """
    if not token:
        return ""
    try:
        return Fernet(_build_key()).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""
