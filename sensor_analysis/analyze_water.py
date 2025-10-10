import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    roc_auc_score, roc_curve, make_scorer, f1_score
)
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import time

# =========================================================
# 0. CẤU HÌNH VÀ THIẾT LẬP BAN ĐẦU
# =========================================================
RANDOM_STATE = 42
TEST_SIZE = 0.2
CONTAMINATION_RATE = 0.05

SELECTED_FEATURES = ["ph", "Turbidity", "Solids"]

print("=" * 70)
print("🚀 BẮT ĐẦU XÂY DỰNG MÔ HÌNH AI CHUẨN ĐOÁN CHẤT LƯỢNG NƯỚC")
print("=" * 70)

# =========================================================
# GIAI ĐOẠN 1: TIỀN XỬ LÝ DỮ LIỆU
# =========================================================

print("\n" + "=" * 70)
print("📊 GIAI ĐOẠN 1: TIỀN XỬ LÝ DỮ LIỆU")
print("=" * 70)

# 1. Đọc dataset
try:
    df = pd.read_csv("water_potability.csv")
    print(f"✅ Đã đọc dataset thành công!")
    print(f"   📏 Kích thước: {df.shape[0]} dòng x {df.shape[1]} cột")
    print(f"   📋 Các cột: {list(df.columns)}")
except FileNotFoundError:
    print("❌ Lỗi: Không tìm thấy file 'water_potability.csv'")
    exit()

# 2. Xử lý giá trị thiếu
print(f"\n🔍 Kiểm tra giá trị thiếu:")
missing_before = df[SELECTED_FEATURES].isnull().sum()
print(missing_before)

for col in SELECTED_FEATURES:
    if df[col].isnull().any():
        median_val = df[col].median()
        df[col].fillna(median_val, inplace=True)
        print(f"✅ Đã điền {col}: {missing_before[col]} giá trị thiếu bằng median = {median_val:.2f}")

print(f"\n📊 Kích thước sau xử lý: {df.shape}")

# Định nghĩa X và y
X = df[SELECTED_FEATURES]
y = df["Potability"]

print(f"\n📈 Thống kê phân bố nhãn:")
print(y.value_counts())
print(f"\n   Tỷ lệ: {y.value_counts(normalize=True).to_dict()}")

# 3. Chia tập dữ liệu
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
)

print(f"\n✂️  Đã chia dữ liệu:")
print(f"   🟦 Tập huấn luyện: {X_train.shape[0]} mẫu ({(1-TEST_SIZE)*100:.0f}%)")
print(f"   🟩 Tập kiểm tra: {X_test.shape[0]} mẫu ({TEST_SIZE*100:.0f}%)")
print(f"   ⚖️  Cân bằng train: Potability=1 chiếm {y_train.mean()*100:.1f}%")
print(f"   ⚖️  Cân bằng test: Potability=1 chiếm {y_test.mean()*100:.1f}%")

# =========================================================
# GIAI ĐOẠN 2: HUẤN LUYỆN VÀ TỐI ƯU HÓA MÔ HÌNH
# =========================================================

print("\n" + "=" * 70)
print("🤖 GIAI ĐOẠN 2: HUẤN LUYỆN VÀ TỐI ƯU HÓA MÔ HÌNH")
print("=" * 70)

# 4. Xây dựng Pipeline
clf_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('classifier', RandomForestClassifier(random_state=RANDOM_STATE, class_weight='balanced'))
])

print("\n🔧 Đã tạo Pipeline:")
print("   1️⃣  StandardScaler (chuẩn hóa dữ liệu)")
print("   2️⃣  RandomForestClassifier (phân loại)")

# 5. Tối ưu hóa siêu tham số
param_grid = {
    'classifier__n_estimators': [50, 100, 200],
    'classifier__max_depth': [None, 10, 20],
    'classifier__min_samples_leaf': [1, 2, 4]
}

