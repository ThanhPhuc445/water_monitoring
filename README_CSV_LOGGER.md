# CSV Logger - Tự động ghi dữ liệu đo từ ESP32

## Mục đích
Mỗi khi ESP32 gửi dữ liệu đo nước về server, hệ thống sẽ tự động:
1. Gắn nhãn theo chuẩn WHO (clean=1 hoặc dirty=0)
2. Lưu vào database
3. **Tự động ghi vào file CSV** để thu thập dataset

## File CSV
**Vị trí:** `sensor_analysis/logs/esp32_measurements.csv`

**Format:**
```csv
ph,tds,ntu,label
7.2,450.0,0.8,1
5.8,300.0,0.5,0
7.0,400.0,0.9,1
```

**Giải thích các cột:**
- `ph`: Độ pH (0-14)
- `tds`: Tổng chất rắn hòa tan (mg/L hoặc ppm)
- `ntu`: Độ đục (NTU)
- `label`: **0 = nước bẩn, 1 = nước sạch** (theo chuẩn WHO strict)

## Cách hoạt động

### 1. ESP32 gửi dữ liệu
```cpp
// ESP32 POST đến /api/upload-reading-strict/
http.begin(serverUrl);
http.addHeader("Content-Type", "application/x-www-form-urlencoded");
String postData = "ph=" + String(phValue) + 
                  "&tds=" + String(tdsValue) + 
                  "&ntu=" + String(ntuValue);
int httpResponseCode = http.POST(postData);
```

### 2. Server xử lý
```python
# views.py - upload_reading_strict()

# 1. Nhận dữ liệu từ ESP32
ph = float(data.get('ph', 0))
tds = float(data.get('tds', 0))
ntu = float(data.get('ntu', 0))

# 2. Gắn nhãn bằng WHO strict rules
ai_result = predict_water_quality_strict_who(ph, ntu, tds)

# 3. Lưu vào database
reading = Reading.objects.create(
    ph=ph, tds=tds, ntu=ntu,
    ai_prediction=ai_result['prediction'],
    ...
)

# 4. TỰ ĐỘNG GHI VÀO CSV
csv_logger = get_logger()
csv_logger.log_measurement(
    ph=ph, 
    tds=tds, 
    ntu=ntu, 
    is_clean=ai_result['is_safe']  # True -> 1, False -> 0
)
```

## Quy tắc gắn nhãn (WHO Strict)

### Clean Water (label=1)
Tất cả các điều kiện sau phải thỏa mãn:
- pH: 6.5 - 8.5
- TDS: ≤ 500 mg/L
- NTU: ≤ 1.0 (ideal for disinfection)

### Dirty Water (label=0)
Nếu **BẤT KỲ** giá trị nào vi phạm:
- pH < 6.5 hoặc pH > 8.5 → dirty
- TDS > 500 mg/L → dirty (strict mode)
- NTU > 1.0 → dirty (strict mode)

**Lưu ý:** Chế độ strict nghĩa là các giá trị "borderline" (ví dụ TDS 550, NTU 1.5) cũng được đánh nhãn là dirty.

## Thu thập Dataset

### Mục tiêu của user
- 100 mẫu nước sạch (label=1)
- 100 mẫu nước bẩn (label=0)

### Cách thu thập
1. **Khởi động server:**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

2. **Đo nước sạch (100 mẫu):**
   - Dùng nước máy/nước lọc
   - ESP32 tự động POST lên server
   - Mỗi lần POST thành công → 1 dòng mới trong CSV với label=1

3. **Đo nước bẩn (100 mẫu):**
   - Thêm tạp chất/muối/chất đục
   - ESP32 POST lên server
   - Mỗi lần POST thành công → 1 dòng mới trong CSV với label=0

4. **Kiểm tra tiến độ:**
   ```bash
   # Xem toàn bộ CSV
   type sensor_analysis\logs\esp32_measurements.csv
   
   # Đếm số dòng (Windows PowerShell)
   (Get-Content sensor_analysis\logs\esp32_measurements.csv).Length - 1
   
   # Đếm số mẫu clean và dirty (Python)
   python -c "import pandas as pd; df = pd.read_csv('sensor_analysis/logs/esp32_measurements.csv'); print(df['label'].value_counts())"
   ```

