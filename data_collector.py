import json
import time
import pandas as pd
import paho.mqtt.client as mqtt

# --- CONFIGURATION ---
MQTT_BROKER = "10.97.48.151"
MQTT_PORT = 1883    
MQTT_TOPIC = "motor/sensors"

# รายการสภาวะ และชื่อไฟล์ปลายทาง
MODE_CONFIG = {
    1: {"name": "ทำงานปกติ (Normal)", "file": "data_normal.csv"},
    2: {"name": "ความร้อนสูง (High Temp)", "file": "data_temp_fault.csv"},
    3: {"name": "สั่นสะเทือนผิดปกติ (High Vib)", "file": "data_vib_fault.csv"},
    4: {"name": "รอบหมุน/แกนติดขัด (RPM Fault)", "file": "data_rpm_fault.csv"}
}

# ตัวแปรระดับ Global สำหรับเก็บข้อมูลชั่วคราว
collected_rows = []
target_samples = 300
selected_filename = ""

# ✅ [แก้ไข 1] รองรับ paho-mqtt v2.x (เปลี่ยน rc เป็น reason_code)
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"\n[MQTT] เชื่อมต่อสำเร็จ! กำลังเริ่มเก็บข้อมูลลงไฟล์: {selected_filename}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"[MQTT] เชื่อมต่อไม่สำเร็จ Reason Code: {reason_code}")

def on_message(client, userdata, msg):
    global collected_rows
    try:
        # 1. แปลง JSON จาก ESP32
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)

        # 2. ดึง 8 ค่าหลักที่นำไปใช้เทรน AI
        row = [
            data.get("timestamp", 0),
            float(data.get("rpm", 0)),
            float(data.get("temperature", 0)),
            float(data.get("vibration_x", 0)),
            float(data.get("vibration_y", 0)),
            float(data.get("vibration_z", 0)),
            float(data.get("current", 0)),
            float(data.get("pwm", 0))
        ]
        
        collected_rows.append(row)
        current_count = len(collected_rows)

        # ✅ [แก้ไข 2] ปรับ Index การแสดงผล Terminal ให้ตรงกับข้อมูล
        # row[0]=Timestamp, row[1]=RPM, row[2]=Temp, row[3]=VibX
        print(f"\r[Progress] เก็บข้อมูลแล้ว: {current_count}/{target_samples} ชุด "
              f"| RPM: {row[1]:.0f} | Temp: {row[2]:.1f}°C | VibX: {row[3]:.2f}", end="")

        # 4. เมื่อเก็บครบจำนวนที่ตั้งไว้ ให้เซฟลงไฟล์ CSV
        if current_count >= target_samples:
            print("\n\n[System] เก็บข้อมูลครบถ้วน! กำลังบันทึกไฟล์...")
            
            # ✅ [แก้ไข 3] เพิ่ม 'timestamp' ให้คอลัมน์ครบ 8 คอลัมน์ตรงกับข้อมูล
            columns = ['timestamp', 'rpm', 'temp', 'vx', 'vy', 'vz', 'current', 'pwm']
            df = pd.DataFrame(collected_rows, columns=columns)
            
            # เซฟไฟล์ CSV (ไม่เอา Index)
            df.to_csv(selected_filename, index=False)
            print(f"✅ บันทึกไฟล์สำเร็จ: {selected_filename} (จำนวน {len(df)} แถว)")
            
            # ตัดการเชื่อมต่อ MQTT เพื่อจบโปรแกรม
            client.disconnect()

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"\n[Error] {e}")

def main():
    global target_samples, selected_filename, collected_rows
    
    print("=========================================")
    print("   โปรแกรมเก็บข้อมูลมอเตอร์ (Data Collector)")
    print("=========================================")
    print("เลือกสภาวะของมอเตอร์ที่กำลังทดสอบอยู่:")
    print(" 1: ทำงานปกติ (Normal)")
    print(" 2: ความร้อนสูง (High Temp)")
    print(" 3: สั่นสะเทือนผิดปกติ (High Vib)")
    print(" 4: รอบหมุนผิดปกติ/แกนติดขัด (RPM Fault)")
    print("-----------------------------------------")

    try:
        choice = int(input("กรอกหมายเลข (1-4): "))
        if choice not in MODE_CONFIG:
            print("❌ ตัวเลือกไม่ถูกต้อง จบการทำงาน")
            return
    except ValueError:
        print("❌ ตัวเลขไม่ถูกต้อง จบการทำงาน")
        return

    try:
        samples_input = input("ต้องการเก็บกี่ชุดข้อมูล? (กด Enter เพื่อใช้ค่าเริ่มต้น 300): ")
        if samples_input.strip() != "":
            target_samples = int(samples_input)
    except ValueError:
        target_samples = 300

    selected_mode = MODE_CONFIG[choice]
    selected_filename = selected_mode["file"]
    collected_rows = []

    print(f"\n[Setup] สภาวะที่เลือก: {selected_mode['name']}")
    print(f"[Setup] ไฟล์ปลายทาง: {selected_filename}")
    print(f"[Setup] จำนวนข้อมูลที่ต้องเก็บ: {target_samples} ชุด (ประมาณ {target_samples / 10:.0f} วินาที)")
    print("[Setup] กำลังเชื่อมต่อ MQTT Broker...")

    # ✅ [แก้ไข 4] ระบุ CallbackAPIVersion.VERSION2 เพื่อรองรับ paho-mqtt 2.1.0
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[System] ผู้ใช้ยกเลิกการทำงาน")
    except Exception as e:
        print(f"\n[Error] ไม่สามารถเชื่อมต่อ Broker ได้: {e}")

if __name__ == "__main__":
    main()