print(f"\n⚙️  Cấu hình GridSearchCV:")
print(f"   🌳 Số lượng cây (n_estimators): {param_grid['classifier__n_estimators']}")
print(f"   📏 Độ sâu cây (max_depth): {param_grid['classifier__max_depth']}")
print(f"   🍃 Min samples/leaf: {param_grid['classifier__min_samples_leaf']}")
print(f"   📊 Tổng số kết hợp: {len(param_grid['classifier__n_estimators']) * len(param_grid['classifier__max_depth']) * len(param_grid['classifier__min_samples_leaf'])}")

scorer = make_scorer(f1_score, average='weighted')

grid_search = GridSearchCV(
    clf_pipeline,
    param_grid,
    cv=5,
    scoring=scorer,
    n_jobs=-1,
    verbose=2  # Tăng verbose để xem chi tiết hơn
)

print(f"\n🔄 Bắt đầu GridSearchCV (5-fold cross-validation)...")
print("   ⏳ Đang tìm kiếm siêu tham số tốt nhất...")
start_time = time.time()

grid_search.fit(X_train, y_train)

elapsed_time = time.time() - start_time
print(f"\n✅ Hoàn thành GridSearchCV trong {elapsed_time:.2f} giây!")

best_clf_model = grid_search.best_estimator_
print(f"\n🏆 KẾT QUẢ TỐI ƯU:")
print(f"   🎯 Siêu tham số tốt nhất:")
for param, value in grid_search.best_params_.items():
    print(f"      - {param.replace('classifier__', '')}: {value}")
print(f"   📊 F1-score (CV): {grid_search.best_score_:.4f}")

# 6. Đánh giá trên tập kiểm tra
print("\n" + "=" * 70)
print("📈 ĐÁNH GIÁ MÔ HÌNH TRÊN TẬP KIỂM TRA")
print("=" * 70)

y_pred = best_clf_model.predict(X_test)
y_pred_proba = best_clf_model.predict_proba(X_test)[:, 1]

accuracy = accuracy_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_pred_proba)

print(f"\n🎯 KẾT QUẢ TỔNG QUAN:")
print(f"   ✓ Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
print(f"   ✓ ROC AUC Score: {roc_auc:.4f}")

print(f"\n📊 Ma trận nhầm lẫn:")
cm = confusion_matrix(y_test, y_pred)
print(cm)

print(f"\n📋 Báo cáo chi tiết:")
print(classification_report(y_test, y_pred, target_names=["Không uống được", "Có thể uống được"]))

# 7. Feature Importance - SỬA LỖI: Tính toán TRƯỚC KHI vẽ
fitted_scaler = best_clf_model.named_steps['scaler']
fitted_classifier = best_clf_model.named_steps['classifier']

feature_importances = pd.Series(
    fitted_classifier.feature_importances_,
    index=SELECTED_FEATURES
).sort_values(ascending=False)

print(f"\n🔍 PHÂN TÍCH ĐẶC TRƯNG QUAN TRỌNG:")
for feature, importance in feature_importances.items():
    print(f"   {'█' * int(importance * 50)} {feature}: {importance:.4f}")

# =========================================================
# VẼ CÁC BIỂU ĐỒ
# =========================================================

print(f"\n📊 Đang tạo biểu đồ...")

# Confusion Matrix
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", 
            xticklabels=["Không uống được", "Có thể uống được"],
            yticklabels=["Không uống được", "Có thể uống được"])
plt.xlabel("Dự đoán")
plt.ylabel("Thực tế")
plt.title(f"Ma trận nhầm lẫn\nAccuracy: {accuracy:.2%}")
plt.tight_layout()
plt.savefig('confusion_matrix.png', dpi=300, bbox_inches='tight')
print("   ✅ Đã lưu: confusion_matrix.png")
plt.show()

# Feature Importance
plt.figure(figsize=(10, 6))
sns.barplot(x=feature_importances.values, y=feature_importances.index, palette="viridis")
plt.xlabel("Mức độ quan trọng")
plt.ylabel("Đặc trưng")
plt.title("Feature Importance của Random Forest")
for i, v in enumerate(feature_importances.values):
    plt.text(v + 0.01, i, f'{v:.3f}', va='center')
