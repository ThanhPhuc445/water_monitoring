from django.contrib import admin
from .models import LoginHistory, UserActionHistory

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'username', 'status', 'timestamp', 'ip_address', 'user_agent')
    list_filter = ('status', 'timestamp')
    search_fields = ('username', 'user__username', 'ip_address')

@admin.register(UserActionHistory)
class UserActionHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    list_filter = ('timestamp', 'action')
    search_fields = ('user__username', 'action', 'detail')
