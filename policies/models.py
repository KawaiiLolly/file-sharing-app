from django.db import models
from django.contrib.auth.models import User

class FilePermission(models.Model):
    PERMISSION_CHOICES = [
        ('READ', 'Read'),
        ('WRITE', 'Write'),
        ('ADMIN', 'Admin')
    ]

    file_name = models.CharField(max_length=255, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissions')
    permission_level = models.CharField(max_length=10, choices=PERMISSION_CHOICES)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('file_name', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.file_name} ({self.permission_level})"
