from django.contrib import admin
from django.urls import path, include
from monitoring import views as monitoring_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Dòng này sẽ bao gồm TẤT CẢ các URL từ monitoring/urls.py của bạn
    # Hãy đảm bảo rằng không có sự trùng lặp nào với các path đã định nghĩa trước đó
    path('', include('monitoring.urls')),
    
    # Bạn có thể giữ lại dòng này nếu bạn muốn sử dụng các URL mặc định của Django cho việc quản lý mật khẩu
    # Nhưng nếu bạn đã tự định nghĩa password-reset-request/ và reset-password/<uidb64>/<token>/
    # thì có thể bạn không cần dòng này nữa, hoặc cần điều chỉnh để tránh trùng lặp.
    # Tuy nhiên, lỗi hiện tại không liên quan đến nó.
    # path("password-reset/", include("django.contrib.auth.urls")), 
]