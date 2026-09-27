from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
    verbose_name = "Платежи"

    def ready(self):
        # Импорт ради побочного эффекта: драйверы регистрируются
        # декоратором @register при импорте модуля.
        from . import (  # noqa: F401
            drivers_cloudpayments,
            drivers_robokassa,
            drivers_tbank,
            drivers_yookassa,
        )
