from django.contrib import admin
from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "inn", "phone", "email", "is_active", "created_at")
    list_filter = ("is_active", "fee_period")
    search_fields = ("name", "inn")
