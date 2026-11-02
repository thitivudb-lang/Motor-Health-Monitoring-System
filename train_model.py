import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

# 1. โหลดข้อมูลและใส่ Label (เฉลี่ยคำตอบให้ AI)
# 0 = Normal, 1 = Temp Fault, 2 = Vib Fault, 3 = RPM Fault
df_normal = pd.read_csv("data_normal.csv")
df_normal['target'] = 0

df_temp = pd.read_csv("data_temp_fault.csv")
df_temp['target'] = 1

df_vib = pd.read_csv("data_vib_fault.csv")
df_vib['target'] = 2

df_rpm = pd.read_csv("data_rpm_fault.csv")
df_rpm['target'] = 3

# 2. รวมข้อมูลทั้งหมด
data = pd.concat([df_normal, df_temp, df_vib, df_rpm], ignore_index=True)

# 3. แยก Features (X) และ Label (y)
features = ['rpm', 'temp', 'vx', 'vy', 'vz', 'current', 'pwm']
X = data[features]
y = data['target']

# 4. แบ่งข้อมูลสำหรับ Train 80% และ Test 20%
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 5. เทรนโมเดล AI
print("🤖 กำลังเทรนโมเดล AI...")
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# 6. วัดผลความแม่นยำ
y_pred = model.predict(X_test)
print(f"✅ ความแม่นยำ (Accuracy): {accuracy_score(y_test, y_pred) * 100:.2f}%\n")
print(classification_report(y_test, y_pred))

# 7. บันทึกโมเดลไว้ใช้งานจริง
joblib.dump(model, "motor_fault_model.pkl")
print("💾 บันทึกโมเดลสำเร็จเป็นไฟล์ 'motor_fault_model.pkl'")