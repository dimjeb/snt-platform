from django.contrib import admin

from .models import AccessLog


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    """
    Журнал только для чтения.

    Запись, которую можно отредактировать или удалить из интерфейса, —
    не доказательство. Чистка старых записей вынесена в отдельную
    команду purge_access_log, чтобы это было осознанным действием.
    """
    list_display = ("created_at", "username", "organization", "resource",
                    "action", "records", "ip")
    list_filter = ("resource", "action", "organization")
    search_fields = ("username", "ip", "path")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
