import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline # Để tạo chuỗi các bước tiền xử lý và mô hình
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    roc_auc_score, roc_curve, make_scorer, f1_score
)
import matplotlib.pyplot as plt
import seaborn as sns
import joblib # Để lưu và tải mô hình, scaler

# =========================================================
# 0. CẤU HÌNH VÀ THIẾT LẬP BAN ĐẦU
# =========================================================
RANDOM_STATE = 42
TEST_SIZE = 0.2
CONTAMINATION_RATE = 0.05 # Tỷ lệ dự kiến bất thường cho Isolation Forest

# Các đặc trưng mà bạn quan tâm từ cảm biến
SELECTED_FEATURES = ["ph", "Turbidity", "Solids"]

print("=== BẮT ĐẦU XÂY DỰNG MÔ HÌNH AI CHUẨN ĐOÁN CHẤT LƯỢNG NƯỚC ===")

# =========================================================
# GIAI ĐOẠN 1: TIỀN XỬ LÝ DỮ LIỆU
# =========================================================

print("\n--- Giai đoạn 1: Tiền xử lý dữ liệu ---")

# 1. Đọc dataset
try:
    df = pd.read_csv("water_potability.csv")
    print(f"Đã đọc dataset. Kích thước ban đầu: {df.shape}")
except FileNotFoundError:
    print("Lỗi: Không tìm thấy file 'water_potability.csv'. Vui lòng kiểm tra đường dẫn.")
    exit()

# 2. Xử lý giá trị thiếu (Missing Values)
# Ở đây ta sẽ điền bằng median thay vì dropna() để giữ lại nhiều dữ liệu hơn,
# đặc biệt nếu số lượng missing values không quá lớn.
# Nếu bạn muốn loại bỏ: df.dropna(inplace=True)
for col in SELECTED_FEATURES:
    if df[col].isnull().any():
        median_val = df[col].median()
        df[col].fillna(median_val, inplace=True)
        print(f"Đã điền giá trị thiếu của cột '{col}' bằng trung vị ({median_val:.2f}).")

# Điền giá trị thiếu cho các cột khác nếu có và cần thiết
# Ví dụ: for col in df.columns: if df[col].isnull().any(): df[col].fillna(df[col].median(), inplace=True)

print(f"Kích thước dataset sau khi xử lý giá trị thiếu: {df.shape}")

# Định nghĩa đặc trưng (X) và nhãn (y)
X = df[SELECTED_FEATURES]
y = df["Potability"]

print(f"Đang sử dụng {len(SELECTED_FEATURES)} đặc trưng chính: {SELECTED_FEATURES}")
print(f"Phân bố nhãn Potability:\n{y.value_counts(normalize=True)}")

# 3. Chia tập dữ liệu thành tập huấn luyện và tập kiểm tra
# 'stratify=y' đảm bảo tỷ lệ lớp cân bằng giữa train/test set
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
)

print(f"\nKích thước tập huấn luyện: {X_train.shape}")
print(f"Kích thước tập kiểm tra: {X_test.shape}")
print(f"Tỷ lệ Potability=1 trong tập huấn luyện: {y_train.mean():.2f}")
print(f"Tỷ lệ Potability=1 trong tập kiểm tra: {y_test.mean():.2f}")

# =========================================================
# GIAI ĐOẠN 2: HUẤN LUYỆN VÀ TỐI ƯU HÓA MÔ HÌNH PHÂN LOẠI
# =========================================================

print("\n--- Giai đoạn 2: Huấn luyện và tối ưu hóa mô hình phân loại ---")

# 4. Xây dựng Pipeline cho mô hình phân loại
# Pipeline giúp chuỗi hóa các bước tiền xử lý và mô hình một cách gọn gàng
clf_pipeline = Pipeline([
    ('scaler', StandardScaler()), # Bước 1: Chuẩn hóa dữ liệu
    ('classifier', RandomForestClassifier(random_state=RANDOM_STATE, class_weight='balanced')) # Bước 2: Mô hình Random Forest
])

