from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "get_full_name", "organization", "role", "is_active")
    list_filter = ("role", "organization", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("СНТ-Платформа", {"fields": ("organization", "role", "phone", "member")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("СНТ-Платформа", {"fields": ("organization", "role", "phone")}),
    )
