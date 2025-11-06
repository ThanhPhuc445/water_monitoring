# accounts/signals.py
from django.contrib.auth.signals import user_logged_in, user_login_failed, user_logged_out
from django.dispatch import receiver
from .models import LoginHistory

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    LoginHistory.objects.create(
        user=user,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        status="SUCCESS"
    )

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    LoginHistory.objects.create(
        user=None,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        status="FAILED"
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    # bạn có thể ghi thêm nếu muốn log logout
    print(f"User {user} đã logout")
