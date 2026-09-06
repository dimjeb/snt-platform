from django.contrib import admin
from .models import EnergyTariff, Meter, MeterReading


@admin.register(EnergyTariff)
class EnergyTariffAdmin(admin.ModelAdmin):
    list_display = ("organization", "valid_from", "price_per_kwh", "price_per_kwh_night")
    list_filter = ("organization",)
    ordering = ("-valid_from",)


class MeterReadingInline(admin.TabularInline):
    model = MeterReading
    extra = 0
    fields = ("date", "value", "value_night", "submitted_by", "notes")
    readonly_fields = ("submitted_by",)


@admin.register(Meter)
class MeterAdmin(admin.ModelAdmin):
    list_display = ("__str__", "organization", "is_main", "serial_number", "installed_at")
    list_filter = ("organization", "is_main")
    inlines = [MeterReadingInline]
