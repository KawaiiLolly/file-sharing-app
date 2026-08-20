from django.contrib import admin
from .models import ServerNode, FileTransfer, File

@admin.register(ServerNode)
class ServerNodeAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'status', 'current_load', 'active_connections', 'last_heartbeat')
    list_filter = ('status',)

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'stored_name', 'owner', 'visibility', 'size', 'created_at')
    list_filter = ('visibility',)
    search_fields = ('original_name', 'stored_name', 'owner__username')

@admin.register(FileTransfer)
class FileTransferAdmin(admin.ModelAdmin):
    list_display = ('file', 'user', 'node', 'state', 'bytes_transferred', 'updated_at')
    list_filter = ('state', 'node')
    search_fields = ('file__original_name', 'user__username')
