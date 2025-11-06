import pandas as pd

df = pd.read_csv("water_potability.csv")
df_reduced = df[["ph", "Solids", "Turbidity", "Potability"]]
df_reduced.to_csv("water_potability_reduced.csv", index=False)

print("Kích thước dataset rút gọn:", df_reduced.shape)
