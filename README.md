⚙️ Motor Fault Monitoring (ระบบตรวจจับความผิดปกติของมอเตอร์แบบเรียลไทม์)

ระบบตรวจสอบสภาพมอเตอร์แบบเรียลไทม์ โดยรับข้อมูลเซนเซอร์จาก ESP32 ผ่าน MQTT แล้วใช้โมเดล Random Forest ทำนายสถานะของมอเตอร์ พร้อมแสดงผลผ่านเทอร์มินัลหรือแดชบอร์ดบนเว็บ

สถานะที่ตรวจจับได้
Label	สถานะ	ความหมาย
0	🟢 ทำงานปกติ (Normal)	มอเตอร์ทำงานปกติ
1	🔥 อุณหภูมิสูงผิดปกติ	ตรวจสอบการระบายความร้อน
2	⚠️ แรงสั่นสะเทือนสูงผิดปกติ	ตรวจสอบฐานและใบพัด
3	⚙️ แกนติดขัด / รอบหมุนตก	ตรวจสอบแกนและโหลด
ภาพรวมการทำงาน
ESP32 (เซนเซอร์มอเตอร์)
      │  JSON ผ่าน MQTT  (topic: motor/sensors)
      ▼
MQTT Broker (10.97.48.151:1883)
      │
      ├── data_collector.py ──► data_*.csv ──► train_model.py ──► motor_fault_model.pkl
      │
      └── app.py / dashboard.py / dashboard_fault_server.py
              └─► โหลด motor_fault_model.pkl ทำนายสถานะแบบเรียลไทม์
โครงสร้างไฟล์
ไฟล์	หน้าที่
data_collector.py	เก็บข้อมูลจาก MQTT แล้วบันทึกเป็น CSV แยกตามสภาวะ
train_model.py	รวม CSV, เทรน Random Forest, วัดความแม่นยำ และบันทึกเป็น motor_fault_model.pkl
app.py	โปรแกรมเทอร์มินัลแบบเบา แสดงสถานะและค่าเซนเซอร์ในบรรทัดเดียว
dashboard.py	แดชบอร์ด Streamlit แสดงสถานะ, ค่าปัจจุบัน และกราฟแนวโน้ม
dashboard_fault_server.py	แดชบอร์ด Flask + Socket.IO (พอร์ต 5001) พร้อมความน่าจะเป็นของแต่ละคลาสและการตั้งค่าอุณหภูมิเอง
dashboard_fault.html	หน้าเว็บที่ใช้คู่กับ dashboard_fault_server.py
temp_control_snippet.html	แผงควบคุมอุณหภูมิ (checkbox + slider) สำหรับวางในหน้าเว็บ
data_normal.csv, data_temp_fault.csv, data_vib_fault.csv, data_rpm_fault.csv	ชุดข้อมูลสำหรับเทรน
motor_fault_model.pkl	โมเดลที่เทรนแล้ว
ข้อมูลเซนเซอร์ (MQTT Payload)

ESP32 ต้องส่ง JSON ไปที่ topic motor/sensors ตามรูปแบบนี้:

json
{
  "timestamp": 123456,
  "rpm": 1500,
  "temperature": 42.5,
  "vibration_x": 0.12,
  "vibration_y": 0.10,
  "vibration_z": 0.98,
  "current": 1.25,
  "pwm": 180,
  "target_rpm": 1500
}
target_rpm เป็นค่าเสริม (ไม่บังคับ) ใช้แสดงผลในแดชบอร์ดแบบ Flask
หากขาดคีย์หลักตัวใดตัวหนึ่ง ข้อมูลชุดนั้นจะถูกข้ามและแสดงข้อความแจ้งเตือน

การแมปชื่อคีย์เป็นฟีเจอร์ของโมเดล

คีย์ใน MQTT	ฟีเจอร์
rpm	rpm
temperature	temp
vibration_x / _y / _z	vx / vy / vz
current	current
pwm	pwm

ลำดับฟีเจอร์ที่ใช้เทรนและทำนาย: ["rpm", "temp", "vx", "vy", "vz", "current", "pwm"]

การติดตั้ง

ต้องใช้ Python 3.9 ขึ้นไป

bash
pip install pandas scikit-learn joblib "paho-mqtt>=2.0" flask flask-socketio streamlit

โค้ดใช้ mqtt.CallbackAPIVersion.VERSION2 จึงต้องใช้ paho-mqtt เวอร์ชัน 2.x

การตั้งค่า

