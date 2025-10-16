@echo off
echo ==========================================
echo KHOI DONG DJANGO SERVER CHO ESP32
echo ==========================================
echo.
echo Server se chay o: http://0.0.0.0:8000
echo ESP32 co the ket noi tu mang LAN
echo.
echo Nhan Ctrl+C de dung server
echo ==========================================
echo.

cd /d E:\PBL4\water_monitoring
call venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
