import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.experimental import enable_iterative_imputer  
from sklearn.impute import IterativeImputer
import matplotlib.pyplot as plt
import seaborn as sns

try:
    df = pd.read_csv('water_potability.csv')
except FileNotFoundError:
    print("LỖI: Không tìm thấy file 'water_potability.csv'. Vui lòng tải và đặt vào cùng thư mục.")
    exit()

print("Đang xử lý các dữ liệu bị thiếu bằng IterativeImputer (tương tự MissForest)...")
imputer = IterativeImputer(random_state=42)
df_imputed = imputer.fit_transform(df)
df = pd.DataFrame(df_imputed, columns=df.columns)
print("=> Xử lý dữ liệu thiếu thành công!")

print("Đang tách dữ liệu thành tập đầu vào (X) và đầu ra (y)...")
X = df.drop('Potability', axis=1)
y = df['Potability']
print("=> Tách dữ liệu thành công!")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("Đang huấn luyện mô hình Random Forest...")
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
print("=> Huấn luyện mô hình hoàn tất!")

print("Đang lấy kết quả Feature Importance từ mô hình...")
importances = model.feature_importances_
feature_names = X.columns

feature_importance_df = pd.DataFrame({
    'Thong_so': feature_names,
    'Diem_quan_trong': importances
})

feature_importance_df = feature_importance_df.sort_values(by='Diem_quan_trong', ascending=False)

print("\n--- KẾT QUẢ PHÂN TÍCH CUỐI CÙNG ---")
print("Bảng xếp hạng mức độ quan trọng của các thông số:")
print(feature_importance_df.to_string(index=False))

print("\nĐang vẽ biểu đồ kết quả...")
plt.figure(figsize=(12, 8))
sns.barplot(x='Diem_quan_trong', y='Thong_so', data=feature_importance_df)
plt.title('Mức độ Quan trọng của các Thông số đến Chất lượng nước (Random Forest)', fontsize=16)
plt.xlabel('Điểm Quan trọng', fontsize=12)
plt.ylabel('Thông số', fontsize=12)
plt.tight_layout()
plt.show()

print("\n--- CHƯƠNG TRÌNH KẾT THÚC ---")
