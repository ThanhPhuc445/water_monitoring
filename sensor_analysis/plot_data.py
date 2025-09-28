import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector

# Kết nối MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="water_data"
)

# Đọc dữ liệu
query = "SELECT created_at, ph, ntu, tds FROM sensor ORDER BY created_at"
df = pd.read_sql(query, conn)
conn.close()

# Vẽ biểu đồ
plt.figure(figsize=(12,6))
plt.plot(df["created_at"], df["ph"], label="pH")
plt.plot(df["created_at"], df["ntu"], label="NTU")
plt.plot(df["created_at"], df["tds"], label="TDS")

plt.xlabel("Thời gian")
plt.ylabel("Giá trị")
plt.title("Biểu đồ dữ liệu cảm biến nước")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