# 5. Tối ưu hóa siêu tham số (Hyperparameter Tuning) với GridSearchCV
# Tìm bộ siêu tham số tốt nhất cho Random Forest
param_grid = {
    'classifier__n_estimators': [50, 100, 200], # Số lượng cây quyết định
    'classifier__max_depth': [None, 10, 20],   # Độ sâu tối đa của cây
    'classifier__min_samples_leaf': [1, 2, 4]  # Số lượng mẫu tối thiểu ở mỗi lá
}

# Sử dụng F1-score làm tiêu chí tối ưu vì dữ liệu có thể không cân bằng
scorer = make_scorer(f1_score, average='weighted')

grid_search = GridSearchCV(
    clf_pipeline,
    param_grid,
    cv=5, # Cross-validation với 5 folds
    scoring=scorer,
    n_jobs=-1, # Sử dụng tất cả các nhân CPU
    verbose=1
)

print("\nĐang thực hiện GridSearchCV để tìm siêu tham số tốt nhất cho Random Forest...")
grid_search.fit(X_train, y_train) # Huấn luyện GridSearchCV trên X_train (chưa chuẩn hóa)

best_clf_model = grid_search.best_estimator_
print(f"\nSiêu tham số tốt nhất tìm được: {grid_search.best_params_}")
print(f"F1-score tốt nhất trên tập huấn luyện (CV): {grid_search.best_score_:.3f}")

# 6. Đánh giá Hiệu suất của Mô hình Phân loại Tốt nhất trên tập kiểm tra
print("\n=== Đánh giá Hiệu suất của Mô hình Random Forest TỐT NHẤT ===")
y_pred = best_clf_model.predict(X_test)
y_pred_proba = best_clf_model.predict_proba(X_test)[:, 1] # Xác suất cho lớp dương tính (Potability=1)

print(f"Độ chính xác (Accuracy): {accuracy_score(y_test, y_pred):.3f}")
print("\nMa trận nhầm lẫn:")
print(confusion_matrix(y_test, y_pred))
print("\nBáo cáo phân loại:")
print(classification_report(y_test, y_pred))
print(f"ROC AUC Score: {roc_auc_score(y_test, y_pred_proba):.3f}")

# Vẽ đường cong ROC
fpr, tpr, thresholds = roc_curve(y_test, y_pred_proba)
plt.figure(figsize=(8, 6))
plt.plot(fpr, tpr, label=f'Random Forest (AUC = {roc_auc_score(y_test, y_pred_proba):.2f})')
plt.plot([0, 1], [0, 1], 'k--', label='Ngẫu nhiên (AUC = 0.50)')
plt.xlabel('Tỷ lệ Dương tính giả (False Positive Rate)')
plt.ylabel('Tỷ lệ Dương tính thật (True Positive Rate)')
plt.title('Đường cong ROC')
plt.legend(loc='lower right')
plt.grid(True)
plt.show()

# 7. Phân tích Feature Importance từ mô hình tốt nhất
# Lấy scaler và classifier từ pipeline
fitted_scaler = best_clf_model.named_steps['scaler']
fitted_classifier = best_clf_model.named_steps['classifier']

print("\n=== Phân tích Feature Importance từ mô hình TỐT NHẤT ===")
feature_importances = pd.Series(fitted_classifier.feature_importances_, index=SELECTED_FEATURES).sort_values(ascending=False)
print("Các đặc trưng quan trọng nhất đối với mô hình dự đoán Potability:")
print(feature_importances)

# Vẽ biểu đồ Feature Importance
plt.figure(figsize=(10, 6))
sns.barplot(x=feature_importances.values, y=feature_importances.index, palette='viridis')
plt.title('Feature Importance từ Random Forest (3 đặc trưng)')
plt.xlabel('Mức độ quan trọng')
plt.ylabel('Đặc trưng')
plt.show()

# =========================================================
# GIAI ĐOẠN 3: HUẤN LUYỆN VÀ ĐÁNH GIÁ MÔ HÌNH PHÁT HIỆN BẤT THƯỜNG
# =========================================================