plt.tight_layout()
plt.savefig('feature_importance.png', dpi=300, bbox_inches='tight')
print("   ✅ Đã lưu: feature_importance.png")
plt.show()

# ROC Curve
fpr, tpr, thresholds = roc_curve(y_test, y_pred_proba)
plt.figure(figsize=(8, 6))
plt.plot(fpr, tpr, label=f'Random Forest (AUC = {roc_auc:.3f})', linewidth=2)
plt.plot([0, 1], [0, 1], 'k--', label='Ngẫu nhiên (AUC = 0.50)')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('Đường cong ROC')
plt.legend(loc='lower right')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('roc_curve.png', dpi=300, bbox_inches='tight')
print("   ✅ Đã lưu: roc_curve.png")
plt.show()

# Biểu đồ 4: Phân bố xác suất dự đoán (Probability Distribution)
plt.figure(figsize=(10, 6))
plt.hist(y_pred_proba[y_test == 0], bins=30, alpha=0.6, label='Không uống được (thực tế)', color='red', edgecolor='black')
plt.hist(y_pred_proba[y_test == 1], bins=30, alpha=0.6, label='Có thể uống được (thực tế)', color='green', edgecolor='black')
plt.axvline(x=0.5, color='black', linestyle='--', linewidth=2, label='Ngưỡng quyết định (0.5)')
plt.xlabel('Xác suất dự đoán "Có thể uống được"')
plt.ylabel('Số lượng mẫu')
plt.title('Phân bố xác suất dự đoán của mô hình')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('probability_distribution.png', dpi=300, bbox_inches='tight')
print("   ✅ Đã lưu: probability_distribution.png")
plt.show()

