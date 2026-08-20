from files.models import File

class PolicyEngine:
    @staticmethod
    def can_read(user, file_obj) -> bool:
        if user.is_staff or user.is_superuser:
            return True
            
        if file_obj.owner == user:
            return True
            
        return file_obj.visibility in {
            File.Visibility.PUBLIC_VIEW,
            File.Visibility.PUBLIC_EDIT,
        }

    @staticmethod
    def can_write(user, file_obj) -> bool:
        if user.is_staff or user.is_superuser:
            return True
            
        if file_obj.owner == user:
            return True
            
        return file_obj.visibility == File.Visibility.PUBLIC_EDIT
