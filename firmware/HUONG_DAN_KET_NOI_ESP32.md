# Hướng dẫn kết nối ESP32 với hệ thống gắn nhãn tự động

## 📝 Tổng quan

ESP32 sẽ:
1. Đo pH, TDS, NTU từ cảm biến
2. Gửi dữ liệu thô lên Django server qua WiFi
3. Server tự động gắn nhãn bằng Strict WHO Rules
4. Nhận kết quả (clean/dirty) từ server
5. Hiển thị trên Serial Monitor (hoặc LED/LCD)

## 🔧 Bước 1: Cấu hình WiFi và Server

### 1.1. Tìm địa chỉ IP của máy tính chạy Django

**Trên Windows (PowerShell hoặc cmd):**
```cmd
ipconfig
```

Tìm dòng "IPv4 Address" của card mạng đang dùng (WiFi hoặc Ethernet), ví dụ: `192.168.1.100`

### 1.2. Cập nhật code ESP32

File `firmware/water_sensor.ino` đã được cập nhật với:

```cpp
// Thay IP này bằng IP máy tính của bạn
const char* ssid       = "Bong Food & Drink";      // Tên WiFi
const char* password   = "trasuabong";             // Mật khẩu WiFi
const char* serverName = "http://192.168.110.231:8000/api/upload-reading-strict/";
```

**Lưu ý quan trọng:**
- ESP32 và máy tính phải cùng mạng WiFi
- Thay `192.168.110.231` bằng IP máy tính của bạn
- Port `8000` là port Django development server

### 1.3. Upload code lên ESP32

1. Mở Arduino IDE
2. Mở file `water_monitoring/firmware/water_sensor.ino`
3. Chọn board: **ESP32 Dev Module**
4. Chọn COM port của ESP32
5. Click **Upload** (Ctrl+U)

## 🚀 Bước 2: Khởi động Django Server

### 2.1. Mở terminal và chạy server

```cmd

venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
```

**Giải thích:**
- `0.0.0.0:8000` cho phép ESP32 từ mạng LAN kết nối vào
- Mặc định `127.0.0.1:8000` chỉ cho máy local truy cập

Bạn sẽ thấy:
```
Starting development server at http://0.0.0.0:8000/
Quit the server with CTRL-BREAK.
```

### 2.2. Kiểm tra firewall

Nếu ESP32 không kết nối được:

**Windows Firewall:**
1. Mở **Windows Defender Firewall**
2. Click **Allow an app through firewall**
3. Tìm Python, tick cả **Private** và **Public**
4. Hoặc tạo rule cho port 8000:
   ```cmd
   netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8000
   ```

## 📊 Bước 3: Test kết nối

### 3.1. Mở Serial Monitor của ESP32

- Arduino IDE → Tools → Serial Monitor
- Set baud rate: **115200**

### 3.2. Quan sát output

ESP32 sẽ in ra:

```
Dang ket noi WiFi...
.....
WiFi connected!
=====================================
pH: 7.20 | NTU: 0.85 | TDS: 450 ppm
POST data: ph=7.20&ntu=0.85&tds=450
Response code: 200
=> Gui du lieu THANH CONG
Response from server:
{"status":"success","message":"Data received and labeled using strict WHO rules",...}
✅ NUOC SACH - An toan de su dung
WHO Label: CLEAN
```

### 3.3. Kiểm tra trên Django server

Trên terminal chạy Django, bạn sẽ thấy:
```
[15/Oct/2025 10:30:00] "POST /api/upload-reading-strict/ HTTP/1.1" 200 XXX
INFO Processing sensor data with STRICT WHO: pH=7.2, NTU=0.85, TDS=450
INFO Successfully processed reading 123 with strict WHO labeling
```

## 🔍 Bước 4: Xem dữ liệu đã gắn nhãn

### 4.1. Vào Django Admin

1. Truy cập: http://127.0.0.1:8000/admin/
2. Login với tài khoản admin
3. Vào **Readings** → Xem các bản ghi mới

Mỗi Reading sẽ có:
- **ai_prediction**: 1 (clean) hoặc 0 (dirty)
- **ai_quality_level**: EXCELLENT, GOOD, FAIR, POOR, VERY_POOR
- **ai_safe_probability**: 0-100%
- **ai_recommendations**: ["Compliant: pH=7.2..."] hoặc ["pH out of range..."]
- **ai_model_version**: "STRICT_RULES_v1.0"

### 4.2. Hoặc xem qua Dashboard

1. Truy cập: http://127.0.0.1:8000/dashboard/
2. Xem bảng readings với nhãn tự động

## 🐛 Xử lý lỗi thường gặp

### Lỗi 1: ESP32 không kết nối được WiFi

**Triệu chứng:**
```
Dang ket noi WiFi.......(mãi không xong)
```

**Giải pháp:**
1. Kiểm tra SSID và password đúng chưa
2. ESP32 có trong vùng phủ sóng WiFi không
3. WiFi có dùng mã hóa WPA2 không (ESP32 không hỗ trợ WPA3)

### Lỗi 2: Response code 404

**Triệu chứng:**
```
Response code: 404
=> Loi khi gui du lieu
```

