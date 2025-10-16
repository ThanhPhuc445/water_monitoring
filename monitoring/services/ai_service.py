"""
AI Service for Water Quality Prediction
Tích hợp mô hình AI để dự đoán chất lượng nước từ dữ liệu cảm biến
"""
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
        # Use PH + NTU model (no TDS). TDS will be used only for post-weighting.
        self.model_path = os.path.join(settings.BASE_DIR, 'sensor_analysis', 'water_quality_ph_ntu_model.pkl')
        self.features_path = os.path.join(settings.BASE_DIR, 'sensor_analysis', 'ph_ntu_features.pkl')
        # Combined weights (alpha) file produced by compute_feature_weights.py
        self.alpha = 0.7
        self.weights_path = os.path.join(settings.BASE_DIR, 'sensor_analysis', f'feature_weights_alpha{self.alpha}.csv')
        self.feature_weights = None  # dict: {'ph': w, 'Turbidity': w, 'Solids': w}
        self.min_factor = 0.6  # minimal multiplicative factor when risk score is maximal
        self._load_feature_weights()
        
    def load_model(self):
        """Load trained model và features"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.features_path):
                self.model = joblib.load(self.model_path)
                self.features = joblib.load(self.features_path)
                self.is_loaded = True
                logger.info("AI model loaded successfully")
                return True
            else:
                logger.error(f"Model files not found: {self.model_path}, {self.features_path}")
                return False
        except Exception as e:
            logger.error(f"Error loading AI model: {str(e)}")
            return False
    
    def convert_tds_to_ec(self, tds_ppm, k_factor=0.7):
        """
        Chuyển đổi TDS (ppm) sang EC (mS/cm)
        
        Args:
            tds_ppm: TDS trong ppm từ cảm biến
            k_factor: Hệ số chuyển đổi (default 0.7)
            
        Returns:
            EC trong mS/cm
        """
        if tds_ppm is None:
            return 0
        if tds_ppm <= 0:
            return 0
        return tds_ppm / (k_factor * 1000)
    
    def predict_water_quality(self, ph, turbidity_ntu, tds_ppm):
        """
        Dự đoán chất lượng nước từ dữ liệu cảm biến với safety override
        
        Args:
            ph: Độ pH (6.5-8.5)
            turbidity_ntu: Độ đục NTU (0-5)
            tds_ppm: TDS ppm (500-1000 cho nước máy)
            
        Returns:
            dict: Kết quả dự đoán
        """
        if not self.is_loaded:
            if not self.load_model():
                return self._get_fallback_result(ph, turbidity_ntu, tds_ppm)
        # Guard against None model if loading failed silently
        if self.model is None:
            logger.error("AI model is not initialized; using fallback")
            return self._get_fallback_result(ph, turbidity_ntu, tds_ppm)

        try:
            # Chuyển đổi TDS sang EC (dùng cho khuyến nghị và weighting)
            ec_ms_cm = self.convert_tds_to_ec(tds_ppm)
            
            # SAFETY OVERRIDE: Kiểm tra trước khi dùng AI
            critical_unsafe = False
            critical_reasons = []
            
            if ph < 5.0 or ph > 9.0:  # pH quá cực đoan
                critical_unsafe = True
                critical_reasons.append("pH cực đoan - nguy hiểm")
            
            if turbidity_ntu > 10.0:  # Độ đục quá cao
                critical_unsafe = True  
                critical_reasons.append("Độ đục cực cao - không an toàn")
            
            if tds_ppm > 2000:  # TDS quá cao
                critical_unsafe = True
                critical_reasons.append("TDS quá cao - không uống được")
            
            # Nếu có yếu tố nguy hiểm cực đoan, override AI
            if critical_unsafe:
                return {
                    'prediction': 0,
                    'is_safe': False,
                    'safe_probability': 5.0,
                    'risk_probability': 95.0,
                    'quality_level': "VERY_POOR",
                    'risk_level': "HIGH",
                    'input_data': {
                        'ph': ph,
                        'turbidity_ntu': turbidity_ntu,
                        'tds_ppm': tds_ppm,
                        'ec_ms_cm': round(ec_ms_cm, 3)
                    },
                    'recommendations': critical_reasons + ["⚠️ NGUY HIỂM - KHÔNG SỬ DỤNG"],
                    'timestamp': timezone.now(),
                    'model_version': 'SAFETY_OVERRIDE_v1.0'
                }
            
            # Chuẩn bị input cho model PH + NTU (không dùng EC/TDS)
            # Use DataFrame with feature names to align with training and suppress warnings
            columns = self.features if self.features else ['ph', 'Turbidity']
            input_data = pd.DataFrame([[ph, turbidity_ntu]], columns=columns)
            
            # Dự đoán
            prediction = self.model.predict(input_data)[0]
            probability = self.model.predict_proba(input_data)[0]
            
            # Tính xác suất
            safe_prob = probability[1] * 100
            risk_prob = probability[0] * 100

            # Combined post-weighting using weights for ph, Turbidity, Solids
            factor, risk_score, devs = self._compute_weighted_factor(ph, turbidity_ntu, tds_ppm)
            safe_prob = round(max(0.0, min(100.0, safe_prob * factor)), 1)
            risk_prob = 100.0 - safe_prob
            
            # SECONDARY SAFETY CHECK: Override khi AI sai rõ ràng
            if prediction == 1:  # AI nói SAFE
                unsafe_factors = []
                
                if ph < 6.0 or ph > 9.0:
                    unsafe_factors.append("pH ngoài giới hạn an toàn")
                
                if turbidity_ntu > 5.0:
                    unsafe_factors.append("Độ đục quá cao")
                
                if tds_ppm is not None and tds_ppm < 10:  # TDS quá thấp bất thường
                    unsafe_factors.append("TDS bất thường thấp")
                
                # Nếu có >= 2 yếu tố không an toàn, override AI
                if len(unsafe_factors) >= 2:
                    logger.warning(f"AI OVERRIDE: pH={ph}, NTU={turbidity_ntu}, TDS={tds_ppm} - {unsafe_factors}")
                    prediction = 0
                    safe_prob = min(safe_prob, 25.0)  # Giảm xuống tối đa 25%
                    risk_prob = 100 - safe_prob
            
            # Phân loại mức độ
            quality_level = self._get_quality_level(safe_prob)
            risk_level = self._get_risk_level(ph, turbidity_ntu, ec_ms_cm)
            
            result = {
                'prediction': int(prediction),
                'is_safe': bool(prediction == 1),
                'safe_probability': round(safe_prob, 1),
                'risk_probability': round(risk_prob, 1),
                'quality_level': quality_level,
                'risk_level': risk_level,
                'input_data': {
                    'ph': ph,
                    'turbidity_ntu': turbidity_ntu,
                    'tds_ppm': tds_ppm,
                    'ec_ms_cm': round(ec_ms_cm, 3)
                },
                'recommendations': self._get_recommendations(ph, turbidity_ntu, ec_ms_cm, prediction),
                'timestamp': timezone.now(),
                'model_version': 'PH_NTU_v1.0',
                'post_weighting': {
                    'factor': round(factor, 3),
                    'risk_score': round(risk_score, 3),
                    'deviations': devs,
                    'weights_used': self.feature_weights
                }
            }
            
            logger.info(f"AI Prediction: pH={ph}, NTU={turbidity_ntu}, TDS={tds_ppm} -> {quality_level}")
            return result
            
        except Exception as e:
            logger.error(f"Error in AI prediction: {str(e)}")
            return self._get_fallback_result(ph, turbidity_ntu, tds_ppm)
    
    def _get_quality_level(self, safe_prob):
        """Xác định mức độ chất lượng"""
        if safe_prob >= 80:
            return "EXCELLENT"
        elif safe_prob >= 65:
            return "GOOD"
        elif safe_prob >= 50:
            return "FAIR"
        elif safe_prob >= 30:
            return "POOR"
        else:
            return "VERY_POOR"
    
    def _get_risk_level(self, ph, turbidity_ntu, ec_ms_cm):
        """Xác định mức độ rủi ro"""
        risk_factors = 0
        
        # Kiểm tra pH
        if ph < 6.5 or ph > 8.5:
            risk_factors += 1
        
        # Kiểm tra turbidity
        if turbidity_ntu > 1.0:
            risk_factors += 1
        if turbidity_ntu > 4.0:
            risk_factors += 1
        
        # Kiểm tra EC
        if ec_ms_cm > 1.5 or ec_ms_cm < 0.3:
            risk_factors += 1
        
        if risk_factors == 0:
            return "LOW"
        elif risk_factors <= 2:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _get_recommendations(self, ph, turbidity_ntu, ec_ms_cm, prediction):
        """Đưa ra khuyến nghị"""
        recommendations = []
        
        # Khuyến nghị về pH
        if ph < 6.5:
            recommendations.append("pH quá thấp - cần tăng pH")
        elif ph > 8.5:
            recommendations.append("pH quá cao - cần giảm pH")
        
        # Khuyến nghị về độ đục
        if turbidity_ntu > 1.0:
            recommendations.append("Độ đục cao - cần lọc")
        if turbidity_ntu > 4.0:
            recommendations.append("Độ đục rất cao - không nên sử dụng")
        
        # Khuyến nghị về EC
        if ec_ms_cm > 1.5:
            recommendations.append("EC cao - nước chứa nhiều muối khoáng")
        elif ec_ms_cm < 0.3:
            recommendations.append("EC thấp - nước quá tinh khiết")
        
        # Khuyến nghị tổng quát
        if prediction == 0:
            recommendations.append("⚠️ KHÔNG AN TOÀN - cần xử lý thêm")
        else:
            recommendations.append("✅ CÓ THỂ SỬ DỤNG")
        
        return recommendations
    
    def _get_fallback_result(self, ph, turbidity_ntu, tds_ppm):
        """Kết quả dự phòng khi AI model không hoạt động"""
        # Rule-based fallback
        is_safe = True
        risk_factors = []
        
        if ph < 6.5 or ph > 8.5:
            is_safe = False
            risk_factors.append("pH ngoài giới hạn")
        
        if turbidity_ntu > 4.0:
            is_safe = False
            risk_factors.append("Độ đục quá cao")
        
        if tds_ppm > 1000 or tds_ppm < 50:
            is_safe = False
            risk_factors.append("TDS ngoài giới hạn")
        
        return {
            'prediction': 1 if is_safe else 0,
            'is_safe': is_safe,
            'safe_probability': 75.0 if is_safe else 25.0,
            'risk_probability': 25.0 if is_safe else 75.0,
            'quality_level': "GOOD" if is_safe else "POOR",
            'risk_level': "LOW" if is_safe else "HIGH",
            'input_data': {
                'ph': ph,
                'turbidity_ntu': turbidity_ntu,
                'tds_ppm': tds_ppm,
                'ec_ms_cm': self.convert_tds_to_ec(tds_ppm)
            },
            'recommendations': risk_factors if risk_factors else ["Chất lượng chấp nhận được"],
            'timestamp': timezone.now(),
            'model_version': 'FALLBACK_v1.0'
        }
    
    def get_model_status(self):
        """Kiểm tra trạng thái model"""
        return {
            'is_loaded': self.is_loaded,
            'model_path': self.model_path,
            'features_path': self.features_path,
            'model_exists': os.path.exists(self.model_path),
            'features_exists': os.path.exists(self.features_path),
            'weights_path': self.weights_path,
            'weights_exists': os.path.exists(self.weights_path),
            'alpha': self.alpha
        }

    def _load_feature_weights(self):
        """Load combined feature weights from CSV. Expect columns: Thong_so, Weight
        Falls back to defaults if file missing.
        """
        try:
            if os.path.exists(self.weights_path):
                df = pd.read_csv(self.weights_path)
                # Normalize by sum to ensure weights sum to 1 for selected features
                mapping = {}
                for _, row in df.iterrows():
                    name = str(row.get('Thong_so'))
                    w = float(row.get('Weight', 0.0))
                    mapping[name] = w
                # Extract only the features we use in post-processing
                keys = ['ph', 'Turbidity', 'Solids']
                selected = {k: mapping.get(k, 0.0) for k in keys}
                s = sum(selected.values()) or 1.0
                self.feature_weights = {k: (v / s) for k, v in selected.items()}
            else:
                # Reasonable fallback normalized weights (based on earlier run)
                base = {'ph': 0.180607, 'Turbidity': 0.160564, 'Solids': 0.419466}
                s = sum(base.values())
                self.feature_weights = {k: v / s for k, v in base.items()}
        except Exception as e:
            logger.error(f"Error loading feature weights: {e}")
            base = {'ph': 0.18, 'Turbidity': 0.16, 'Solids': 0.42}
            s = sum(base.values())
            self.feature_weights = {k: v / s for k, v in base.items()}

    def _compute_weighted_factor(self, ph, turbidity_ntu, tds_ppm):
        """Compute multiplicative factor from feature deviations and learned weights.
        - Deviation is in [0,1] where 0 means ideal/safe range, 1 means worst among chosen bounds.
        - Risk score = sum_j w_j * dev_j, w normalized to sum 1.
        - Factor = 1 - (1 - min_factor) * risk_score.
        Returns (factor, risk_score, deviations_dict)
        """
        w = self.feature_weights or {'ph': 1/3, 'Turbidity': 1/3, 'Solids': 1/3}

        # pH deviation: 0 if 6.5..8.5; ramp to 1 at <=5.0 or >=9.0
        if ph is None:
            dev_ph = 0.0
        elif 6.5 <= ph <= 8.5:
            dev_ph = 0.0
        elif ph < 6.5:
            dev_ph = min(1.0, (6.5 - ph) / (6.5 - 5.0))
        else:  # ph > 8.5
            dev_ph = min(1.0, (ph - 8.5) / (9.0 - 8.5))

        # Turbidity deviation: 0 at <=1 NTU, linearly to 1 at 5 NTU; clamp beyond
        if turbidity_ntu is None:
            dev_ntu = 0.0
        elif turbidity_ntu <= 1.0:
            dev_ntu = 0.0
        elif turbidity_ntu >= 5.0:
            dev_ntu = 1.0
        else:
            dev_ntu = (turbidity_ntu - 1.0) / (5.0 - 1.0)

        # TDS deviation: 0 in [50,1000]; ramp to 1 at 0 or 2000
        if tds_ppm is None:
            dev_tds = 0.0
        else:
            try:
                tds_val = float(tds_ppm)
                if 50 <= tds_val <= 1000:
                    dev_tds = 0.0
                elif tds_val < 50:
                    dev_tds = min(1.0, (50 - tds_val) / 50.0)
                else:  # > 1000
                    dev_tds = min(1.0, (tds_val - 1000) / 1000.0)
            except Exception:
                dev_tds = 0.0

        devs = {'ph': round(dev_ph, 3), 'Turbidity': round(dev_ntu, 3), 'Solids': round(dev_tds, 3)}
        risk_score = (
            w.get('ph', 0.0) * dev_ph +
            w.get('Turbidity', 0.0) * dev_ntu +
            w.get('Solids', 0.0) * dev_tds
        )
        risk_score = max(0.0, min(1.0, risk_score))
        factor = 1.0 - (1.0 - self.min_factor) * risk_score
        factor = max(self.min_factor, min(1.0, factor))
        return factor, risk_score, devs

# Singleton instance
water_quality_ai = WaterQualityAI()

def predict_water_quality(ph, turbidity_ntu, tds_ppm):
    """
    Convenience function để dự đoán chất lượng nước
    
    Args:
        ph: Độ pH
        turbidity_ntu: Độ đục (NTU)
        tds_ppm: TDS (ppm)
    
    Returns:
        dict: Kết quả dự đoán
    """
    return water_quality_ai.predict_water_quality(ph, turbidity_ntu, tds_ppm)

def get_ai_status():
    """Lấy trạng thái AI service"""
    return water_quality_ai.get_model_status()


def predict_water_quality_strict_who(ph, turbidity_ntu, tds_ppm):
    """
    Dự đoán chất lượng nước bằng strict WHO rules (không dùng ML).
    Trả về dict tương thích với format của predict_water_quality để dễ thay thế.
    
    Args:
        ph: Độ pH
        turbidity_ntu: Độ đục (NTU)
        tds_ppm: TDS (ppm/mg/L)
    
    Returns:
        dict: {
            'prediction': 0/1,
            'is_safe': bool,
            'safe_probability': 0-100,
            'risk_probability': 0-100,
            'quality_level': str,
            'risk_level': str,
            'recommendations': list[str],
            'model_version': str,
            'input_data': dict,
            'timestamp': datetime,
            'strict_who_details': dict  # thêm thông tin chi tiết từ labeler
        }
    """
    from sensor_analysis.labeler import compute_label, LabelConfig
    from django.utils import timezone as tz
    
    # Gọi strict labeler
    cfg = LabelConfig(strict=True)  # Chính sách nghiêm mặc định
    result = compute_label(ph, tds_ppm, turbidity_ntu, cfg)
    
    is_clean = result['is_clean']
    confidence = result['confidence']  # 0..1
    
    # Ánh xạ sang format tương thích với AI service
    prediction = 1 if is_clean else 0
    # Map confidence (0..1) sang probability (0..100)
    # Nếu clean: safe_prob dựa trên confidence
    # Nếu dirty: safe_prob = 0
    if is_clean:
        safe_prob = round(max(50.0, confidence * 100.0), 1)  # clean ít nhất 50%
    else:
        safe_prob = round(min(40.0, confidence * 100.0), 1)  # dirty tối đa 40%
    
    risk_prob = 100.0 - safe_prob
    
    # Quality level mapping dựa trên safe_prob
    if safe_prob >= 80:
        quality_level = "EXCELLENT"
    elif safe_prob >= 65:
        quality_level = "GOOD"
    elif safe_prob >= 50:
        quality_level = "FAIR"
    elif safe_prob >= 30:
        quality_level = "POOR"
    else:
        quality_level = "VERY_POOR"
    
    # Risk level: nếu dirty hoặc có vi phạm nào đó => HIGH, ngược lại LOW/MEDIUM
    if not is_clean:
        risk_level = "HIGH"
    elif confidence < 0.5:  # sát biên
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    return {
        'prediction': prediction,
        'is_safe': is_clean,
        'safe_probability': safe_prob,
        'risk_probability': risk_prob,
        'quality_level': quality_level,
        'risk_level': risk_level,
        'recommendations': result['reasons'],
        'model_version': 'STRICT_WHO_v1.0',
        'input_data': {
            'ph': ph,
            'turbidity_ntu': turbidity_ntu,
            'tds_ppm': tds_ppm,
        },
        'timestamp': tz.now(),
        'strict_who_details': {
            'label': result['label'],
            'confidence': result['confidence'],
            'margins': result['margins'],
        }
    }