from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("report_type", "organization", "period", "generated_by", "sent_to", "created_at")
    list_filter = ("organization", "report_type")
    readonly_fields = ("generated_by", "created_at", "updated_at")
