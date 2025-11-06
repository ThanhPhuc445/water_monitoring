# train_ai_from_esp32.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import os

print("🚀 HUẤN LUYỆN AI TỪ DỮ LIỆU ESP32 THỰC TẾ...")

# Đọc dữ liệu từ file CSV
df = pd.read_csv('sensor_analysis/logs/esp32_measurements.csv')
print(f"📊 Tổng số mẫu: {len(df)}")
print(f"📈 Phân phối nhãn:\n{df['label'].value_counts()}")

# Kiểm tra dữ liệu
print("\n🔍 Thống kê dữ liệu:")
print(df.describe())

# Kiểm tra giá trị thiếu
print(f"\n❓ Giá trị thiếu:\n{df.isnull().sum()}")

# Chuẩn bị features và target
X = df[['ph', 'tds', 'ntu']]
y = df['label']

print(f"\n🎯 Features: {X.columns.tolist()}")
print(f"🎯 Target: label (0=Bẩn, 1=Sạch)")

# Chia tập train/test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\n📚 Kích thước tập dữ liệu:")
print(f"  - Train: {X_train.shape}")
print(f"  - Test:  {X_test.shape}")

# Huấn luyện Random Forest
print("\n🤖 Đang huấn luyện Random Forest...")
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42
)

model.fit(X_train, y_train)

# Đánh giá model
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"\n✅ KẾT QUẢ HUẤN LUYỆN:")
print(f"  - Độ chính xác: {accuracy:.4f}")

# Cross-validation
cv_scores = cross_val_score(model, X, y, cv=5)
print(f"  - Cross-validation: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

# Classification report
print(f"\n📊 Báo cáo phân loại:")
print(classification_report(y_test, y_pred, target_names=['Bẩn', 'Sạch']))

# Feature importance
feature_importance = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print(f"\n🎯 Mức độ quan trọng của features:")
print(feature_importance)

# Lưu model
os.makedirs('models', exist_ok=True)
model_path = 'models/water_quality_model.pkl'
joblib.dump(model, model_path)

# Lưu features
features_path = 'models/water_quality_features.pkl'
joblib.dump(X.columns.tolist(), features_path)

print(f"\n💾 Đã lưu model: {model_path}")
print(f"💾 Đã lưu features: {features_path}")

# SỬA LẠI PHẦN VẼ BIỂU ĐỒ
fig, axes = plt.subplots(2, 2, figsize=(15, 12))

# 1. Confusion Matrix
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[0,0],
            xticklabels=['Bẩn', 'Sạch'], yticklabels=['Bẩn', 'Sạch'])
axes[0,0].set_title('Confusion Matrix')
axes[0,0].set_xlabel('Dự đoán')
axes[0,0].set_ylabel('Thực tế')

# 2. Feature Importance
sns.barplot(x='importance', y='feature', data=feature_importance, ax=axes[0,1])
axes[0,1].set_title('Mức độ quan trọng của Features')

# 3. Phân phối pH theo nhãn
colors = ['red', 'green']
for label in [0, 1]:
    data = df[df['label'] == label]['ph']
    axes[1,0].hist(data, alpha=0.7, label=f'Label {label}', 
                   color=colors[label], bins=20)
axes[1,0].set_title('Phân phối pH theo nhãn')
axes[1,0].legend()
axes[1,0].set_xlabel('pH')

# 4. Phân phối TDS theo nhãn
for label in [0, 1]:
    data = df[df['label'] == label]['tds']
    axes[1,1].hist(data, alpha=0.7, label=f'Label {label}', 
                   color=colors[label], bins=20)
axes[1,1].set_title('Phân phối TDS theo nhãn')
axes[1,1].legend()
axes[1,1].set_xlabel('TDS (ppm)')

plt.tight_layout()
plt.savefig('models/training_results.png', dpi=300, bbox_inches='tight')
plt.show()

# Tạo thêm biểu đồ cho NTU (biểu đồ riêng)
plt.figure(figsize=(10, 6))
for label in [0, 1]:
    data = df[df['label'] == label]['ntu']
    plt.hist(data, alpha=0.7, label=f'Label {label}', 
             color=colors[label], bins=20)
plt.title('Phân phối NTU theo nhãn')
plt.legend()
plt.xlabel('NTU')
plt.ylabel('Số lượng')
plt.tight_layout()
plt.savefig('models/ntu_distribution.png', dpi=300, bbox_inches='tight')
plt.show()

# Test với một số mẫu từ dữ liệu thực
print("\n🔬 KIỂM THỬ VỚI DỮ LIỆU THỰC:")
test_samples = [
    [2.27, 1431, 3.17],  # Bẩn (từ dữ liệu thực)
    [7.45, 130, 0.31],   # Sạch (từ dữ liệu thực)
    [4.13, 1148, 0.76],  # Bẩn
    [7.16, 120, 0.22],   # Sạch
]

for i, sample in enumerate(test_samples):
    prediction = model.predict([sample])[0]
    probability = model.predict_proba([sample])[0]
    
    status = "SẠCH" if prediction == 1 else "BẨN"
    confidence = probability[prediction] * 100
    
    print(f"Mẫu {i+1}: pH={sample[0]}, TDS={sample[1]}, NTU={sample[2]}")
    print(f"  → {status} (độ tin cậy: {confidence:.1f}%)")
    print(f"  → Xác suất: Sạch={probability[1]*100:.1f}%, Bẩn={probability[0]*100:.1f}%")
    print()

print("🎉 HUẤN LUYỆN HOÀN TẤT! AI ĐÃ SẴN SÀNG PHÂN TÍCH.")

# Hiển thị thông tin model
print(f"\n📋 THÔNG TIN MODEL:")
print(f"  - Số cây: {model.n_estimators}")
print(f"  - Độ sâu tối đa: {model.max_depth}")
print(f"  - Số features: {model.n_features_in_}")
print(f"  - Classes: {model.classes_}")

# Kiểm tra model có thể load lại được không
try:
    loaded_model = joblib.load(model_path)
    loaded_features = joblib.load(features_path)
    print(f"✅ Model đã được lưu và load lại thành công!")
    print(f"✅ Features: {loaded_features}")
except Exception as e:
    print(f"❌ Lỗi khi load model: {e}")