แก้ค่าด้านบนของแต่ละไฟล์ให้ตรงกับระบบของคุณ

python
MQTT_BROKER = "10.97.48.151"   # IP ของ MQTT Broker
MQTT_PORT   = 1883
MQTT_TOPIC  = "motor/sensors"

ค่านี้อยู่ในไฟล์ app.py, dashboard.py, dashboard_fault_server.py และ data_collector.py

วิธีใช้งาน
1) เก็บข้อมูลสำหรับเทรน
bash
python data_collector.py

เลือกสภาวะของมอเตอร์ที่กำลังทดสอบ แล้วระบุจำนวนตัวอย่าง (ค่าเริ่มต้น 300 ชุด ≈ 30 วินาที ที่ 10 ข้อมูล/วินาที)

เลือก	สภาวะ	ไฟล์ที่บันทึก
1	ทำงานปกติ	data_normal.csv
2	ความร้อนสูง	data_temp_fault.csv
3	สั่นสะเทือนผิดปกติ	data_vib_fault.csv
4	รอบหมุน/แกนติดขัด	data_rpm_fault.csv

รันซ้ำสำหรับทั้ง 4 สภาวะ ไฟล์ CSV มีคอลัมน์: timestamp, rpm, temp, vx, vy, vz, current, pwm

2) เทรนโมเดล
bash
python train_model.py

สคริปต์จะรวมข้อมูลทั้ง 4 ไฟล์ แบ่ง Train/Test 80/20 เทรน RandomForestClassifier (100 trees) แสดง Accuracy และ classification report แล้วบันทึกโมเดลเป็น motor_fault_model.pkl

3) รันระบบตรวจจับ

ตัวเลือก A – เทอร์มินัล

bash
python app.py

ตัวเลือก B – แดชบอร์ด Streamlit

bash
streamlit run dashboard.py

ตัวเลือก C – แดชบอร์ด Flask + Socket.IO (แนะนำ)

bash
python dashboard_fault_server.py

จากนั้นเปิด http://localhost:5001 (ไฟล์ dashboard_fault.html ต้องอยู่โฟลเดอร์เดียวกับเซิร์ฟเวอร์)

ตัวเลือกนี้มีความสามารถเพิ่มเติม:

แสดงความน่าจะเป็นของแต่ละสถานะ (predict_proba)
เก็บประวัติล่าสุด 120 รายการ
แสดงสถานะการเชื่อมต่อ MQTT
ตั้งค่าอุณหภูมิเอง (ดูหัวข้อถัดไป)
ฟีเจอร์ตั้งค่าอุณหภูมิเอง (กรณีเซนเซอร์เสีย)

ในแดชบอร์ด Flask สามารถเลือกให้โมเดลใช้อุณหภูมิที่ตั้งเองแทนค่าจากเซนเซอร์ได้

โหมด sensor – ใช้ค่าจาก ESP32 ตามปกติ
โหมด manual – ใช้ค่าจาก slider บนหน้าเว็บ (ช่วง 0–150 °C) แทนค่าเซนเซอร์

การตั้งค่าจะซิงก์ไปทุกหน้าที่เปิดอยู่ผ่าน Socket.IO และระบบยังเก็บค่าอุณหภูมิจริงจากเซนเซอร์ไว้แสดงเทียบ

ถ้าหน้าเว็บของคุณยังไม่มีแผงนี้ ให้นำโค้ดจาก temp_control_snippet.html ไปวางใน dashboard_fault.html (ตัวแปร socket ในสนิปเป็ตต้องตรงกับที่หน้าเดิมสร้างไว้ เช่น const socket = io();)

ข้อควรระวัง
ต้องใช้ motor_fault_model.pkl ที่เทรนด้วย scikit-learn เวอร์ชันใกล้เคียงกับที่ใช้รัน หากเวอร์ชันต่างกันมากอาจโหลดไม่ได้ ให้รัน train_model.py ใหม่
dashboard_fault_server.py ค้นหาโมเดลจากหลายตำแหน่ง (โฟลเดอร์เดียวกัน, โฟลเดอร์แม่, model/) และใช้ตัวแรกที่เจอ
Broker และเซิร์ฟเวอร์เปิดรับการเชื่อมต่อจากเครือข่ายภายใน (0.0.0.0) ควรใช้งานในเครือข่ายที่เชื่อถือได้
คุณภาพของโมเดลขึ้นกับข้อมูลที่เก็บ ควรเก็บข้อมูลแต่ละสภาวะให้หลากหลายและสมดุลกัน
