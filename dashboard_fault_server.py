import os
import json
import math
import time
from collections import deque

import joblib
import pandas as pd
import paho.mqtt.client as mqtt
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

# ============================================================
# CONFIG
# ============================================================
HERE = os.path.dirname(os.path.abspath(__file__))

# หาไฟล์โมเดลจากหลายที่ (ที่ไหนเจอก่อนใช้อันนั้น)
MODEL_CANDIDATES = [
    os.path.join(HERE, "motor_fault_model.pkl"),
    os.path.join(os.path.dirname(HERE), "motor_fault_model.pkl"),
    os.path.join(os.path.dirname(HERE), "model", "motor_fault_model.pkl"),
    "motor_fault_model.pkl",
]

MQTT_BROKER = "10.97.48.151"
MQTT_PORT = 1883
MQTT_TOPIC = "motor/sensors"

WEB_HOST = "0.0.0.0"
WEB_PORT = 5001  # คนละพอร์ตกับแดชบอร์ดแรก จะเปิดพร้อมกันได้

FEATURES = ["rpm", "temp", "vx", "vy", "vz", "current", "pwm"]

KEY_MAP = {
    "rpm": "rpm",
    "temperature": "temp",
    "vibration_x": "vx",
    "vibration_y": "vy",
    "vibration_z": "vz",
    "current": "current",
    "pwm": "pwm",
}

STATUS = {
    0: {"name": "ทำงานปกติ", "desc": "Normal", "color": "#1E8E5A"},
    1: {"name": "อุณหภูมิสูงผิดปกติ", "desc": "คำเตือน: ตรวจสอบการระบายความร้อน", "color": "#C8372D"},
    2: {"name": "แรงสั่นสะเทือนสูงผิดปกติ", "desc": "คำเตือน: ตรวจสอบฐานและใบพัด", "color": "#C98A0B"},
    3: {"name": "แกนติดขัด / รอบหมุนตก", "desc": "คำเตือน: ตรวจสอบแกนและโหลด", "color": "#6B4FBB"},
}

# ------------------------------------------------------------
# การตั้งค่าอุณหภูมิจากหน้าแดชบอร์ด
#   mode = "sensor" -> ใช้ค่าจาก ESP32 ตามเดิม
#   mode = "manual" -> ใช้ค่าที่เลือกบนหน้าเว็บแทนค่าเซนเซอร์
# ------------------------------------------------------------
TEMP_MIN = 0.0
TEMP_MAX = 150.0
temp_setting = {"mode": "sensor", "value": 40.0}

# ============================================================
# LOAD MODEL
# ============================================================
MODEL_PATH = next((p for p in MODEL_CANDIDATES if os.path.exists(p)), None)
if MODEL_PATH is None:
    raise SystemExit("ไม่พบ motor_fault_model.pkl ในตำแหน่งเหล่านี้:\n" + "\n".join(MODEL_CANDIDATES))

model = joblib.load(MODEL_PATH)
if hasattr(model, "n_jobs"):
    model.n_jobs = 1  # ทำนายทีละแถว ใช้ thread เดียวเร็วกว่า
HAS_PROBA = hasattr(model, "predict_proba")
print("Model:", MODEL_PATH, "|", type(model).__name__)

if hasattr(model, "classes_"):
    CLASS_IDS = [int(c) for c in model.classes_]
else:
    CLASS_IDS = sorted(STATUS)

CLASS_META = [
    {"id": c, **STATUS.get(c, {"name": f"Unknown ({c})", "desc": "", "color": "#8896A3"})}
    for c in CLASS_IDS
]

# ============================================================
# WEB SERVER
# ============================================================
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

history = deque(maxlen=120)
mqtt_state = {"connected": False}


@app.route("/")
def index():
    return send_from_directory(HERE, "dashboard_fault.html")


@socketio.on("connect")
def on_web_connect():
    emit(
        "init",
        {
            "classes": CLASS_META,
            "history": list(history),
            "mqtt": mqtt_state["connected"],
            "topic": MQTT_TOPIC,
            "broker": MQTT_BROKER,
            "temp_setting": temp_setting,
            "temp_range": {"min": TEMP_MIN, "max": TEMP_MAX},
        },
    )


@socketio.on("set_temp")
def on_set_temp(data):
    """รับค่าจากหน้าเว็บ: {"mode": "manual"|"sensor", "value": 55}"""
    data = data or {}

    mode = data.get("mode", "sensor")
    if mode not in ("sensor", "manual"):
        mode = "sensor"

    try:
        value = float(data.get("value", temp_setting["value"]))
        if math.isnan(value) or math.isinf(value):
            raise ValueError
    except (TypeError, ValueError):
        value = temp_setting["value"]

    value = max(TEMP_MIN, min(TEMP_MAX, value))

    temp_setting["mode"] = mode
    temp_setting["value"] = value

    print(f"Temperature setting: {mode} ({value:.1f} C)")

    # แจ้งทุกหน้าที่เปิดอยู่ให้ตรงกัน
    socketio.emit("temp_setting", temp_setting)


# ============================================================
# PREDICT
# ============================================================
def predict(data):
    missing = [k for k in KEY_MAP if k not in data]
    if missing:
        raise ValueError(f"ข้อมูลไม่ครบ ขาด {missing}")

    row = {KEY_MAP[k]: float(data[k]) for k in KEY_MAP}

    # เก็บค่าจริงจากเซนเซอร์ไว้ แล้วแทนด้วยค่าที่เลือกถ้าอยู่โหมด manual
    sensor_temp = row["temp"]
    if temp_setting["mode"] == "manual":
        row["temp"] = temp_setting["value"]

    X = pd.DataFrame([row], columns=FEATURES)

    pred = int(model.predict(X)[0])
    result = {
        "ts": time.time(),
        "values": row,
        "temp_source": temp_setting["mode"],
        "temp_sensor": sensor_temp,
        "target_rpm": float(data["target_rpm"]) if "target_rpm" in data else None,
        "pred": pred,
        "probs": None,
    }
    if HAS_PROBA:
        proba = model.predict_proba(X)[0]
        result["probs"] = {str(c): float(p) for c, p in zip(CLASS_IDS, proba)}
    return result


# ============================================================
# MQTT
# ============================================================
def on_connect(client, userdata, flags, reason_code, properties=None):
    ok = reason_code == 0
    mqtt_state["connected"] = ok
    if ok:
        client.subscribe(MQTT_TOPIC)
        print("MQTT connected, subscribed:", MQTT_TOPIC)
    socketio.emit("mqtt", {"connected": ok})


def on_disconnect(client, userdata, *args, **kwargs):
    mqtt_state["connected"] = False
    socketio.emit("mqtt", {"connected": False})


def on_message(client, userdata, msg):
    try:
        result = predict(json.loads(msg.payload.decode("utf-8")))
    except Exception as e:
        print("ERROR:", e)
        socketio.emit("error", {"message": str(e)})
        return
    history.append(result)
    socketio.emit("reading", result)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message
client.reconnect_delay_set(min_delay=1, max_delay=30)

if __name__ == "__main__":
    client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    print(f"เปิดแดชบอร์ดที่ http://localhost:{WEB_PORT}")
    socketio.run(app, host=WEB_HOST, port=WEB_PORT, allow_unsafe_werkzeug=True)