from django.utils.deprecation import MiddlewareMixin
from .models import ActivityLog

class ActivityLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/static/') or request.path.startswith('/media/') or request.path == '/favicon.ico':
            return None

        if request.user.is_authenticated:
            # Get IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')

            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                method=request.method,
                path=request.path,
                ip_address=ip,
                is_admin=request.user.is_superuser or request.user.is_staff
            )
        
        return None
