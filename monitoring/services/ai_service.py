# monitoring/services/ai_service.py
import os
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class WaterQualityAI:
    """Service class để dự đoán chất lượng nước"""
    
    def __init__(self):
        self.model = None
        self.features = None
        self.is_loaded = False
        self.model_path = os.path.join(settings.BASE_DIR, 'models', 'water_quality_model.pkl')
        self.features_path = os.path.join(settings.BASE_DIR, 'models', 'water_quality_features.pkl')
        self._load_model()
        
    def _load_model(self):
        """Load trained model và features"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.features_path):
                self.model = joblib.load(self.model_path)
                self.features = joblib.load(self.features_path)
                self.is_loaded = True
                logger.info("✅ AI model loaded successfully")
                logger.info(f"📊 Model features: {self.features}")
                return True
            else:
                logger.warning(f"⚠️ Model files not found, using rule-based system")
                return False
        except Exception as e:
            logger.error(f"❌ Error loading AI model: {str(e)}")
            return False
    
    def predict_water_quality(self, ph, tds, ntu):
        """
        Dự đoán chất lượng nước - ưu tiên AI model, fallback rule-based
        """
        # Kiểm tra dữ liệu đầu vào
        if ph is None or tds is None or ntu is None:
            return self._get_fallback_result(ph, tds, ntu)
        
        if self.is_loaded:
            try:
                return self._predict_with_ai(ph, tds, ntu)
            except Exception as e:
                logger.error(f"❌ AI prediction failed, using rule-based: {str(e)}")
                return self._predict_rule_based(ph, tds, ntu)
        else:
            return self._predict_rule_based(ph, tds, ntu)
    
    def _predict_with_ai(self, ph, tds, ntu):
        """Dự đoán sử dụng AI model"""
        # Chuẩn bị input data
        input_data = np.array([[ph, tds, ntu]])
        input_df = pd.DataFrame(input_data, columns=self.features)
        
        # Dự đoán
        prediction = self.model.predict(input_df)[0]
        probability = self.model.predict_proba(input_df)[0]
        
        # Tính xác suất
        safe_prob = probability[1] * 100  # Xác suất lớp 1 (Sạch)
        risk_prob = probability[0] * 100  # Xác suất lớp 0 (Bẩn)
        
        # Xác định kết quả cuối cùng
        final_prediction = 1 if safe_prob >= 50 else 0
        
        # Phân loại chất lượng
        quality_level = self._get_quality_level(safe_prob)
        risk_level = self._get_risk_level(safe_prob)
        
        result = {
            'prediction': int(final_prediction),
            'is_safe': bool(final_prediction == 1),
            'safe_probability': round(safe_prob, 1),
            'risk_probability': round(risk_prob, 1),
            'quality_level': quality_level,
            'risk_level': risk_level,
            'input_data': {'ph': ph, 'tds': tds, 'ntu': ntu},
            'recommendations': self._get_recommendations(ph, tds, ntu, final_prediction),
            'timestamp': timezone.now(),
            'model_version': 'RF_ESP32_v1.0'
        }
        
        logger.info(f"🤖 AI Prediction: pH={ph}, TDS={tds}, NTU={ntu} -> {quality_level} ({safe_prob:.1f}%)")
        return result
    
    def _predict_rule_based(self, ph, tds, ntu):
        """Dự đoán sử dụng rule-based system"""
        # Rule-based theo tiêu chuẩn WHO
        is_safe = True
        reasons = []
        violation_count = 0
        
        # Kiểm tra pH (WHO: 6.5-8.5)
        if ph < 6.5 or ph > 8.5:
            is_safe = False
            violation_count += 1
            reasons.append(f"pH ngoài ngưỡng an toàn (6.5-8.5): {ph:.2f}")
        elif 6.5 <= ph <= 8.5:
            reasons.append("pH trong ngưỡng an toàn")
        
        # Kiểm tra độ đục (WHO: < 1 NTU, chấp nhận đến 4 NTU)
        if ntu > 4.0:
            is_safe = False
            violation_count += 1
            reasons.append(f"Độ đục quá cao (>4.0 NTU): {ntu:.2f}")
        elif ntu > 1.0:
            violation_count += 0.5
            reasons.append(f"Độ đục cao (>1.0 NTU): {ntu:.2f}")
        else:
            reasons.append("Độ đục trong ngưỡng an toàn")
        
        # Kiểm tra TDS (WHO: < 500 ppm, chấp nhận đến 1000 ppm)
        if tds > 1000:
            is_safe = False
            violation_count += 1
            reasons.append(f"TDS quá cao (>1000 ppm): {tds:.0f}")
        elif tds > 500:
            violation_count += 0.5
            reasons.append(f"TDS cao (>500 ppm): {tds:.0f}")
        else:
            reasons.append("TDS trong ngưỡng an toàn")
        
        # Tính độ tin cậy dựa trên số lượng vi phạm
        if is_safe:
            safe_prob = max(50.0, 100.0 - (violation_count * 20.0))
        else:
            safe_prob = max(10.0, 40.0 - (violation_count * 15.0))
        
        risk_prob = 100.0 - safe_prob
        
        # Quality level mapping
        if safe_prob >= 85:
            quality_level = "RẤT TỐT"
        elif safe_prob >= 70:
            quality_level = "TỐT"
        elif safe_prob >= 55:
            quality_level = "TRUNG BÌNH"
        elif safe_prob >= 40:
            quality_level = "KÉM"
        else:
            quality_level = "RẤT KÉM"
        
        # Risk level
        if not is_safe or violation_count >= 2:
            risk_level = "CAO"
        elif violation_count == 1:
            risk_level = "TRUNG BÌNH"
        else:
            risk_level = "THẤP"
        
        # Thêm khuyến nghị tổng quát
        if is_safe:
            reasons.append("✅ NƯỚC CÓ THỂ SỬ DỤNG")
        else:
            reasons.append("⚠️ KHÔNG NÊN SỬ DỤNG - cần xử lý thêm")
        
        return {
            'prediction': 1 if is_safe else 0,
            'is_safe': is_safe,
            'safe_probability': round(safe_prob, 1),
            'risk_probability': round(risk_prob, 1),
            'quality_level': quality_level,
            'risk_level': risk_level,
            'input_data': {'ph': ph, 'tds': tds, 'ntu': ntu},
            'recommendations': reasons,
            'timestamp': timezone.now(),
            'model_version': 'RULE_BASED_v1.0'
        }
    
    def _get_quality_level(self, safe_prob):
        """Xác định mức độ chất lượng"""
        if safe_prob >= 85:
            return "RẤT TỐT"
        elif safe_prob >= 70:
            return "TỐT"
        elif safe_prob >= 55:
            return "TRUNG BÌNH"
        elif safe_prob >= 40:
            return "KÉM"
        else:
            return "RẤT KÉM"
    
    def _get_risk_level(self, safe_prob):
        """Xác định mức độ rủi ro"""
        if safe_prob >= 70:
            return "THẤP"
        elif safe_prob >= 50:
            return "TRUNG BÌNH"
        else:
            return "CAO"
    
    def _get_recommendations(self, ph, tds, ntu, prediction):
        """Đưa ra khuyến nghị dựa trên kết quả"""
        recommendations = []
        
        # Khuyến nghị về pH
        if ph < 6.5:
            recommendations.append("pH quá thấp - cần tăng pH")
        elif ph > 8.5:
            recommendations.append("pH quá cao - cần giảm pH")
        elif 6.5 <= ph <= 8.5:
            recommendations.append("pH trong ngưỡng an toàn")
        
        # Khuyến nghị về độ đục
        if ntu > 4.0:
            recommendations.append(f"Độ đục rất cao ({ntu:.2f} NTU) - cần lọc khẩn cấp")
        elif ntu > 1.0:
            recommendations.append(f"Độ đục cao ({ntu:.2f} NTU) - cần lọc")
        elif ntu <= 1.0:
            recommendations.append("Độ đục trong ngưỡng an toàn")
        
        # Khuyến nghị về TDS
        if tds > 1000:
            recommendations.append(f"TDS rất cao ({tds:.0f} ppm) - không nên sử dụng")
        elif tds > 500:
            recommendations.append(f"TDS cao ({tds:.0f} ppm) - có thể chứa nhiều khoáng chất")
        elif tds < 50:
            recommendations.append(f"TDS thấp ({tds:.0f} ppm) - nước quá tinh khiết")
        else:
            recommendations.append("TDS trong ngưỡng phù hợp")
        
        # Khuyến nghị tổng quát
        if prediction == 1:
            recommendations.append("✅ NƯỚC AN TOÀN CHO SỬ DỤNG")
        else:
            recommendations.append("❌ KHÔNG AN TOÀN - CẦN XỬ LÝ")
        
        return recommendations
    
    def _get_fallback_result(self, ph, tds, ntu):
        """Kết quả dự phòng khi có lỗi"""
        return {
            'prediction': 0,
            'is_safe': False,
            'safe_probability': 0.0,
            'risk_probability': 100.0,
            'quality_level': "CHƯA PHÂN TÍCH",
            'risk_level': "CAO",
            'input_data': {'ph': ph, 'tds': tds, 'ntu': ntu},
            'recommendations': ["Thiếu dữ liệu cảm biến để phân tích"],
            'timestamp': timezone.now(),
            'model_version': 'FALLBACK'
        }
    
    def get_model_status(self):
        """Kiểm tra trạng thái model"""
        return {
            'is_loaded': self.is_loaded,
            'model_path': self.model_path,
            'features_path': self.features_path,
            'model_exists': os.path.exists(self.model_path),
            'features_exists': os.path.exists(self.features_path),
            'message': 'AI đã sẵn sàng' if self.is_loaded else 'Sử dụng rule-based system'
        }

# Singleton instance
water_quality_ai = WaterQualityAI()

# Các hàm public để sử dụng từ bên ngoài
def predict_water_quality(ph, tds, ntu):
    """Hàm chính để dự đoán chất lượng nước"""
    return water_quality_ai.predict_water_quality(ph, tds, ntu)

def get_ai_status():
    """Lấy trạng thái AI service"""
    return water_quality_ai.get_model_status()

def predict_water_quality_simple(ph, tds, ntu):
    """
    Phiên bản đơn giản - trả về kết quả số (0/1) thay vì chuỗi
    """
    try:
        result = predict_water_quality(ph, tds, ntu)
        return {
            'prediction': result['prediction'],
            'confidence': result['safe_probability'],
            'quality_level': result['quality_level'],
            'is_safe': result['is_safe']
        }
    except Exception as e:
        logger.error(f"Error in simple prediction: {str(e)}")
        # Fallback đơn giản
        is_safe = True
        if ph is not None and (ph < 6.5 or ph > 8.5):
            is_safe = False
        elif ntu is not None and ntu > 5.0:
            is_safe = False
        elif tds is not None and tds > 1000:
            is_safe = False
            
        return {
            'prediction': 1 if is_safe else 0,
            'confidence': 75.0 if is_safe else 25.0,
            'quality_level': "TỐT" if is_safe else "KÉM",
            'is_safe': is_safe
        }