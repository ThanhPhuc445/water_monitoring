from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from .models import LoginHistory
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .decorators import admin_required, user_required
from .mixins import RoleBasedPermission, IsAdminUser, IsUser
from .models import Reading, Report
from .serializers import ReadingSerializer
from monitoring.models import UserActionHistory, LoginHistory
from django.contrib.admin.views.decorators import staff_member_required
from .forms import ReportForm
import json

# 🔑 Dùng Custom User
User = get_user_model()


def home_view(request):
    """Trang chủ công khai, không yêu cầu đăng nhập"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, "monitoring/home.html")


# ---------------- ĐĂNG KÝ ----------------
def register_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        role = request.POST.get('role', 'user')

        errors = []

        if not username:
            errors.append("Tên đăng nhập là bắt buộc")
        if not email:
            errors.append("Email là bắt buộc")
        if not password1:
            errors.append("Mật khẩu là bắt buộc")
        if password1 != password2:
            errors.append("Mật khẩu xác nhận không khớp")
        if role not in ['admin', 'user']:
            errors.append("Vai trò không hợp lệ")

        if User.objects.filter(username=username).exists():
            errors.append("Tên đăng nhập đã tồn tại")

        if User.objects.filter(email=email).exists():
            errors.append("Email đã tồn tại")

        if password1 and len(password1) < 6:
            errors.append("Mật khẩu phải có ít nhất 6 ký tự")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "registration/register.html", {
                'username': username,
                'email': email,
                'role': role
            })

        try:
            # Tạo user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
            )

            # Gán quyền dựa trên role
            if role == "admin":
                user.is_staff = True
                user.is_superuser = True
            else:
                user.is_staff = False
                user.is_superuser = False

            user.role = role  # ⚡ nếu custom User có field role
            user.save()

            messages.success(request, "Đăng ký thành công! Hãy đăng nhập.")
            return redirect("login")
        except Exception as e:
            messages.error(request, f"Đăng ký thất bại: {str(e)}")
            return render(request, "registration/register.html", {
                'username': username,
                'email': email,
                'role': role
            })

    return render(request, "registration/register.html")


# ---------------- ĐĂNG NHẬP ----------------
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        username = request.POST.get('username')
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')

        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # ghi log thành công
            LoginHistory.objects.create(
                user=user,
                username=username,
                ip_address=ip,
                user_agent=ua,
                status="SUCCESS",
                timestamp=timezone.now()
            )

            return redirect("dashboard")
        else:
            # ghi log thất bại
            LoginHistory.objects.create(
                user=None,
                username=username,
                ip_address=ip,
                user_agent=ua,
                status="FAILED",
                timestamp=timezone.now()
            )
            messages.error(request, "Sai tài khoản hoặc mật khẩu")
    else:
        form = AuthenticationForm()
    return render(request, "registration/login.html", {"form": form})

def get_client_ip(request):
    """Lấy IP người dùng"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ---------------- ĐĂNG XUẤT ----------------
def logout_view(request):
    logout(request)
    messages.success(request, "Đã đăng xuất thành công.")
    return redirect("home")


# ---------------- DASHBOARD ----------------
@login_required
@user_required
def dashboard_view(request):
    user_role = getattr(request.user, "role", "user")
    latest_readings = Reading.objects.order_by('-timestamp')[:20]
    chart_data = []
    if latest_readings:
        for reading in latest_readings[:10]:
            chart_data.append({
                'timestamp': reading.timestamp.strftime('%H:%M:%S'),
                'ph': float(reading.ph),
                'tds': float(reading.tds),
                'ntu': float(reading.ntu)
            })
        chart_data.reverse()

    context = {
        'user_role': user_role,
        'is_admin': user_role == 'admin',
        'latest_readings': latest_readings,
        'chart_data': json.dumps(chart_data)
    }
    return render(request, "monitoring/dashboard.html", context)


@login_required
@admin_required
def admin_dashboard_view(request):
    users = User.objects.all()
    return render(request, "monitoring/admin_dashboard.html", {"users": users})


# ---------------- PASSWORD RESET ----------------
def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{request.scheme}://{request.get_host()}/reset-password/{uid}/{token}/"
            subject = 'Đặt lại mật khẩu - Water Monitor'
            message = f"""
            Xin chào {user.username},
            Bạn đã yêu cầu đặt lại mật khẩu cho tài khoản Water Monitor.
            Vui lòng click vào liên kết sau để đặt lại mật khẩu:
            {reset_url}
            Liên kết này sẽ hết hạn trong 24 giờ.
            Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.
            Trân trọng,
            Đội ngũ Water Monitor
            """

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            messages.success(request, "Email đặt lại mật khẩu đã được gửi! Vui lòng kiểm tra hộp thư của bạn.")
            return redirect('login')
        except User.DoesNotExist:
            messages.error(request, "Email không tồn tại trong hệ thống")

    return render(request, "registration/password_reset_request.html")