print("\n--- Giai đoạn 3: Huấn luyện mô hình phát hiện bất thường ---")

# 8. Huấn luyện Mô hình Phát hiện Bất thường (Isolation Forest)
# Isolation Forest được huấn luyện trên dữ liệu huấn luyện đã chuẩn hóa.
# Lưu ý: IsolationForest thường được huấn luyện trên toàn bộ X (đã chuẩn hóa) hoặc X_train_scaled
# vì nó là mô hình không giám sát (không cần nhãn y).
# Chúng ta sẽ huấn luyện trên X_train đã được xử lý bởi scaler của pipeline
anomaly_detector = IsolationForest(random_state=RANDOM_STATE, contamination=CONTAMINATION_RATE)
anomaly_detector.fit(fitted_scaler.transform(X_train)) # Áp dụng scaler từ pipeline

print(f"\nĐã huấn luyện Mô hình Isolation Forest với contamination={CONTAMINATION_RATE*100:.0f}%")

# =========================================================
# GIAI ĐOẠN 4: LƯU TRỮ MÔ HÌNH VÀ TRIỂN KHAI
# =========================================================

print("\n--- Giai đoạn 4: Lưu trữ mô hình và triển khai ---")

# 9. Lưu các mô hình đã huấn luyện và các thành phần cần thiết
joblib.dump(best_clf_model, 'clf_pipeline_potability.pkl') # Lưu cả pipeline
joblib.dump(anomaly_detector, 'anomaly_detector_potability.pkl')
joblib.dump(SELECTED_FEATURES, 'selected_features.pkl') # Lưu danh sách đặc trưng

print("\nĐã lưu Pipeline phân loại, Isolation Forest và danh sách đặc trưng vào file .pkl")

print("\n=== KẾT THÚC GIAI ĐOẠN HUẤN LUYỆN VÀ ĐÁNH GIÁ ===")

# =========================================================
# GIAI ĐOẠN 5: SỬ DỤNG MÔ HÌNH ĐÃ HUẤN LUYỆN ĐỂ DỰ ĐOÁN DỮ LIỆU MỚI
# =========================================================

print("\n\n=== BẮT ĐẦU SỬ DỤNG MÔ HÌNH ĐÃ HUẤN LUYỆN CHO DỮ LIỆU MỚI ===")

# Tải các mô hình và scaler đã lưu
try:
    loaded_clf_pipeline = joblib.load('clf_pipeline_potability.pkl')
    loaded_anomaly_detector = joblib.load('anomaly_detector_potability.pkl')
    loaded_selected_features = joblib.load('selected_features.pkl')
    
    # Trích xuất scaler từ pipeline đã tải để sử dụng độc lập cho Isolation Forest nếu cần
    loaded_scaler_from_pipeline = loaded_clf_pipeline.named_steps['scaler']
    loaded_classifier_from_pipeline = loaded_clf_pipeline.named_steps['classifier']

    print("\nĐã tải Pipeline phân loại, Isolation Forest và danh sách đặc trưng.")
except FileNotFoundError:
    print("Lỗi: Không tìm thấy các file mô hình đã lưu. Vui lòng chạy lại giai đoạn huấn luyện.")
    exit()

