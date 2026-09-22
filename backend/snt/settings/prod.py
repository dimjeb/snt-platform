from .base import *  # noqa

DEBUG = False

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Caddy терминирует TLS и проксирует в Django по http, поэтому схему
# оригинального запроса Django узнаёт только из заголовка.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# ─── Cookie и сессии ──────────────────────────────────────────────────────────

# Django admin работает на сессиях, и именно там персональные данные видны
# целиком. Кука сессии по умолчанию уходит и по http, и доступна скриптам.
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# Восемь часов — рабочий день. Сессия, оставленная в админке на неделю,
# это открытый реестр на чужом экране.
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True

# HSTS уже отдаёт Caddy (max-age=31536000, includeSubDomains, preload),
# поэтому SECURE_HSTS_* здесь намеренно не задаются: два источника одного
# заголовка расходятся при первой же правке одного из них.
