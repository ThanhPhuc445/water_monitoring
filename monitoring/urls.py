from django.urls import path
from . import views
from .views import AdminOnlyAPIView, UserProfileAPIView, change_user_role, change_password, home_view, latest_reading, upload_reading, readings_table_view
from .views import (
    AdminOnlyAPIView, UserProfileAPIView, change_user_role, change_password, 
    latest_reading, upload_reading, readings_table_view
)
urlpatterns = [
    # Template URLs
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path('', home_view, name='home'),
    path("readings/", readings_table_view, name="readings_table"),
    path("admin-dashboard/", views.admin_dashboard_view, name="admin_dashboard"),
    path("password-reset-request/", views.password_reset_request, name="password_reset_request"),
    path("reset-password/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
    
    # API URLs
    path("api/admin/users/", AdminOnlyAPIView.as_view(), name="admin_users_api"),
    path("api/user/profile/", UserProfileAPIView.as_view(), name="user_profile_api"),
    path("api/user/<int:user_id>/change-role/", change_user_role, name="change_user_role"),
    path("api/user/change-password/", change_password, name="change_password_api"),
    path('api/latest-reading/', latest_reading, name='latest-reading'),
    path('api/upload-reading/', upload_reading, name='upload-reading'),

    path("reports/", views.report_list_view, name="report_list"),
    path("reports/<int:pk>/", views.report_detail_view, name="report_detail"),
    path("reports/create/", views.report_create_view, name="report_create"),
    path('<int:pk>/edit/', views.report_edit, name='report_edit'),
    path('<int:pk>/delete/', views.report_delete, name='report_delete'),
    

]