## Test thử nghiệm

### Chạy test tự động
```bash
python test_csv_logger.py
```

Test này sẽ:
- Gửi 5 mẫu test (2 clean + 3 dirty)
- Kiểm tra response từ server
- Xác nhận CSV được ghi đúng

### Test bằng curl (manual)
```bash
# Test clean water
curl -X POST http://192.168.1.6:8000/api/upload-reading-strict/ ^
  -H "Content-Type: application/json" ^
  -d "{\"ph\":7.2,\"tds\":450,\"ntu\":0.8}"

# Test dirty water
curl -X POST http://192.168.1.6:8000/api/upload-reading-strict/ ^
  -H "Content-Type: application/json" ^
  -d "{\"ph\":5.5,\"tds\":600,\"ntu\":2.0}"
```

## Xem thống kê CSV bằng code

```python
from monitoring.services.data_logger import get_logger

# Lấy logger instance
logger = get_logger()

# Xem thống kê
stats = logger.get_stats()
print(f"Tổng số mẫu: {stats['total_samples']}")
print(f"Nước sạch: {stats['clean_count']} ({stats['clean_percentage']:.1f}%)")
print(f"Nước bẩn: {stats['dirty_count']} ({stats['dirty_percentage']:.1f}%)")
print(f"File path: {stats['filepath']}")
```

## Tính năng nâng cao

### 1. Xóa CSV và bắt đầu lại
```bash
del sensor_analysis\logs\esp32_measurements.csv
```
File sẽ tự động được tạo lại với header khi có POST request tiếp theo.

### 2. Backup CSV
```bash
copy sensor_analysis\logs\esp32_measurements.csv sensor_analysis\logs\backup_20250115.csv
```

### 3. Import vào pandas để phân tích
```python
import pandas as pd

df = pd.read_csv('sensor_analysis/logs/esp32_measurements.csv')

# Thống kê cơ bản
print(df.describe())

# Đếm clean/dirty
print(df['label'].value_counts())

# Giá trị trung bình theo nhóm
print(df.groupby('label').mean())
```

## Troubleshooting

### CSV có giá trị 0.0,0.0,0.0,0
**Nguyên nhân:** Server nhận được POST form data nhưng các field trống.

**Giải pháp:** Đảm bảo ESP32 gửi đúng format:
```cpp
String postData = "ph=" + String(phValue, 2) + 
                  "&tds=" + String(tdsValue, 1) + 
                  "&ntu=" + String(ntuValue, 2);
```

### File CSV không được tạo
**Nguyên nhân:** Thư mục `sensor_analysis/logs/` không tồn tại.

**Giải pháp:** Logger tự động tạo thư mục, nhưng kiểm tra quyền ghi file.

### Tất cả samples đều bị label là dirty (0)
**Nguyên nhân:** Chế độ strict rất nghiêm ngặt.

**Kiểm tra:** 
- pH có trong khoảng 6.5-8.5?
- TDS ≤ 500?
- NTU ≤ 1.0?

## Files liên quan

- **Logger class:** `monitoring/services/data_logger.py`
- **View integration:** `monitoring/views.py` (hàm `upload_reading_strict()`)
- **Labeler logic:** `sensor_analysis/labeler.py`
- **Test script:** `test_csv_logger.py`
- **CSV output:** `sensor_analysis/logs/esp32_measurements.csv`

## Tóm tắt
✅ Mỗi POST từ ESP32 → tự động ghi 1 dòng vào CSV  
✅ Format đơn giản: ph,tds,ntu,label  
✅ Label: 0=dirty, 1=clean (WHO strict)  
✅ Sẵn sàng thu thập 200 mẫu (100 clean + 100 dirty)  
✅ Tự động tạo file và thư mục nếu chưa có  
