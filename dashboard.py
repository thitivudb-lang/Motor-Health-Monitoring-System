import json
import queue
import time
import joblib
import pandas as pd
import paho.mqtt.client as mqtt
import streamlit as st

# ==========================================
# ⚙️ ตั้งค่าระบบ (CONFIGURATIONS)
# ==========================================
MQTT_BROKER = "10.97.48.151"
MQTT_PORT = 1883
MQTT_TOPIC = "motor/sensors"
MODEL_PATH = "motor_fault_model.pkl"

STATUS_MAP = {
    0: "🟢 ทำงานปกติ (Normal)",
    1: "🔥 คำเตือน: อุณหภูมิสูงผิดปกติ!",
    2: "⚠️ คำเตือน: แรงสั่นสะเทือนสูงผิดปกติ!",
    3: "⚙️ คำเตือน: แกนติดขัด / รอบหมุนตก!",
}

st.set_page_config(
    page_title="Motor Health Dashboard",
    page_icon="⚙️",
    layout="wide"
)

# ------------------------------------------
# 1. โหลด โมเดล และ เริ่ม MQTT Client
# ------------------------------------------
@st.cache_resource
def load_model():
    try:
        return joblib.load(MODEL_PATH)
    except Exception as e:
        st.error(f"ไม่สามารถโหลดโมเดล '{MODEL_PATH}': {e}")
        return None

@st.cache_resource
def init_mqtt():
    data_queue = queue.Queue()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        ok = (reason_code == 0) or (getattr(reason_code, "value", 1) == 0)
        if ok:
            client.subscribe(MQTT_TOPIC)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            data_queue.put(payload)
        except Exception:
            pass

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        st.error(f"เชื่อมต่อ MQTT Broker ล้มเหลว: {e}")
        
    return data_queue

model = load_model()
msg_queue = init_mqtt()

# เก็บประวัติข้อมูล
if "history" not in st.session_state:
    st.session_state.history = pd.DataFrame(
        columns=["Time", "Status", "Temp", "VibX", "VibY", "VibZ", "RPM", "Current"]
    )

# ------------------------------------------
# 2. ส่วนแสดงผล UI บน Streamlit
# ------------------------------------------
st.title("⚙️ Real-time Motor Condition Monitoring")

# ดึงข้อมูลจาก Queue มาประมวลผล
while not msg_queue.empty():
    data = msg_queue.get()
    
    input_df = pd.DataFrame([{
        "rpm": float(data.get("rpm", 0)),
        "temp": float(data.get("temperature", 0)),
        "vx": float(data.get("vibration_x", 0)),
        "vy": float(data.get("vibration_y", 0)),
        "vz": float(data.get("vibration_z", 0)),
        "current": float(data.get("current", 0)),
        "pwm": float(data.get("pwm", 0)),
    }])

    prediction = model.predict(input_df)[0] if model else -1
    status_text = STATUS_MAP.get(prediction, f"Unknown ({prediction})")
    
    new_row = {
        "Time": time.strftime("%H:%M:%S"),
        "Status": status_text,
        "Temp": input_df["temp"][0],
        "VibX": input_df["vx"][0],
        "VibY": input_df["vy"][0],
        "VibZ": input_df["vz"][0],
        "RPM": input_df["rpm"][0],
        "Current": input_df["current"][0],
    }
    
    st.session_state.history = pd.concat(
        [st.session_state.history, pd.DataFrame([new_row])], 
        ignore_index=True
    ).tail(50)

# แสดงสถานะเมื่อยังไม่มีข้อมูล
if st.session_state.history.empty:
    st.info(f"⏳ กำลังเชื่อมต่อ MQTT Broker (`{MQTT_BROKER}`) และรอข้อมูลจาก Topic: `{MQTT_TOPIC}` ...")
else:
    latest = st.session_state.history.iloc[-1]
    
    # การแสดงผลสถานะ
    if "คำเตือน" in latest["Status"]:
        st.error(f"### สถานะล่าสุด: {latest['Status']}")
    else:
        st.success(f"### สถานะล่าสุด: {latest['Status']}")
        
    # การ์ดแสดงค่าปัจจุบัน
    cols = st.columns(5)
    cols[0].metric("Temperature", f"{latest['Temp']} °C")
    cols[1].metric("RPM", f"{latest['RPM']}")
    cols[2].metric("Current", f"{latest['Current']} A")
    cols[3].metric("Vibration X", f"{latest['VibX']}")
    cols[4].metric("Vibration Y", f"{latest['VibY']}")

    # กราฟแนวโน้ม
    st.subheader("📈 Real-time Trend Charts")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Temperature (°C)**")
        st.line_chart(st.session_state.history.set_index("Time")["Temp"])
    with c2:
        st.write("**Vibration (X / Y / Z)**")
        st.line_chart(st.session_state.history.set_index("Time")[["VibX", "VibY", "VibZ"]])

# รีเฟรชหน้าจอทุก 1 วินาที
time.sleep(1)
st.rerun()