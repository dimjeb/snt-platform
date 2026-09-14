from django import forms
from django.contrib import admin

from .models import ObligatoryPayment, PaymentProvider


class PaymentProviderForm(forms.ModelForm):
    """
    Форма провайдера с отдельным полем для секрета.

    Сохранённый ключ не показывается никогда — ни в открытом виде, ни
    шифротекстом. Пустое поле означает «оставить как было», поэтому
    провайдера можно переименовать или выключить, не вводя ключ заново.
    """

    secret_input = forms.CharField(
        label="Секретный ключ",
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="ЮKassa — секретный ключ, Т-Банк — пароль терминала, "
                  "Робокасса — Пароль №1. Пусто = не менять.",
    )
    secret2_input = forms.CharField(
        label="Дополнительный ключ",
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Робокасса — Пароль №2, CloudPayments — API secret. "
                  "Остальным не нужен. Пусто = не менять.",
    )

    class Meta:
        model = PaymentProvider
        exclude = ("secret_encrypted", "secret2_encrypted")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            for field, is_set in (
                ("secret_input", self.instance.secret_is_set),
                ("secret2_input", self.instance.secret2_is_set),
            ):
                self.fields[field].help_text = (
                    "Ключ сохранён и читается."
                    if is_set
                    else "Не задан или не читается текущим ключом шифрования."
                ) + " Оставьте пустым, чтобы не менять."

    def clean(self):
        cleaned = super().clean()
        # clean() модели проверяет наличие секрета, поэтому кладём введённое
        # значение в инстанс до валидации, иначеновый провайдер не сохранить.
        if cleaned.get("secret_input"):
            self.instance.secret = cleaned["secret_input"]
        if cleaned.get("secret2_input"):
            self.instance.secret2 = cleaned["secret2_input"]
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get("secret_input"):
            obj.secret = self.cleaned_data["secret_input"]
        if self.cleaned_data.get("secret2_input"):
            obj.secret2 = self.cleaned_data["secret2_input"]
        if commit:
            obj.save()
        return obj


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    form = PaymentProviderForm
    list_display = (
        "title", "organization", "kind", "direction",
        "test_mode", "is_active", "is_default", "configured",
    )
    list_filter = ("organization", "direction", "kind", "is_active", "test_mode")
    search_fields = ("title", "merchant_id", "organization__name")
    ordering = ("organization", "direction", "-is_default")

    fieldsets = (
        (None, {
            "fields": ("organization", "title", "kind", "direction"),
        }),
        ("Реквизиты", {
            "fields": ("merchant_id", "secret_input", "secret2_input", "test_mode"),
            "description": (
                "Ключи хранятся в базе в зашифрованном виде и после "
                "сохранения не отображаются. Идентификатор мерчанта: "
                "shopId у ЮKassa, TerminalKey у Т-Банка, логин магазина "
                "у Робокассы, public id у CloudPayments."
            ),
        }),
        ("Использование", {
            "fields": ("is_active", "is_default", "notes"),
        }),
    )

    @admin.display(description="Готов к работе", boolean=True)
    def configured(self, obj):
        return obj.is_configured


@admin.register(ObligatoryPayment)
class ObligatoryPaymentAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "kind", "amount",
                    "due_date", "status", "overdue")
    list_filter = ("organization", "status", "kind")
    search_fields = ("title", "recipient", "notes")
    date_hierarchy = "due_date"
    ordering = ("status", "due_date")

    @admin.display(description="Просрочен", boolean=True)
    def overdue(self, obj):
        return obj.is_overdue