**Giải pháp:**
1. Kiểm tra URL trong code ESP32 đúng chưa: `/api/upload-reading-strict/`
2. Django server có đang chạy không
3. Kiểm tra IP máy tính có thay đổi không (WiFi động IP)

### Lỗi 3: Response code -1 hoặc timeout

**Triệu chứng:**
```
Response code: -1
```

**Giải pháp:**
1. Firewall block port 8000 → Allow Python qua firewall
2. IP sai → Chạy `ipconfig` kiểm tra lại
3. ESP32 và PC không cùng mạng → Kết nối cùng WiFi

### Lỗi 4: Response code 400

**Triệu chứng:**
```
Response code: 400
```

**Giải pháp:**
1. Dữ liệu gửi không hợp lệ (pH, TDS, NTU âm hoặc ngoài phạm vi)
2. Kiểm tra cảm biến có hoạt động đúng không
3. Xem log Django để biết lỗi cụ thể

## 📈 Bước 5: Thêm tính năng hiển thị (Optional)

### 5.1. Thêm LED báo hiệu

Thêm vào code ESP32:

```cpp
// Khai báo pins
#define LED_GREEN_PIN 25  // LED xanh - nước sạch
#define LED_RED_PIN   26  // LED đỏ - nước bẩn

// Trong setup()
pinMode(LED_GREEN_PIN, OUTPUT);
pinMode(LED_RED_PIN, OUTPUT);

// Trong phần xử lý response (thay comment)
if (response.indexOf("\"is_safe\":false") > 0) {
  digitalWrite(LED_RED_PIN, HIGH);   // Bật LED đỏ
  digitalWrite(LED_GREEN_PIN, LOW);
  Serial.println("❌ NUOC BAN - LED do bat");
} else {
  digitalWrite(LED_RED_PIN, LOW);
  digitalWrite(LED_GREEN_PIN, HIGH); // Bật LED xanh
  Serial.println("✅ NUOC SACH - LED xanh bat");
}
```

### 5.2. Thêm LCD hiển thị

Nếu có LCD I2C:

```cpp
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);  // Địa chỉ I2C 0x27, LCD 16x2

// Trong setup()
lcd.init();
lcd.backlight();

// Trong phần hiển thị kết quả
lcd.clear();
lcd.setCursor(0, 0);
lcd.print("pH:");
lcd.print(pHValue, 1);
lcd.print(" TDS:");
lcd.print(sensor::tds);

lcd.setCursor(0, 1);
if (response.indexOf("\"label\":\"clean\"") > 0) {
  lcd.print("Status: CLEAN ");
} else {
  lcd.print("Status: DIRTY ");
}
```

## 📝 Checklist trước khi test

- [ ] ESP32 đã upload code mới (với endpoint `/api/upload-reading-strict/`)
- [ ] WiFi SSID và password đúng
- [ ] IP máy tính đã cập nhật trong code ESP32
- [ ] Django server đang chạy: `python manage.py runserver 0.0.0.0:8000`
- [ ] Firewall đã allow port 8000
- [ ] ESP32 và PC cùng mạng WiFi
- [ ] Serial Monitor đã mở (115200 baud)
- [ ] Cảm biến pH, TDS, NTU đã kết nối đúng

## 🎯 Kết quả mong đợi

Khi test thành công:

1. **Trên Serial Monitor (ESP32):**
   - Đo và in ra pH, TDS, NTU mỗi giây
   - Gửi lên server mỗi 3 giây
   - Nhận response 200 OK
   - Hiển thị nhãn CLEAN hoặc DIRTY

2. **Trên Django terminal:**
   - Log mỗi request: `POST /api/upload-reading-strict/`
   - Log processing: `Processing sensor data with STRICT WHO`
   - Log thành công: `Successfully processed reading X`

3. **Trên Database:**
   - Reading mới tạo mỗi 3 giây
   - Có đầy đủ pH, TDS, NTU, timestamp
   - Có nhãn tự động: ai_prediction, ai_recommendations

## 🔄 Workflow hoàn chỉnh

```
[ESP32] → Đo cảm biến → Gửi HTTP POST → [Django Server]
                                              ↓
                                    Nhận pH, TDS, NTU
                                              ↓
                                    Gọi strict labeler
                                              ↓
                          Tính toán: clean/dirty + reasons
                                              ↓
                                  Lưu vào Database
                                              ↓
                             Trả về JSON response → [ESP32]
                                                         ↓
                                              Parse kết quả
                                                         ↓
                                         Hiển thị LED/LCD/Serial
```

## 📞 Cần hỗ trợ thêm?

Nếu gặp vấn đề, kiểm tra:
1. Serial Monitor của ESP32 → thấy lỗi gì
2. Django terminal → thấy log gì
3. Chạy `python test_esp32_api.py` → API có hoạt động không
4. Ping từ ESP32 đến máy tính → mạng có thông không

---

**Tóm tắt:** 
- ESP32 chỉ gửi dữ liệu thô (pH, TDS, NTU)
- Server Django tự động gắn nhãn theo WHO strict rules
- Không cần flash lại ESP32 khi thay đổi ngưỡng gắn nhãn
- Dễ bảo trì và mở rộng sau này!
