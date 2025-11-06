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
from datetime import datetime, timedelta
from django.db.models import Avg, Max, Min, Count
import json
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
from .services.data_logger import get_logger
from .services.ai_service import predict_water_quality, get_ai_status, predict_water_quality_simple
from .models import Reading
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
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
from datetime import datetime, timedelta
from django.db.models import Avg, Max, Min, Count
import json
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
from .services.data_logger import get_logger
from .services.ai_service import predict_water_quality, get_ai_status, predict_water_quality_simple
from .models import Reading
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

# THÊM DÒNG NÀY - import require_http_methods
from django.views.decorators.http import require_http_methods

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
    """View hiển thị bảng dữ liệu Reading với AI phân tích"""
    readings = Reading.objects.order_by('-timestamp')
    
    # XỬ LÝ AI PHÂN TÍCH CHO CÁC READING CHƯA ĐƯỢC PHÂN TÍCH
    for reading in readings:
        if (reading.ai_prediction is None and  
            reading.ph is not None and reading.tds is not None and reading.ntu is not None):
            
            try:
                # Gọi hàm AI phân tích
                ai_result = predict_water_quality(reading.ph, reading.tds, reading.ntu)
                
                # Cập nhật database với kết quả AI
                reading.ai_prediction = ai_result['prediction']  # 0 hoặc 1
                reading.ai_safe_probability = ai_result['safe_probability']
                reading.ai_quality_level = ai_result['quality_level']
                reading.ai_risk_level = ai_result['risk_level']
                reading.ai_recommendations = ai_result['recommendations']
                reading.ai_model_version = ai_result['model_version']
                reading.save()
                
                logger.info(f"✅ Đã phân tích reading {reading.id}: {ai_result['quality_level']} ({ai_result['safe_probability']}%)")
                
            except Exception as e:
                logger.error(f"❌ Lỗi phân tích reading {reading.id}: {str(e)}")
                # Không lưu nếu có lỗi, để trống cho lần sau phân tích lại
    
    context = {
        'readings': readings,
        'total_readings': readings.count(),
        'ai_status': get_ai_status()
    }
    return render(request, "monitoring/readings_table.html", context)
