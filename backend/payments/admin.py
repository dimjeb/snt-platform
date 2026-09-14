from django import forms
from django.contrib import admin

from .models import PaymentProvider


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
        help_text="Оставьте пустым, чтобы не менять сохранённый ключ.",
    )

    class Meta:
        model = PaymentProvider
        exclude = ("secret_encrypted",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["secret_input"].help_text = (
                "Ключ сохранён и читается."
                if self.instance.secret_is_set
                else "Ключ не задан или не читается текущим ключом шифрования."
            ) + " Оставьте пустым, чтобы не менять."

    def clean(self):
        cleaned = super().clean()
        # clean() модели проверяет наличие секрета, поэтому кладём введённое
        # значение в инстанс до валидации, иначеновый провайдер не сохранить.
        secret = cleaned.get("secret_input")
        if secret:
            self.instance.secret = secret
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        secret = self.cleaned_data.get("secret_input")
        if secret:
            obj.secret = secret
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
            "fields": ("merchant_id", "secret_input", "test_mode"),
            "description": (
                "Секретный ключ хранится в базе в зашифрованном виде "
                "и нигде не отображается после сохранения."
            ),
        }),
        ("Использование", {
            "fields": ("is_active", "is_default", "notes"),
        }),
    )

    @admin.display(description="Готов к работе", boolean=True)
    def configured(self, obj):
        return obj.is_configured
