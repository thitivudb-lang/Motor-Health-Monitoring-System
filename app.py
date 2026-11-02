import json
import joblib
import pandas as pd
import paho.mqtt.client as mqtt

model = joblib.load("motor_fault_model.pkl")
FEATURES = ["rpm", "temp", "vx", "vy", "vz", "current", "pwm"]

# map ชื่อคีย์ใน MQTT -> ชื่อฟีเจอร์ที่ใช้เทรน
KEY_MAP = {
    "rpm": "rpm",
    "temperature": "temp",
    "vibration_x": "vx",
    "vibration_y": "vy",
    "vibration_z": "vz",
    "current": "current",
    "pwm": "pwm",
}

STATUS_MAP = {
    0: "🟢 ทำงานปกติ (Normal)",
    1: "🔥 คำเตือน: อุณหภูมิสูงผิดปกติ!",
    2: "⚠️ คำเตือน: แรงสั่นสะเทือนสูงผิดปกติ!",
    3: "⚙️ คำเตือน: แกนติดขัด / รอบหมุนตก!",
}

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("✅ เชื่อมต่อ MQTT สำเร็จ!\n")
        client.subscribe("motor/sensors")
    else:
        print(f"❌ เชื่อมต่อไม่สำเร็จ: {reason_code}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))

        missing = [k for k in KEY_MAP if k not in data]
        if missing:
            print(f"\n⚠️ ข้อมูลไม่ครบ ข้าม: ขาด {missing}")
            return

        row = {KEY_MAP[k]: float(data[k]) for k in KEY_MAP}
        X = pd.DataFrame([row], columns=FEATURES)  # บังคับลำดับคอลัมน์

        pred = int(model.predict(X)[0])
        status = STATUS_MAP.get(pred, f"Unknown ({pred})")

        line = (
            f"[Status]: {status} | RPM: {row['rpm']:.0f} | "
            f"Temp: {row['temp']:.1f}°C | "
            f"VibX: {row['vx']:.2f} | VibY: {row['vy']:.2f} | VibZ: {row['vz']:.2f} | "
            f"Current: {row['current']:.2f}A | PWM: {row['pwm']:.0f}"
        )
        print("\r\x1b[2K" + line, end="", flush=True)

    except Exception as e:
        print(f"\n❌ Error: {e}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.reconnect_delay_set(min_delay=1, max_delay=30)

client.connect("10.97.48.151", 1883, 60)
client.loop_forever(retry_first_connection=True)