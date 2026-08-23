from django.db import models
from django.contrib.auth.models import User

class ServerNode(models.Model):
    hostname = models.CharField(max_length=255, unique=True)
    current_load = models.FloatField(default=0.0)
    active_connections = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='online')
    last_heartbeat = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.hostname} ({self.status})"

class File(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "PRIVATE", "Private"
        PUBLIC = "PUBLIC", "Public"

    original_name = models.CharField(max_length=255)
    stored_name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="files",
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    size = models.BigIntegerField()
    checksum = models.CharField(max_length=64, blank=True, null=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.original_name

class FileTransfer(models.Model):
    STATE_CHOICES = [
        ('PENDING', 'Pending'),
        ('TRANSFERRING', 'Transferring'),
        ('VERIFYING', 'Verifying'),
        ('COMPLETE', 'Complete'),
        ('DISCONNECTED', 'Disconnected'),
        ('FAILED', 'Failed')
    ]

    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='transfers')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transfers')
    node = models.ForeignKey(ServerNode, on_delete=models.SET_NULL, null=True, blank=True)
    state = models.CharField(max_length=50, choices=STATE_CHOICES, default='PENDING')
    bytes_transferred = models.BigIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.file.original_name} - {self.state} ({self.bytes_transferred})"
