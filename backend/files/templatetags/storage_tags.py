import os
import shutil
from django import template
from django.conf import settings
from files.models import File

register = template.Library()

@register.simple_tag
def get_storage_stats():
    # Calculate size from the database or the directory
    # For a file sharing platform, let's use the DB as the source of truth for user files
    total_db_bytes = sum(f.size for f in File.objects.all())
    
    # Get physical disk space info for the UPLOADS_DIR drive
    total, used, free = shutil.disk_usage(settings.UPLOADS_DIR)
    
    # Alternatively, we could set a quota. But disk space is a real metric.
    # We will return in GB/MB for display
    def format_bytes(b):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024:
                return f"{b:.2f} {unit}"
            b /= 1024
        return f"{b:.2f} PB"

    # We can display the percentage of disk used by our app versus system
    # App usage vs Total Disk
    app_percentage = (total_db_bytes / total) * 100 if total > 0 else 0
    total_used_percentage = (used / total) * 100 if total > 0 else 0
    
    return {
        'app_used_bytes': total_db_bytes,
        'app_used_str': format_bytes(total_db_bytes),
        'disk_total_bytes': total,
        'disk_total_str': format_bytes(total),
        'disk_used_str': format_bytes(used),
        'disk_free_str': format_bytes(free),
        'app_percentage': min(100, app_percentage),
        'total_used_percentage': min(100, total_used_percentage),
    }
