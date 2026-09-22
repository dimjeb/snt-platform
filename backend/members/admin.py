from django.contrib import admin
from .models import Member, Plot, PlotOwnership


class PlotOwnershipInline(admin.TabularInline):
    model = PlotOwnership
    extra = 0
    fields = ("member", "date_from", "date_to", "notes")


@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display = (
        "number", "organization", "area_sotok", "owners", "cadastral_number",
    )
    list_filter = ("organization",)
    search_fields = ("number", "cadastral_number")
    inlines = [PlotOwnershipInline]

    @admin.display(description="Собственники")
    def owners(self, obj):
        return obj.current_owners_display

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("ownerships__member")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "organization", "phone", "email", "status", "joined_at")
    list_filter = ("organization", "status")
    search_fields = ("last_name", "first_name", "patronymic", "phone", "email")
