from django.contrib import admin
from .models import FilePermission

@admin.register(FilePermission)
class FilePermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'file_name', 'permission_level')
    search_fields = ('user__username', 'file_name')
    list_filter = ('permission_level',)
