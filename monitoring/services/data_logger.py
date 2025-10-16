"""
Logger để tự động ghi dữ liệu đo từ ESP32 vào CSV file.
Mỗi lần POST thành công sẽ ghi: ph, tds, ntu, label (0=dirty, 1=clean)
"""
import os
import csv
from datetime import datetime
from django.conf import settings


class WaterQualityLogger:
    """Logger để ghi dữ liệu đo vào CSV file"""
    
    def __init__(self, filename='esp32_measurements.csv'):
        """
        Khởi tạo logger
        
        Args:
            filename: Tên file CSV (mặc định: esp32_measurements.csv)
        """
        self.log_dir = os.path.join(settings.BASE_DIR, 'sensor_analysis', 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.filepath = os.path.join(self.log_dir, filename)
        self._initialize_file()
    
    def _initialize_file(self):
        """Tạo file CSV với header nếu chưa tồn tại"""
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header: ph, tds, ntu, label (0=dirty, 1=clean)
                writer.writerow(['ph', 'tds', 'ntu', 'label'])
    
    def log_measurement(self, ph, tds, ntu, is_clean):
        """
        Ghi một dòng đo vào CSV
        
        Args:
            ph: Giá trị pH
            tds: Giá trị TDS (mg/L hoặc ppm)
            ntu: Giá trị độ đục (NTU)
            is_clean: True (clean) hoặc False (dirty)
        
        Returns:
            bool: True nếu ghi thành công
        """
        try:
            # Chuyển is_clean thành 0/1
            label = 1 if is_clean else 0
            
            # Format số với độ chính xác phù hợp
            ph_formatted = round(float(ph), 2)
            tds_formatted = round(float(tds), 1)
            ntu_formatted = round(float(ntu), 2)
            
            # Ghi vào file
            with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([ph_formatted, tds_formatted, ntu_formatted, label])
            
            return True
        except Exception as e:
            print(f"Error logging measurement: {e}")
            return False
    
    def get_filepath(self):
        """Trả về đường dẫn đầy đủ của file CSV"""
        return self.filepath
    
    def get_row_count(self):
        """Đếm số dòng dữ liệu (không tính header)"""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return sum(1 for line in f) - 1  # Trừ header
        except:
            return 0
    
    def get_stats(self):
        """Lấy thống kê nhanh về dữ liệu đã log"""
        try:
            import pandas as pd
            df = pd.read_csv(self.filepath)
            
            total = len(df)
            clean_count = (df['label'] == 1).sum()
            dirty_count = (df['label'] == 0).sum()
            
            return {
                'total_samples': total,
                'clean_count': clean_count,
                'dirty_count': dirty_count,
                'clean_percentage': round(clean_count / total * 100, 1) if total > 0 else 0,
                'dirty_percentage': round(dirty_count / total * 100, 1) if total > 0 else 0,
                'filepath': self.filepath
            }
        except Exception as e:
            return {
                'total_samples': 0,
                'clean_count': 0,
                'dirty_count': 0,
                'clean_percentage': 0,
                'dirty_percentage': 0,
                'filepath': self.filepath,
                'error': str(e)
            }


# Singleton instance
_logger_instance = None

def get_logger(filename='esp32_measurements.csv'):
    """
    Lấy instance của logger (singleton pattern)
    
    Args:
        filename: Tên file CSV
    
    Returns:
        WaterQualityLogger: Instance của logger
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = WaterQualityLogger(filename)
    return _logger_instance
