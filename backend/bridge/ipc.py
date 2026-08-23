import os
import django
from asgiref.sync import sync_to_async

# Configure Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "control_plane.settings")
django.setup()

from django.contrib.auth.models import User
from policies.engine import PolicyEngine
from files.models import FileTransfer, ServerNode, File

class DjangoBridge:
    @staticmethod
    @sync_to_async
    def initialize_upload(username: str, original_name: str, file_size: int, visibility: str) -> dict:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return {"error": "User not found"}
            
        # Check for incomplete transfer to resume
        transfers = FileTransfer.objects.filter(
            user=user, 
            file__original_name=original_name,
            file__size=file_size
        ).exclude(state__in=['COMPLETE', 'ERROR', 'FAILED', 'DISCONNECTED']).order_by('-updated_at')
        
        # If there is a DISCONNECTED or PENDING state, we can resume it
        resume_transfers = FileTransfer.objects.filter(
            user=user, 
            file__original_name=original_name,
            file__size=file_size,
            state__in=['PENDING', 'TRANSFERRING', 'DISCONNECTED']
        ).order_by('-updated_at')
        
        if resume_transfers.exists():
            transfer = resume_transfers.first()
            return {"stored_name": transfer.file.stored_name, "is_new": False, "file_id": transfer.file.id}

        # Generate unique stored name
        base_name, ext = os.path.splitext(original_name)
        stored_name = f"{base_name}_{user.username}{ext}"
        counter = 1
        while File.objects.filter(stored_name=stored_name).exists():
            stored_name = f"{base_name}_{user.username}_{counter}{ext}"
            counter += 1
            
        # Create new File
        file_obj = File.objects.create(
            original_name=original_name,
            stored_name=stored_name,
            owner=user,
            visibility=visibility or File.Visibility.PRIVATE,
            size=file_size,
        )
        return {"stored_name": file_obj.stored_name, "is_new": True, "file_id": file_obj.id}

    @staticmethod
    @sync_to_async
    def check_download_permission(username: str, original_name: str) -> dict:
        try:
            user = User.objects.get(username=username)
            # Find the most recent file with this name that the user can read
            files = File.objects.filter(original_name=original_name).order_by('-created_at')
            for f in files:
                if PolicyEngine.can_read(user, f):
                    return {
                        "allowed": True, 
                        "stored_name": f.stored_name, 
                        "file_size": f.size, 
                        "checksum": f.checksum,
                        "file_id": f.id
                    }
            return {"allowed": False, "error": "Permission denied or file not found"}
        except User.DoesNotExist:
            return {"allowed": False, "error": "User not found"}

    @staticmethod
    @sync_to_async
    def update_transfer_state(file_id: int, username: str, state: str, bytes_transferred: int, node_hostname: str = 'localhost'):
        try:
            user = User.objects.get(username=username)
            file_obj = File.objects.get(id=file_id)
            node, _ = ServerNode.objects.get_or_create(hostname=node_hostname)
            
            transfer, _ = FileTransfer.objects.get_or_create(
                file=file_obj,
                user=user,
                defaults={'node': node}
            )
            transfer.state = state
            transfer.bytes_transferred = bytes_transferred
            transfer.save()
            
            if state == 'COMPLETE':
                file_obj.checksum = file_obj.checksum # It's updated in connection.py then saved here? 
                # Wait, connection.py doesn't have sync db access. Let's let connection.py pass the checksum.
        except (User.DoesNotExist, File.DoesNotExist):
            pass

    @staticmethod
    @sync_to_async
    def finalize_upload(file_id: int, checksum: str):
        try:
            file_obj = File.objects.get(id=file_id)
            file_obj.checksum = checksum
            file_obj.save()
        except File.DoesNotExist:
            pass
