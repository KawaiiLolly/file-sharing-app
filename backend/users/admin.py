from django.contrib import admin
from .models import ActivityLog

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'method', 'path', 'ip_address', 'is_admin')
    list_filter = ('is_admin', 'method', 'timestamp')
    search_fields = ('user__username', 'path', 'ip_address')
    readonly_fields = ('user', 'method', 'path', 'ip_address', 'timestamp', 'is_admin')

    def has_add_permission(self, request):
        return False
