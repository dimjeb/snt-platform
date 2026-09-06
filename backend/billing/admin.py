from django.contrib import admin
from .models import ChargeType, BillingPeriod, Charge, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("date", "amount", "method", "is_cancelled", "recorded_by")
    readonly_fields = ("recorded_by",)


@admin.register(ChargeType)
class ChargeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "organization", "is_active")
    list_filter = ("organization", "category", "is_active")


@admin.register(BillingPeriod)
class BillingPeriodAdmin(admin.ModelAdmin):
    list_display = ("__str__", "organization", "status")
    list_filter = ("organization", "status", "year")


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ("plot", "charge_type", "period", "amount", "paid_amount", "debt")
    list_filter = ("organization", "period", "charge_type")
    search_fields = ("plot__number",)
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("charge", "date", "amount", "method", "is_cancelled")
    list_filter = ("organization", "method", "is_cancelled")
    readonly_fields = ("recorded_by",)