def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)

        if default_token_generator.check_token(user, token):
            if request.method == "POST":
                password = request.POST.get('password')
                password_confirm = request.POST.get('password_confirm')

                if password == password_confirm:
                    if len(password) < 6:
                        messages.error(request, "Mật khẩu phải có ít nhất 6 ký tự")
                        return render(request, "registration/password_reset_confirm.html")

                    user.set_password(password)
                    user.save()
                    messages.success(request, "Mật khẩu đã được đặt lại thành công! Vui lòng đăng nhập.")
                    return redirect('login')
                else:
                    messages.error(request, "Mật khẩu xác nhận không khớp")

            return render(request, "registration/password_reset_confirm.html", {'validlink': True})
        else:
            messages.error(request, "Liên kết không hợp lệ hoặc đã hết hạn")
            return redirect('login')
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        messages.error(request, "Liên kết không hợp lệ")
        return redirect('login')


# ---------------- API VIEWS ----------------
class AdminOnlyAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        users = User.objects.all()
        data = [{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': getattr(user, "role", "user"),
            'is_active': user.is_active
        } for user in users]
        return Response({'users': data})


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    allowed_roles = ['user', 'admin']

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': getattr(user, "role", "user"),
            'is_staff': user.is_staff
        })

    def put(self, request):
        user = request.user
        data = request.data
        if 'email' in data:
            user.email = data['email']

        user.save()
        return Response({'message': 'Cập nhật thông tin thành công'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def change_user_role(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        new_role = request.data.get('role')

        if new_role not in ['admin', 'user']:
            return Response({'error': 'Vai trò không hợp lệ'}, status=status.HTTP_400_BAD_REQUEST)

        user.role = new_role
        user.save()

        return Response({'message': f'Đã thay đổi vai trò của {user.username} thành {new_role}'})
    except User.DoesNotExist:
        return Response({'error': 'Người dùng không tồn tại'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not user.check_password(current_password):
        return Response({'error': 'Mật khẩu hiện tại không đúng'}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 6:
        return Response({'error': 'Mật khẩu mới phải có ít nhất 6 ký tự'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    return Response({'message': 'Mật khẩu đã được thay đổi thành công'})


# ---------------- BẢNG READING ----------------
@login_required
@user_required
def readings_table_view(request):
    readings = Reading.objects.order_by('-timestamp')
    context = {
        'readings': readings,
        'total_readings': readings.count()
    }
    return render(request, "monitoring/readings_table.html", context)


@api_view(['GET'])
@permission_classes([])
def latest_reading(request):
    reading = Reading.objects.order_by('-timestamp').first()
    if reading:
        data = {
            "ph": reading.ph,
            "ntu": reading.ntu,
            "tds": reading.tds,
            "timestamp": reading.timestamp,
        }
        return Response(data)
    return Response({"error": "No data"}, status=404)


@api_view(['POST'])
@permission_classes([])
def upload_reading(request):
    try:
        ph = float(request.POST.get('ph', 0))
        ntu = float(request.POST.get('ntu', 0))
        tds = float(request.POST.get('tds', 0))

        reading = Reading.objects.create(
            ph=ph,
            ntu=ntu,
            tds=tds
        )

        return Response({'message': 'Data received successfully', 'id': reading.pk})
    except Exception as e:
        return Response({'error': str(e)}, status=400)


# ---------------- REPORTS ----------------
def log_action(request, action, detail=""):
    ip = request.META.get('REMOTE_ADDR')
    UserActionHistory.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        detail=detail,
        ip_address=ip
    )


@staff_member_required
def access_report(request):
    login_logs = LoginHistory.objects.all().order_by('-timestamp')[:50]
    actions = UserActionHistory.objects.all().order_by('-timestamp')[:50]
    return render(request, 'monitoring/access_report.html', {
        'login_logs': login_logs,
        'actions': actions
    })


def is_admin(user):
    return user.is_superuser or user.is_staff


@login_required
def report_list_view(request):
    if request.user.is_staff:
        reports = Report.objects.all().order_by('-created_at')
    else:
        reports = Report.objects.filter(recipient=request.user).order_by('-created_at')
    return render(request, "monitoring/report_list.html", {"reports": reports})


@login_required
def report_detail_view(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if not request.user.is_staff and report.recipient != request.user:
        return redirect("report_list")
    return render(request, "monitoring/report_detail.html", {"report": report})


@login_required
@user_passes_test(is_admin)
def report_create_view(request):
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = request.user
            if report.status == "SENT":
                report.sent_at = timezone.now()
            report.save()
            form.save_m2m()
            log_action(request, "Tạo báo cáo", f"Report ID: {report.id}")
            return redirect("report_list")
    else:
        form = ReportForm()
    return render(request, "monitoring/report_form.html", {"form": form})

@login_required
@user_passes_test(is_admin)
def report_edit(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if request.method == "POST":
        form = ReportForm(request.POST, instance=report)
        if form.is_valid():
            form.save()
            messages.success(request, "Báo cáo đã được cập nhật.")
            return redirect("report_list")
    else:
        form = ReportForm(instance=report)
    return render(request, "reports/report_form.html", {"form": form})

@login_required
@user_passes_test(is_admin)
def report_delete(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if request.method == "POST":
        report.delete()
        messages.success(request, "Báo cáo đã được xóa.")
        return redirect("report_list")
    return render(request, "reports/report_confirm_delete.html", {"report": report})