# Hàm để phân tích một mẫu nước mới hoàn chỉnh
def analyze_new_water_sample_detailed(new_data: dict):
    # 1. Kiểm tra và sắp xếp dữ liệu đầu vào
    input_series = pd.Series(new_data, index=loaded_selected_features)
    input_df = pd.DataFrame([input_series])

    # 2. Dự đoán Potability (có thể uống được hay không)
    # Pipeline tự động thực hiện chuẩn hóa trước khi dự đoán
    prediction = loaded_clf_pipeline.predict(input_df)[0]
    prediction_proba = loaded_clf_pipeline.predict_proba(input_df)[0][1] # Xác suất là lớp 1

    potability_label = "Có thể uống được" if prediction == 1 else "Không thể uống được"

    # 3. Phát hiện bất thường
    # Phải chuẩn hóa dữ liệu đầu vào bằng scaler từ pipeline trước khi đưa vào anomaly_detector
    scaled_input_for_anomaly = loaded_scaler_from_pipeline.transform(input_df)
    
    anomaly_score = loaded_anomaly_detector.decision_function(scaled_input_for_anomaly)[0]
    anomaly_label = loaded_anomaly_detector.predict(scaled_input_for_anomaly)[0]

    is_anomaly = "Có" if anomaly_label == -1 else "Không"
    anomaly_threshold_explanation = f"(Điểm bất thường < {loaded_anomaly_detector.offset_:.4f} là bất thường)"

    # 4. Trả về kết quả chi tiết
    result = {
        "Dữ liệu đầu vào": new_data,
        "Dự đoán Potability": potability_label,
        "Xác suất Potability (là 'Có thể uống được')": f"{prediction_proba:.4f}",
        "Là bất thường": is_anomaly,
        "Điểm bất thường": f"{anomaly_score:.4f} {anomaly_threshold_explanation}",
        "Khuyến nghị": ""
    }

    # Đưa ra khuyến nghị dựa trên kết quả
    if is_anomaly == "Có":
        result["Khuyến nghị"] = "Cảnh báo: Dữ liệu này có vẻ bất thường so với dữ liệu lịch sử. Cần kiểm tra kỹ lưỡng!"
    elif potability_label == "Không thể uống được":
        result["Khuyến nghị"] = "Cảnh báo: Nước không an toàn để uống. Cần xử lý hoặc kiểm tra thêm."
    else:
        result["Khuyến nghị"] = "Nước có vẻ an toàn để uống."
        
    # Thêm gợi ý về các đặc trưng quan trọng nhất (từ mô hình)
    if loaded_classifier_from_pipeline is not None:
        top_features = pd.Series(loaded_classifier_from_pipeline.feature_importances_, index=loaded_selected_features).nlargest(3)
        result["Phân tích đặc trưng quan trọng"] = top_features.to_dict()

    return result

# =========================================================
# VÍ DỤ VỚI DỮ LIỆU THẬT/MỚI TỪ CẢM BIẾN
# =========================================================

print("\n=== DỰ ĐOÁN VỚI CÁC MẪU NƯỚC MỚI TỪ CẢM BIẾN ===")

# Mẫu nước 1: Ví dụ nước có vẻ tốt
sample_1 = {"ph": 7.2, "Turbidity": 2.8, "Solids": 25000}
result_1 = analyze_new_water_sample_detailed(sample_1)
print(f"\n--- Kết quả Phân tích Mẫu 1 (Nước tốt) ---")
for k, v in result_1.items():
    print(f"{k}: {v}")

# Mẫu nước 2: Ví dụ nước có vẻ không tốt (pH thấp, Turbidity cao, Solids cao)
sample_2 = {"ph": 4.5, "Turbidity": 8.5, "Solids": 45000}
result_2 = analyze_new_water_sample_detailed(sample_2)
print(f"\n--- Kết quả Phân tích Mẫu 2 (Nước không tốt) ---")
for k, v in result_2.items():
    print(f"{k}: {v}")

# Mẫu nước 3: Một mẫu có thể nằm ở ranh giới hoặc bất thường (pH rất cao)
sample_3 = {"ph": 11.0, "Turbidity": 3.5, "Solids": 28000}
result_3 = analyze_new_water_sample_detailed(sample_3)
print(f"\n--- Kết quả Phân tích Mẫu 3 (pH bất thường) ---")
for k, v in result_3.items():
    print(f"{k}: {v}")

# Mẫu nước 4: Một mẫu có Turbidity cực kỳ cao (có thể là bất thường)
sample_4 = {"ph": 7.0, "Turbidity": 15.0, "Solids": 20000}
result_4 = analyze_new_water_sample_detailed(sample_4)
print(f"\n--- Kết quả Phân tích Mẫu 4 (Turbidity bất thường) ---")
for k, v in result_4.items():
    print(f"{k}: {v}")

print("\n=== HOÀN THÀNH PHÂN TÍCH DỮ LIỆU MỚI ===")