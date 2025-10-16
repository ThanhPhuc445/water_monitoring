from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .decorators import admin_required, user_required
from .mixins import RoleBasedPermission, IsAdminUser, IsUser
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Reading, Device, Alert
from .serializers import ReadingSerializer
from .services.ai_service import predict_water_quality, get_ai_status, predict_water_quality_strict_who
from .services.data_logger import get_logger

import json
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def home_view(request):
    """Trang chủ công khai, không yêu cầu đăng nhập"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, "monitoring/home.html")

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
        
        if len(password1) < 6:
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
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                role=role
            )
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
# Đăng nhập
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.POST.get('next', request.GET.get('next', 'dashboard'))
            messages.success(request, f"Đăng nhập thành công! Chào mừng {user.username}.")
            return redirect(next_url)
        else:
            messages.error(request, "Sai tài khoản hoặc mật khẩu")
    else:
        form = AuthenticationForm()
    return render(request, "registration/login.html", {"form": form})

# Đăng xuất
def logout_view(request):
    logout(request)
    messages.success(request, "Đã đăng xuất thành công.")
    return redirect("home")

# Dashboard với phân quyền
@login_required
@user_required
def dashboard_view(request):
    user_role = request.user.role
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

# Đặt lại mật khẩu
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

# API Views với phân quyền
class AdminOnlyAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        users = User.objects.all()
        data = [{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
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
            'role': user.role,
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

@login_required
@user_required
def readings_table_view(request):
    """View hiển thị bảng dữ liệu Reading"""
    readings = Reading.objects.order_by('-timestamp')
    context = {
        'readings': readings,
        'total_readings': readings.count()
    }
    return render(request, "monitoring/readings_table.html", context)

@login_required
def reading_detail_view(request, reading_id):
    """View hiển thị chi tiết một reading với đầy đủ thông tin AI"""
    reading = get_object_or_404(Reading, pk=reading_id)
    
    # Lấy các readings gần đây từ cùng thiết bị (nếu có)
    similar_readings = None
    if reading.device:
        similar_readings = Reading.objects.filter(
            device=reading.device
        ).order_by('-timestamp')[:10]
    
    context = {
        'reading': reading,
        'similar_readings': similar_readings
    }
    return render(request, "monitoring/reading_detail.html", context)

@api_view(['GET'])
@permission_classes([])  # Bỏ yêu cầu authentication
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
    """
    API endpoint để Arduino gửi dữ liệu sensor và nhận kết quả AI
    """
    try:
        # Lấy dữ liệu từ request
        ph = float(request.POST.get('ph', 0))
        ntu = float(request.POST.get('ntu', 0))  # turbidity
        tds = float(request.POST.get('tds', 0))
        battery = float(request.POST.get('battery', 0)) if request.POST.get('battery') else None
        signal = float(request.POST.get('signal', 0)) if request.POST.get('signal') else None
        device_id = request.POST.get('device_id')  # Optional device identifier
        
        # Validate input data
        if ph < 0 or ph > 14:
            return Response({'error': 'Invalid pH value (0-14)'}, status=400)
        if ntu < 0:
            return Response({'error': 'Invalid turbidity value (>= 0)'}, status=400)
        if tds < 0:
            return Response({'error': 'Invalid TDS value (>= 0)'}, status=400)
        
        # Tìm device nếu có
        device = None
        if device_id:
            try:
                device = Device.objects.get(id=device_id)
            except Device.DoesNotExist:
                logger.warning(f"Device with ID {device_id} not found")
        
        # Dự đoán chất lượng nước bằng AI
        logger.info(f"Processing sensor data: pH={ph}, NTU={ntu}, TDS={tds}")
        ai_result = predict_water_quality(ph, ntu, tds)
        
        # Tạo Reading với AI prediction
        reading = Reading.objects.create(
            ph=ph,
            ntu=ntu,
            tds=tds,
            battery=battery,
            signal=signal,
            device=device,
            # AI fields
            ai_prediction=ai_result['prediction'],
            ai_safe_probability=ai_result['safe_probability'],
            ai_quality_level=ai_result['quality_level'],
            ai_risk_level=ai_result['risk_level'],
            ai_recommendations=ai_result['recommendations'],
            ai_model_version=ai_result['model_version']
        )
        
        # Tạo Alert nếu AI phát hiện vấn đề
        if not ai_result['is_safe'] or ai_result['risk_level'] == 'HIGH':
            alert_message = f"Water quality alert: {ai_result['quality_level']} - "
            alert_message += f"Safety: {ai_result['safe_probability']:.1f}%"
            
            Alert.objects.create(
                message=alert_message,
                severity="HIGH" if ai_result['risk_level'] == 'HIGH' else "MEDIUM",
                type="AI",
                status="NEW",
                device=device
            )
            logger.warning(f"Created alert for unsafe water: {alert_message}")
        
        # Response cho Arduino
        response_data = {
            'status': 'success',
            'message': 'Data received and analyzed successfully',
            'reading_id': reading.pk,
            'ai_analysis': {
                'is_safe': ai_result['is_safe'],
                'quality_level': ai_result['quality_level'],
                'safe_probability': ai_result['safe_probability'],
                'risk_level': ai_result['risk_level'],
                'recommendations': ai_result['recommendations'][:3]  # Chỉ gửi 3 recommendations đầu
            },
            'sensor_data': {
                'ph': ph,
                'turbidity_ntu': ntu,
                'tds_ppm': tds,
                'ec_ms_cm': ai_result['input_data']['ec_ms_cm']
            },
            'timestamp': reading.timestamp.isoformat()
        }
        
        logger.info(f"Successfully processed reading {reading.pk} with AI analysis")
        return Response(response_data)
        
    except ValueError as e:
        error_msg = f"Invalid data format: {str(e)}"
        logger.error(error_msg)
        return Response({'error': error_msg}, status=400)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return Response({'error': error_msg}, status=500)

@api_view(['GET'])
@permission_classes([])
def ai_status(request):
    """
    API endpoint để kiểm tra trạng thái AI service
    """
    try:
        status_info = get_ai_status()
        return Response({
            'ai_service_status': 'online' if status_info['is_loaded'] else 'offline',
            'model_details': status_info,
            'last_check': timezone.now().isoformat()
        })
    except Exception as e:
        return Response({
            'ai_service_status': 'error',
            'error': str(e),
            'last_check': timezone.now().isoformat()
        }, status=500)

@api_view(['POST'])
@permission_classes([])
def analyze_water(request):
    """
    API endpoint để phân tích chất lượng nước mà không lưu vào database
    """
    try:
        ph = float(request.POST.get('ph', 0))
        ntu = float(request.POST.get('ntu', 0))
        tds = float(request.POST.get('tds', 0))
        
        # Validate
        if ph < 0 or ph > 14:
            return Response({'error': 'Invalid pH value (0-14)'}, status=400)
        
        # Phân tích bằng AI
        ai_result = predict_water_quality(ph, ntu, tds)
        
        return Response({
            'analysis_result': ai_result,
            'input_parameters': {
                'ph': ph,
                'turbidity_ntu': ntu,
                'tds_ppm': tds
            }
        })
        
    except ValueError as e:
        return Response({'error': f'Invalid data: {str(e)}'}, status=400)
    except Exception as e:
        return Response({'error': f'Analysis failed: {str(e)}'}, status=500)


@api_view(['POST'])
@permission_classes([])
def upload_reading_strict(request):
    """
    API endpoint cho ESP32 gửi dữ liệu và sử dụng STRICT WHO labeler thay vì ML AI.
    Tương thích 100% với upload_reading, chỉ khác thuật toán gắn nhãn.
    
    Usage từ ESP32:
        POST /api/upload_reading_strict/
        Content-Type: application/x-www-form-urlencoded
        Body: ph=7.2&tds=450&ntu=0.8&battery=85&signal=75&device_id=1
    """
    try:
        # Lấy dữ liệu từ request (hỗ trợ cả POST form và JSON)
        if request.content_type == 'application/json':
            data = request.data
        else:
            data = request.POST
        
        ph = float(data.get('ph', 0))
        ntu = float(data.get('ntu', 0))  # turbidity
        tds = float(data.get('tds', 0))
        battery = float(data.get('battery', 0)) if data.get('battery') else None
        signal = float(data.get('signal', 0)) if data.get('signal') else None
        device_id = data.get('device_id')  # Optional device identifier
        
        # Validate input data
        if ph < 0 or ph > 14:
            return Response({'error': 'Invalid pH value (0-14)'}, status=400)
        if ntu < 0:
            return Response({'error': 'Invalid turbidity value (>= 0)'}, status=400)
        if tds < 0:
            return Response({'error': 'Invalid TDS value (>= 0)'}, status=400)
        
        # Tìm device nếu có
        device = None
        if device_id:
            try:
                device = Device.objects.get(id=device_id)
            except Device.DoesNotExist:
                logger.warning(f"Device with ID {device_id} not found")
        
        # Gắn nhãn bằng STRICT WHO RULES
        logger.info(f"Processing sensor data with STRICT WHO: pH={ph}, NTU={ntu}, TDS={tds}")
        ai_result = predict_water_quality_strict_who(ph, ntu, tds)
        
        # Tạo Reading với strict labeling
        reading = Reading.objects.create(
            ph=ph,
            ntu=ntu,
            tds=tds,
            battery=battery,
            signal=signal,
            device=device,
            # AI fields (populated by strict labeler)
            ai_prediction=ai_result['prediction'],
            ai_safe_probability=ai_result['safe_probability'],
            ai_quality_level=ai_result['quality_level'],
            ai_risk_level=ai_result['risk_level'],
            ai_recommendations=ai_result['recommendations'],
            ai_model_version=ai_result['model_version']
        )
        
        # Log measurement to CSV for dataset collection
        csv_logger = get_logger()
        csv_logger.log_measurement(
            ph=ph,
            tds=tds,
            ntu=ntu,
            is_clean=ai_result['is_safe']
        )
        logger.info(f"Logged measurement to CSV: ph={ph}, tds={tds}, ntu={ntu}, label={'1' if ai_result['is_safe'] else '0'}")
        
        # Tạo Alert nếu strict labeler phát hiện vấn đề
        if not ai_result['is_safe'] or ai_result['risk_level'] == 'HIGH':
            alert_message = f"Water quality alert (WHO strict): {ai_result['quality_level']} - "
            alert_message += f"Safety: {ai_result['safe_probability']:.1f}%"
            
            Alert.objects.create(
                message=alert_message,
                severity="HIGH" if ai_result['risk_level'] == 'HIGH' else "MEDIUM",
                type="RULE",  # Đánh dấu là rule-based thay vì AI
                status="NEW",
                device=device
            )
            logger.warning(f"Created alert for unsafe water (strict WHO): {alert_message}")
        
        # Response cho ESP32
        response_data = {
            'status': 'success',
            'message': 'Data received and labeled using strict WHO rules',
            'reading_id': reading.pk,
            'analysis': {
                'method': 'STRICT_WHO_RULES',
                'is_safe': ai_result['is_safe'],
                'label': ai_result['strict_who_details']['label'],  # clean/dirty
                'quality_level': ai_result['quality_level'],
                'safe_probability': ai_result['safe_probability'],
                'risk_level': ai_result['risk_level'],
                'confidence': ai_result['strict_who_details']['confidence'],
                'recommendations': ai_result['recommendations'][:3]  # Top 3
            },
            'sensor_data': {
                'ph': ph,
                'turbidity_ntu': ntu,
                'tds_ppm': tds,
            },
            'timestamp': reading.timestamp.isoformat()
        }
        
        logger.info(f"Successfully processed reading {reading.pk} with strict WHO labeling")
        return Response(response_data)
        
    except ValueError as e:
        error_msg = f"Invalid data format: {str(e)}"
        logger.error(error_msg)
        return Response({'error': error_msg}, status=400)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return Response({'error': error_msg}, status=500)
