from rest_framework import permissions

class RoleBasedPermission(permissions.BasePermission):
    """
    Permission class để kiểm tra vai trò người dùng trong API Views
    """
    def has_permission(self, request, view):
        # Lấy danh sách roles được phép từ view
        allowed_roles = getattr(view, 'allowed_roles', [])
        
        if not request.user.is_authenticated:
            return False
            
        if not allowed_roles:  # Nếu không định nghĩa roles, cho phép tất cả
            return True
            
        return request.user.role in allowed_roles

class IsAdminUser(permissions.BasePermission):
    """Chỉ cho phép admin truy cập"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsUser(permissions.BasePermission):
    """Chỉ cho phép user thông thường truy cập"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'user'