# Biểu đồ 5: Phân bố dữ liệu theo từng đặc trưng (Feature Distribution)
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
colors = ['#FF6B6B', '#4ECDC4']
for idx, feature in enumerate(SELECTED_FEATURES):
    ax = axes[idx]
    
    # Vẽ histogram cho 2 lớp
    ax.hist(X_test[y_test == 0][feature], bins=20, alpha=0.6, 
            label='Không uống được', color=colors[0], edgecolor='black')
    ax.hist(X_test[y_test == 1][feature], bins=20, alpha=0.6, 
            label='Có thể uống được', color=colors[1], edgecolor='black')
    
    ax.set_xlabel(feature, fontsize=12, fontweight='bold')
    ax.set_ylabel('Số lượng mẫu', fontsize=11)
    ax.set_title(f'Phân bố {feature}', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('feature_distribution.png', dpi=300, bbox_inches='tight')
print("   ✅ Đã lưu: feature_distribution.png")
plt.show()

# =========================================================
# GIAI ĐOẠN 3: MÔ HÌNH PHÁT HIỆN BẤT THƯỜNG
# =========================================================

print("\n" + "=" * 70)
print("🔍 GIAI ĐOẠN 3: HUẤN LUYỆN MÔ HÌNH PHÁT HIỆN BẤT THƯỜNG")
print("=" * 70)

anomaly_detector = IsolationForest(random_state=RANDOM_STATE, contamination=CONTAMINATION_RATE)
anomaly_detector.fit(fitted_scaler.transform(X_train))

print(f"✅ Đã huấn luyện Isolation Forest")
print(f"   📊 Contamination rate: {CONTAMINATION_RATE*100:.1f}%")

# =========================================================
# GIAI ĐOẠN 4: LƯU MÔ HÌNH
# =========================================================

print("\n" + "=" * 70)
print("💾 GIAI ĐOẠN 4: LƯU TRỮ MÔ HÌNH")
print("=" * 70)

joblib.dump(best_clf_model, 'clf_pipeline_potability.pkl')
joblib.dump(anomaly_detector, 'anomaly_detector_potability.pkl')
joblib.dump(SELECTED_FEATURES, 'selected_features.pkl')

print("✅ Đã lưu các file:")
print("   📁 clf_pipeline_potability.pkl")
print("   📁 anomaly_detector_potability.pkl")
print("   📁 selected_features.pkl")

# =========================================================
# GIAI ĐOẠN 5: DỰ ĐOÁN DỮ LIỆU MỚI
# =========================================================

print("\n" + "=" * 70)
print("🔮 GIAI ĐOẠN 5: DỰ ĐOÁN DỮ LIỆU MỚI")
print("=" * 70)

# Tải lại mô hình
loaded_clf_pipeline = joblib.load('clf_pipeline_potability.pkl')
loaded_anomaly_detector = joblib.load('anomaly_detector_potability.pkl')
loaded_selected_features = joblib.load('selected_features.pkl')
loaded_scaler_from_pipeline = loaded_clf_pipeline.named_steps['scaler']
loaded_classifier_from_pipeline = loaded_clf_pipeline.named_steps['classifier']

print("✅ Đã tải lại mô hình thành công")

def analyze_new_water_sample_detailed(new_data: dict):
    input_series = pd.Series(new_data, index=loaded_selected_features)
    input_df = pd.DataFrame([input_series])
    
    prediction = loaded_clf_pipeline.predict(input_df)[0]
    prediction_proba = loaded_clf_pipeline.predict_proba(input_df)[0][1]
    
    potability_label = "Có thể uống được" if prediction == 1 else "Không thể uống được"
    
    scaled_input_for_anomaly = loaded_scaler_from_pipeline.transform(input_df)
    anomaly_score = loaded_anomaly_detector.decision_function(scaled_input_for_anomaly)[0]
    anomaly_label = loaded_anomaly_detector.predict(scaled_input_for_anomaly)[0]
    
    is_anomaly = "Có" if anomaly_label == -1 else "Không"
    
    result = {
        "Dữ liệu đầu vào": new_data,
        "Dự đoán Potability": potability_label,
        "Xác suất": f"{prediction_proba:.4f} ({prediction_proba*100:.2f}%)",
        "Là bất thường": is_anomaly,
        "Điểm bất thường": f"{anomaly_score:.4f}",
        "Khuyến nghị": ""
    }
    
    if is_anomaly == "Có":
        result["Khuyến nghị"] = "⚠️  CẢNH BÁO: Dữ liệu bất thường! Cần kiểm tra kỹ lưỡng!"
    elif potability_label == "Không thể uống được":
        result["Khuyến nghị"] = "❌ KHÔNG AN TOÀN để uống. Cần xử lý."
    else:
        result["Khuyến nghị"] = "✅ Nước an toàn để uống."
    
    top_features = pd.Series(
        loaded_classifier_from_pipeline.feature_importances_, 
        index=loaded_selected_features
    ).nlargest(3)
    result["Đặc trưng quan trọng"] = top_features.to_dict()
    
    return result

# Các mẫu thử nghiệm
samples = [
    {"name": "Mẫu 1 (Nước tốt)", "data": {"ph": 7.2, "Turbidity": 2.8, "Solids": 25000}},
    {"name": "Mẫu 2 (Nước xấu)", "data": {"ph": 4.5, "Turbidity": 8.5, "Solids": 45000}},
    {"name": "Mẫu 3 (pH bất thường)", "data": {"ph": 11.0, "Turbidity": 3.5, "Solids": 28000}},
    {"name": "Mẫu 4 (Turbidity cao)", "data": {"ph": 7.0, "Turbidity": 15.0, "Solids": 20000}}
]

for sample in samples:
    print(f"\n{'=' * 70}")
    print(f"🧪 {sample['name']}")
    print(f"{'=' * 70}")
    result = analyze_new_water_sample_detailed(sample['data'])
    for k, v in result.items():
        if k == "Dữ liệu đầu vào":
            print(f"📥 {k}:")
            for key, val in v.items():
                print(f"      {key}: {val}")
        elif k == "Đặc trưng quan trọng":
            print(f"🔍 {k}:")
            for key, val in v.items():
                print(f"      {key}: {val:.4f}")
        else:
            print(f"   {k}: {v}")

print("\n" + "=" * 70)
print("✅ HOÀN THÀNH TẤT CẢ CÁC GIAI ĐOẠN")
print("=" * 70)