@login_required
def reading_detail_view(request, reading_id):
    """View hiển thị chi tiết một reading"""
    reading = get_object_or_404(Reading, pk=reading_id)
    
    context = {
        'reading': reading
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
        ntu = float(request.POST.get('ntu', 0))
        tds = float(request.POST.get('tds', 0))
        battery = float(request.POST.get('battery', 0)) if request.POST.get('battery') else None
        signal = float(request.POST.get('signal', 0)) if request.POST.get('signal') else None
        device_id = request.POST.get('device_id')
        
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
        
        # SỬA PHẦN NÀY: Dùng hàm đơn giản
        logger.info(f"Processing sensor data: pH={ph}, NTU={ntu}, TDS={tds}")
        ai_result = predict_water_quality_simple(ph, tds, ntu)
        
        # Tạo Reading với AI prediction
        reading = Reading.objects.create(
            ph=ph,
            ntu=ntu,
            tds=tds,
            battery=battery,
            signal=signal,
            device=device,
            # AI fields - SỬA THEO FORMAT MỚI
            ai_prediction=ai_result['prediction'],
            ai_confidence=ai_result['confidence'],
            ai_quality_level=ai_result['quality_level']
        )
        
        # Tạo Alert nếu cần
        if ai_result['prediction'] == 'BAN' or ai_result['confidence'] < 50:
            alert_message = f"Chất lượng nước kém: {ai_result['quality_level']} - Độ tin cậy: {ai_result['confidence']}%"
            
            Alert.objects.create(
                message=alert_message,
                severity="HIGH" if ai_result['confidence'] < 30 else "MEDIUM",
                type="AI",
                status="NEW",
                device=device
            )
            logger.warning(f"Created alert: {alert_message}")
        
        # Response cho Arduino - SỬA THEO FORMAT MỚI
        response_data = {
            'status': 'success',
            'message': 'Data received and analyzed successfully',
            'reading_id': reading.pk,
            'ai_analysis': {
                'prediction': ai_result['prediction'],  # SACH/BAN
                'quality_level': ai_result['quality_level'],
                'confidence': ai_result['confidence'],
            },
            'sensor_data': {
                'ph': ph,
                'turbidity_ntu': ntu,
                'tds_ppm': tds,
            },
            'timestamp': reading.timestamp.isoformat()
        }
        
        logger.info(f"Successfully processed reading {reading.pk}")
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
        
        # SỬA: Dùng hàm predict_water_quality
        ai_result = predict_water_quality(ph, tds, ntu)
        
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
        ai_result =  predict_water_quality_simple(ph, ntu, tds)
        
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
def historical_analysis_view(request):
    # --- 1️⃣ Lấy tham số thời gian ---
    period = request.GET.get('period', '7d')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    now = timezone.now()

    # Xử lý khoảng thời gian
    if period == '7d':
        start_date = now - timedelta(days=7)
        end_date = now
    elif period == '30d':
        start_date = now - timedelta(days=30)
        end_date = now
    elif period == '90d':
        start_date = now - timedelta(days=90)
        end_date = now
    elif period == 'custom' and date_from and date_to:
        try:
            # Chuyển đổi date string thành datetime với timezone
            start_date = timezone.make_aware(datetime.strptime(date_from, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(date_to, '%Y-%m-%d'))
            # Thêm 1 ngày để bao gồm cả ngày kết thúc
            end_date = end_date + timedelta(days=1)
        except ValueError as e:
            start_date = now - timedelta(days=7)
            end_date = now
    else:
        start_date = now - timedelta(days=7)
        end_date = now

# --- 2️⃣ Lọc dữ liệu từ database ---
    try:
        readings = Reading.objects.filter(
            timestamp__range=[start_date, end_date]
        ).order_by('timestamp')
        total_readings = readings.count()
    except Exception as e:
        readings = Reading.objects.none()
        total_readings = 0

    # --- 3️⃣ PHÂN TÍCH AI REAL-TIME (KHÔNG LƯU DATABASE) ---
    ai_results = []
    safe_count = 0
    unsafe_count = 0
    
    for reading in readings:
        if reading.ph is not None and reading.tds is not None and reading.ntu is not None:
            try:
                # Gọi AI để phân tích real-time
                ai_result = predict_water_quality_simple(reading.ph, reading.tds, reading.ntu)
                
                # Đếm kết quả
                if ai_result['prediction'] == 1:
                    safe_count += 1
                elif ai_result['prediction'] == 0:
                    unsafe_count += 1
                
                # Lưu kết quả để hiển thị
                ai_results.append({
                    'reading': reading,
                    'ai_result': ai_result
                })
                
            except Exception as e:
                print(f"❌ Lỗi AI phân tích reading {reading.id}: {str(e)}")
                unsafe_count += 1  # Mặc định là unsafe nếu lỗi

    # --- 4️⃣ Tính toán thống kê từ AI real-time ---
    if total_readings > 0:
        stats = readings.aggregate(
            avg_ph=Avg('ph'),
            min_ph=Min('ph'),
            max_ph=Max('ph'),
            avg_tds=Avg('tds'),
            avg_ntu=Avg('ntu'),
        )
        
        # Sử dụng kết quả AI real-time thay vì database
        stats['safe_count'] = safe_count
        stats['unsafe_count'] = unsafe_count
        stats['unknown_count'] = total_readings - (safe_count + unsafe_count)
        
        # Xử lý giá trị None
        stats['avg_ph'] = stats['avg_ph'] or 0
        stats['min_ph'] = stats['min_ph'] or 0
        stats['max_ph'] = stats['max_ph'] or 0
        stats['avg_tds'] = stats['avg_tds'] or 0
        stats['avg_ntu'] = stats['avg_ntu'] or 0
    else:
        stats = {
            'avg_ph': 0, 'min_ph': 0, 'max_ph': 0,
            'avg_tds': 0, 'avg_ntu': 0,
            'safe_count': 0, 'unsafe_count': 0, 'unknown_count': 0
        }

    stats['total_readings'] = total_readings

    # --- 5️⃣ Phân tích xu hướng ---
    def calc_trend(field):
        if total_readings < 2:
            return {"trend": "KHÔNG ĐỦ DỮ LIỆU", "change": 0}
        
        try:
            # Lấy 25% đầu và 25% cuối để tính xu hướng ổn định hơn
            sample_size = min(max(1, total_readings // 4), total_readings)
            readings_list = list(readings)
            first_readings = readings_list[:sample_size]
            last_readings = readings_list[-sample_size:]

            # Tính trung bình của nhóm đầu và cuối
            first_values = [getattr(r, field) or 0 for r in first_readings if getattr(r, field) is not None]
            last_values = [getattr(r, field) or 0 for r in last_readings if getattr(r, field) is not None]
            
            if not first_values or not last_values:
                return {"trend": "KHÔNG CÓ DỮ LIỆU", "change": 0}
                
            first_avg = sum(first_values) / len(first_values)
            last_avg = sum(last_values) / len(last_values)
            
            change = last_avg - first_avg
            
            # Xác định xu hướng với ngưỡng hợp lý
            if field == 'ph':
                if abs(change) > 1.0:
                    trend = "TĂNG MẠNH" if change > 0 else "GIẢM MẠNH"
                elif abs(change) > 0.3:
                    trend = "TĂNG NHẸ" if change > 0 else "GIẢM NHẸ"
                else:
                    trend = "ỔN ĐỊNH"
            elif field == 'tds':
                if abs(change) > 200:
                    trend = "TĂNG MẠNH" if change > 0 else "GIẢM MẠNH"
                elif abs(change) > 50:
                    trend = "TĂNG NHẸ" if change > 0 else "GIẢM NHẸ"
                else:
                    trend = "ỔN ĐỊNH"
            elif field == 'ntu':
                if abs(change) > 2.0:
                    trend = "TĂNG MẠNH" if change > 0 else "GIẢM MẠNH"
                elif abs(change) > 0.5:
                    trend = "TĂNG NHẸ" if change > 0 else "GIẢM NHẸ"
                else:
                    trend = "ỔN ĐỊNH"
                    
            return {"trend": trend, "change": round(change, 2)}
        except Exception as e:
            print(f"❌ Error calculating trend for {field}: {str(e)}")
            return {"trend": "LỖI", "change": 0}

    trends = {
        'ph_trend': calc_trend('ph')["trend"],
        'tds_trend': calc_trend('tds')["trend"],
        'ntu_trend': calc_trend('ntu')["trend"],
        'ph_change': calc_trend('ph')["change"],
        'tds_change': calc_trend('tds')["change"],
        'ntu_change': calc_trend('ntu')["change"],
    }

    # --- 6️⃣ Cảnh báo & đề xuất ---
    anomalies = []
    if total_readings > 0:
        for r in readings:
            if r.ph is not None and (r.ph < 6.5 or r.ph > 8.5):
                anomalies.append({
                    "type": "pH bất thường",
                    "message": f"pH = {r.ph:.2f} ngoài khoảng an toàn (6.5–8.5)",
                    "value": f"{r.ph:.2f}",
                    "timestamp": r.timestamp,
                    "severity": "CAO" if r.ph < 6 or r.ph > 9 else "TRUNG BÌNH"
                })
            elif r.ntu is not None and r.ntu > 5:
                anomalies.append({
                    "type": "NTU cao",
                    "message": f"Độ đục {r.ntu:.2f} vượt mức khuyến cáo (<5)",
                    "value": f"{r.ntu:.2f} NTU",
                    "timestamp": r.timestamp,
                    "severity": "TRUNG BÌNH"
                })
            elif r.tds is not None and r.tds > 1000:
                anomalies.append({
                    "type": "TDS cao",
                    "message": f"TDS {r.tds:.0f} ppm vượt mức khuyến cáo (<1000)",
                    "value": f"{r.tds:.0f} ppm",
                    "timestamp": r.timestamp,
                    "severity": "TRUNG BÌNH"
                })

    recommendations = []
    if total_readings == 0:
        recommendations.append({
            "type": "Không có dữ liệu",
            "priority": "CAO",
            "message": "Không tìm thấy bản ghi nào trong khoảng thời gian đã chọn.",
            "action": "Kiểm tra kết nối cảm biến hoặc mở rộng khoảng thời gian."
        })
    elif unsafe_count > safe_count:
        recommendations.append({
            "type": "Chất lượng nước kém",
            "priority": "CAO",
            "message": f"Nhiều mẫu nước không đạt ({unsafe_count}/{total_readings}).",
            "action": "Kiểm tra hệ thống lọc và nguồn nước ngay."
        })
    elif stats['avg_tds'] and stats['avg_tds'] > 500:
        recommendations.append({
            "type": "TDS cao",
            "priority": "TRUNG BÌNH",
            "message": f"TDS trung bình {stats['avg_tds']:.0f} ppm cao hơn mức khuyến nghị.",
            "action": "Cần kiểm tra nguồn nước hoặc thay lõi lọc."
        })
    elif stats['avg_ph'] and (stats['avg_ph'] < 6.5 or stats['avg_ph'] > 8.5):
        recommendations.append({
            "type": "pH không ổn định",
            "priority": "TRUNG BÌNH",
            "message": f"pH trung bình {stats['avg_ph']:.2f} ngoài khoảng tối ưu.",
            "action": "Điều chỉnh hệ thống cân bằng pH."
        })
    else:
        recommendations.append({
            "type": "Ổn định",
            "priority": "THẤP",
            "message": "Chất lượng nước trong giới hạn cho phép.",
            "action": "Tiếp tục theo dõi định kỳ."
        })

    # --- 7️⃣ Dữ liệu biểu đồ ---
    chart_data = {
        'timestamps': [r.timestamp.strftime("%Y-%m-%d %H:%M:%S") for r in readings],
        'ph': [float(r.ph) if r.ph is not None else 0 for r in readings],
        'tds': [float(r.tds) if r.tds is not None else 0 for r in readings],
        'ntu': [float(r.ntu) if r.ntu is not None else 0 for r in readings],
    }

    # --- 8️⃣ Trả dữ liệu cho template ---
    context = {
        'period': period,
        'date_from': start_date.date(),
        'date_to': (end_date - timedelta(days=1)).date(),
        'total_readings': total_readings,
        'chart_data': chart_data,
        'ai_analysis': {
            'stats': stats,
            'trends': trends,
            'anomalies': anomalies[:10],
            'recommendations': recommendations,
            'ai_results': ai_results[:10]  # Hiển thị 10 kết quả AI đầu tiên
        }
    }
    
    print(f"🤖 AI Real-time Analysis: Safe: {safe_count}, Unsafe: {unsafe_count}, Total: {total_readings}")
    return render(request, "monitoring/historical_analysis.html", context)
def prepare_chart_data(readings):
    """Chuẩn bị dữ liệu cho biểu đồ"""
    timestamps = []
    ph_data = []
    tds_data = []
    ntu_data = []
    ai_predictions = []
    
    for reading in readings:
        timestamps.append(reading.timestamp.strftime('%m/%d %H:%M'))
        ph_data.append(float(reading.ph))
        tds_data.append(float(reading.tds))
        ntu_data.append(float(reading.ntu))
        ai_predictions.append(reading.ai_prediction or 0)
    
    return {
        'timestamps': timestamps,
        'ph': ph_data,
        'tds': tds_data,
        'ntu': ntu_data,
        'ai_predictions': ai_predictions
    }

def perform_ai_analysis(readings):
    """Phân tích dữ liệu bằng AI và rule-based"""
    if not readings:
        return {}
    
    # Thống kê cơ bản
    stats = {
        'total_readings': readings.count(),
        'safe_count': readings.filter(ai_prediction=1).count(),
        'unsafe_count': readings.filter(ai_prediction=0).count(),
        'avg_ph': readings.aggregate(Avg('ph'))['ph__avg'],
        'avg_tds': readings.aggregate(Avg('tds'))['tds__avg'],
        'avg_ntu': readings.aggregate(Avg('ntu'))['ntu__avg'],
        'max_ph': readings.aggregate(Max('ph'))['ph__max'],
        'min_ph': readings.aggregate(Min('ph'))['ph__min'],
    }
    
    # Phân tích xu hướng
    trends = analyze_trends(readings)
    
    # Phát hiện bất thường
    anomalies = detect_anomalies(readings)
    
    # Đề xuất
    recommendations = generate_recommendations(stats, trends, anomalies)
    
    return {
        'stats': stats,
        'trends': trends,
        'anomalies': anomalies,
        'recommendations': recommendations
    }

def analyze_trends(readings):
    """Phân tích xu hướng dữ liệu"""
    if len(readings) < 2:
        return {}
    
    # Phân chia thành các khoảng thời gian
    readings_list = list(readings)
    first_half = readings_list[:len(readings_list)//2]
    second_half = readings_list[len(readings_list)//2:]
    
    # Tính trung bình từng nửa
    first_avg_ph = sum(r.ph for r in first_half) / len(first_half)
    second_avg_ph = sum(r.ph for r in second_half) / len(second_half)
    first_avg_tds = sum(r.tds for r in first_half) / len(first_half)
    second_avg_tds = sum(r.tds for r in second_half) / len(second_half)
    first_avg_ntu = sum(r.ntu for r in first_half) / len(first_half)
    second_avg_ntu = sum(r.ntu for r in second_half) / len(second_half)
    
    trends = {
        'ph_trend': 'ỔN ĐỊNH',
        'tds_trend': 'ỔN ĐỊNH', 
        'ntu_trend': 'ỔN ĐỊNH',
        'ph_change': round(second_avg_ph - first_avg_ph, 2),
        'tds_change': round(second_avg_tds - first_avg_tds, 0),
        'ntu_change': round(second_avg_ntu - first_avg_ntu, 2),
    }
    
    # Xác định xu hướng pH
    if abs(trends['ph_change']) > 0.5:
        trends['ph_trend'] = 'TĂNG MẠNH' if trends['ph_change'] > 0 else 'GIẢM MẠNH'
    elif abs(trends['ph_change']) > 0.2:
        trends['ph_trend'] = 'TĂNG NHẸ' if trends['ph_change'] > 0 else 'GIẢM NHẸ'
    
    # Xác định xu hướng TDS
    if abs(trends['tds_change']) > 100:
        trends['tds_trend'] = 'TĂNG MẠNH' if trends['tds_change'] > 0 else 'GIẢM MẠNH'
    elif abs(trends['tds_change']) > 50:
        trends['tds_trend'] = 'TĂNG NHẸ' if trends['tds_change'] > 0 else 'GIẢM NHẸ'
    
    # Xác định xu hướng NTU
    if abs(trends['ntu_change']) > 1.0:
        trends['ntu_trend'] = 'TĂNG MẠNH' if trends['ntu_change'] > 0 else 'GIẢM MẠNH'
    elif abs(trends['ntu_change']) > 0.3:
        trends['ntu_trend'] = 'TĂNG NHẸ' if trends['ntu_change'] > 0 else 'GIẢM NHẸ'
    
    return trends

def detect_anomalies(readings):
    """Phát hiện các giá trị bất thường"""
    anomalies = []
    
    for reading in readings:
        # Phát hiện pH bất thường
        if reading.ph < 5.0 or reading.ph > 9.0:
            anomalies.append({
                'timestamp': reading.timestamp,
                'type': 'pH NGUY HIỂM',
                'value': reading.ph,
                'severity': 'CAO',
                'message': f'pH đạt {reading.ph} - vượt ngưỡng an toàn'
            })
        elif reading.ph < 6.0 or reading.ph > 8.5:
            anomalies.append({
                'timestamp': reading.timestamp,
                'type': 'pH CẢNH BÁO', 
                'value': reading.ph,
                'severity': 'TRUNG BÌNH',
                'message': f'pH {reading.ph} - gần ngưỡng giới hạn'
            })
        
        # Phát hiện TDS bất thường
        if reading.tds > 1500:
            anomalies.append({
                'timestamp': reading.timestamp,
                'type': 'TDS QUÁ CAO',
                'value': reading.tds,
                'severity': 'CAO',
                'message': f'TDS {reading.tds}ppm - vượt ngưỡng cho phép'
            })
        
        # Phát hiện NTU bất thường
        if reading.ntu > 5.0:
            anomalies.append({
                'timestamp': reading.timestamp,
                'type': 'ĐỘ ĐỤC CAO',
                'value': reading.ntu,
                'severity': 'TRUNG BÌNH',
                'message': f'Độ đục {reading.ntu}NTU - cần xử lý'
            })
    
    return anomalies[:10]  # Giới hạn 10 bất thường

def generate_recommendations(stats, trends, anomalies):
    """Tạo đề xuất dựa trên phân tích"""
    recommendations = []
    
    # Đề xuất dựa trên chất lượng trung bình
    if stats['avg_ph'] < 6.5:
        recommendations.append({
            'type': 'CẢI THIỆN CHẤT LƯỢNG',
            'priority': 'CAO',
            'message': 'pH trung bình thấp - cần tăng pH',
            'action': 'Kiểm tra nguồn nước, sử dụng vật liệu nâng pH'
        })
    elif stats['avg_ph'] > 8.5:
        recommendations.append({
            'type': 'CẢI THIỆN CHẤT LƯỢNG',
            'priority': 'CAO', 
            'message': 'pH trung bình cao - cần giảm pH',
            'action': 'Sử dụng acid an toàn để điều chỉnh pH'
        })
    
    if stats['avg_tds'] > 1000:
        recommendations.append({
            'type': 'XỬ LÝ NƯỚC',
            'priority': 'TRUNG BÌNH',
            'message': 'TDS trung bình cao - nhiều khoáng chất',
            'action': 'Xem xét sử dụng hệ thống lọc RO'
        })
    
    if stats['avg_ntu'] > 1.0:
        recommendations.append({
            'type': 'XỬ LÝ NƯỚC',
            'priority': 'TRUNG BÌNH',
            'message': 'Độ đục trung bình cao',
            'action': 'Cần cải thiện hệ thống lọc cặn'
        })
    
    # Đề xuất dựa trên xu hướng
    if trends.get('ph_trend') in ['TĂNG MẠNH', 'GIẢM MẠNH']:
        recommendations.append({
            'type': 'THEO DÕI XU HƯỚNG',
            'priority': 'TRUNG BÌNH',
            'message': f'pH đang {trends["ph_trend"].lower()}',
            'action': 'Tăng tần suất giám sát pH'
        })
    
    # Đề xuất dựa trên số lượng bất thường
    if len(anomalies) > 5:
        recommendations.append({
            'type': 'BẢO TRÌ HỆ THỐNG',
            'priority': 'CAO',
            'message': f'Phát hiện {len(anomalies)} giá trị bất thường',
            'action': 'Kiểm tra toàn bộ hệ thống cảm biến và xử lý nước'
        })
    
    # Đề xuất tổng quát
    safe_percentage = (stats['safe_count'] / stats['total_readings'] * 100) if stats['total_readings'] > 0 else 0
    if safe_percentage >= 80:
        recommendations.append({
            'type': 'ĐÁNH GIÁ TỔNG QUÁT',
            'priority': 'THẤP',
            'message': 'Chất lượng nước tốt',
            'action': 'Duy trì hiện trạng'
        })
    elif safe_percentage >= 60:
        recommendations.append({
            'type': 'ĐÁNH GIÁ TỔNG QUÁT',
            'priority': 'TRUNG BÌNH',
            'message': 'Chất lượng nước khá',
            'action': 'Cải thiện các chỉ số chưa đạt'
        })
    else:
        recommendations.append({
            'type': 'ĐÁNH GIÁ TỔNG QUÁT', 
            'priority': 'CAO',
            'message': 'Chất lượng nước cần cải thiện',
            'action': 'Ưu tiên xử lý các vấn đề nghiêm trọng'
        })
    
    return recommendations
@login_required
@user_required
def readings_table_view(request):
    """View hiển thị bảng dữ liệu Reading với AI phân tích"""
    readings = Reading.objects.order_by('-timestamp')
    
    # XỬ LÝ AI PHÂN TÍCH CHO CÁC READING CHƯA ĐƯỢC PHÂN TÍCH
    for reading in readings:
        if (reading.ai_prediction is None and  
            reading.ph is not None and reading.tds is not None and reading.ntu is not None):
            
            try:
                # Gọi hàm AI phân tích
                ai_result = predict_water_quality(reading.ph, reading.tds, reading.ntu)
                
                # Cập nhật database với kết quả AI
                reading.ai_prediction = ai_result['prediction']  # 0 hoặc 1
                reading.ai_safe_probability = ai_result['safe_probability']
                reading.ai_quality_level = ai_result['quality_level']
                reading.ai_risk_level = ai_result['risk_level']
                reading.ai_recommendations = ai_result['recommendations']
                reading.ai_model_version = ai_result['model_version']
                reading.save()
                
                logger.info(f"✅ Đã phân tích reading {reading.id}: {ai_result['quality_level']} ({ai_result['safe_probability']}%)")
                
            except Exception as e:
                logger.error(f"❌ Lỗi phân tích reading {reading.id}: {str(e)}")
                # Không lưu nếu có lỗi, để trống cho lần sau phân tích lại
    
    context = {
        'readings': readings,
        'total_readings': readings.count(),
        'ai_status': get_ai_status()
    }
    return render(request, "monitoring/readings_table.html", context)
@require_GET
@csrf_exempt
def reading_ai_analysis(request, reading_id):
    """
    API endpoint để lấy phân tích AI chi tiết cho một reading cụ thể
    """
    try:
        reading = get_object_or_404(Reading, pk=reading_id)
        
        # Phân tích real-time bằng AI
        if reading.ph is not None and reading.tds is not None and reading.ntu is not None:
            ai_result = predict_water_quality(reading.ph, reading.tds, reading.ntu)
            
            # Cập nhật database với kết quả AI real-time
            reading.ai_prediction = ai_result['prediction']
            reading.ai_safe_probability = ai_result['safe_probability']
            reading.ai_quality_level = ai_result['quality_level']
            reading.ai_risk_level = ai_result['risk_level']
            reading.ai_recommendations = ai_result['recommendations']
            reading.ai_model_version = ai_result['model_version']
            reading.save()
        else:
            ai_result = {
                'prediction': -1,
                'is_safe': False,
                'safe_probability': 0.0,
                'quality_level': 'KHÔNG XÁC ĐỊNH',
                'risk_level': 'CAO',
                'recommendations': ['Thiếu dữ liệu cảm biến để phân tích'],
                'model_version': 'ERROR',
                'timestamp': timezone.now()
            }
        
        # Format response
        response_data = {
            'reading': {
                'id': reading.id,
                'timestamp': reading.timestamp.strftime('%d/%m/%Y %H:%M:%S'),
                'ph': reading.ph,
                'tds': reading.tds,
                'ntu': reading.ntu,
                'battery': reading.battery,
                'signal': reading.signal,
                'device': reading.device.name if reading.device else 'Không xác định'
            },
            'ai_analysis': ai_result,
            'status': 'success'
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in reading AI analysis: {str(e)}")
        return JsonResponse({
            'error': 'Lỗi khi phân tích dữ liệu',
            'details': str(e),
            'status': 'error'
        }, status=500)
@csrf_exempt
@require_http_methods(["GET"])
def get_unanalyzed_readings(request):
    """
    API endpoint để lấy danh sách các bản ghi chưa được phân tích AI
    """
    try:
        # Lọc các bản ghi chưa có phân tích AI (ai_prediction là None)
        unanalyzed_readings = Reading.objects.filter(
            ai_prediction__isnull=True
        ).order_by('-timestamp')[:50]  # Giới hạn 50 bản ghi để tránh quá tải
        
        readings_data = [
            {
                'id': reading.id,
                'timestamp': reading.timestamp.strftime('%d/%m/%Y %H:%M:%S'),
                'ph': float(reading.ph) if reading.ph else 0,
                'tds': float(reading.tds) if reading.tds else 0,
                'ntu': float(reading.ntu) if reading.ntu else 0,
            }
            for reading in unanalyzed_readings
        ]
        
        return JsonResponse({
            'status': 'success',
            'count': len(readings_data),
            'readings': readings_data
        })
        
    except Exception as e:
        logger.error(f"Error getting unanalyzed readings: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"]) 
def analyze_multiple_readings(request):
    """
    API endpoint để phân tích hàng loạt nhiều bản ghi
    """
    try:
        data = json.loads(request.body)
        reading_ids = data.get('reading_ids', [])
        
        if not reading_ids:
            return JsonResponse({
                'status': 'error',
                'error': 'No reading IDs provided'
            }, status=400)
        
        results = {
            'success_count': 0,
            'error_count': 0,
            'details': []
        }
        
        for reading_id in reading_ids:
            try:
                reading = Reading.objects.get(id=reading_id)
                
                # Phân tích bằng AI
                if reading.ph is not None and reading.tds is not None and reading.ntu is not None:
                    ai_result = predict_water_quality(reading.ph, reading.tds, reading.ntu)
                    
                    # Cập nhật database
                    reading.ai_prediction = ai_result['prediction']
                    reading.ai_safe_probability = ai_result['safe_probability']
                    reading.ai_quality_level = ai_result['quality_level']
                    reading.ai_risk_level = ai_result['risk_level']
                    reading.ai_recommendations = ai_result['recommendations']
                    reading.ai_model_version = ai_result['model_version']
                    reading.save()
                    
                    results['success_count'] += 1
                    results['details'].append({
                        'reading_id': reading_id,
                        'status': 'success',
                        'quality_level': ai_result['quality_level']
                    })
                else:
                    results['error_count'] += 1
                    results['details'].append({
                        'reading_id': reading_id,
                        'status': 'error',
                        'error': 'Missing sensor data'
                    })
                    
            except Reading.DoesNotExist:
                results['error_count'] += 1
                results['details'].append({
                    'reading_id': reading_id,
                    'status': 'error', 
                    'error': 'Reading not found'
                })
            except Exception as e:
                results['error_count'] += 1
                results['details'].append({
                    'reading_id': reading_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return JsonResponse({
            'status': 'success',
            'results': results
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error analyzing multiple readings: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)