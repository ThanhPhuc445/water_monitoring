from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from functools import wraps
from django.shortcuts import redirect

def role_required(roles):
    """
    Decorator để kiểm tra vai trò người dùng
    roles: danh sách các vai trò được phép (ví dụ: ['admin', 'user'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if request.user.role not in roles:
                return JsonResponse({
                    'error': 'Permission denied', 
                    'message': 'Bạn không có quyền truy cập trang này'
                }, status=403)
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def admin_required(view_func):
    """Decorator chỉ cho phép admin truy cập"""
    return role_required(['admin'])(view_func)

def user_required(view_func):
    """Decorator chỉ cho phép user thông thường truy cập"""
    return role_required(['user', 'admin'])(view_func)