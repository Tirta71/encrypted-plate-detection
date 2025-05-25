import os
import cv2
import time
import json
import base64
import secrets
import certifi
import paho.mqtt.client as mqtt
from datetime import datetime
from tkinter import Tk, filedialog
from ultralytics import YOLO
from paddleocr import PaddleOCR
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

# === Konfigurasi MQTT ===
MQTT_BROKER = "0fc5ab61ae91429d80cc08fc224eb005.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "tirta71"
MQTT_PASSWORD = "hero1234"
MQTT_TOPIC = "plat/ocr"

# === Kunci Enkripsi ===
KEY_B64 = "kKgTWK1FuLFlHrxRX8xlE7e9IYvqqMaI8CyZGhmmu6c="
KEY = base64.b64decode(KEY_B64)

# === Enkripsi Teks ===
def encrypt_text(text: str, key: bytes) -> dict:
    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)
    start = time.perf_counter()
    ciphertext = chacha.encrypt(nonce, text.encode(), None)
    elapsed = round((time.perf_counter() - start) * 1000, 3)
    return {
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "encrypt_time_ms": elapsed,
        "poly1305_tag": base64.b64encode(ciphertext[-16:]).decode()
    }

# === Enkripsi File Gambar ===
def encrypt_file(file_path: str, key: bytes, output_dir: str) -> dict:
    with open(file_path, "rb") as f:
        data = f.read()
    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)
    start = time.perf_counter()
    ciphertext = chacha.encrypt(nonce, data, None)
    elapsed = round((time.perf_counter() - start) * 1000, 3)
    enc_path = os.path.join(output_dir, os.path.basename(file_path) + ".enc")
    with open(enc_path, "wb") as ef:
        ef.write(ciphertext)
    return {
        "nama_file": os.path.basename(file_path),
        "ukuran_byte": len(data),
        "ukuran_terenkripsi": len(ciphertext),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "encrypt_time_ms": elapsed,
        "poly1305_tag": base64.b64encode(ciphertext[-16:]).decode()
    }

# === Kirim MQTT ===
def kirim_ke_mqtt(payload: dict):
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(ca_certs=certifi.where())
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
        time.sleep(2)
        client.loop_stop()
        client.disconnect()
        print("📤 Payload berhasil dikirim ke MQTT.")
    except Exception as e:
        print(f"❌ Gagal kirim MQTT: {e}")

# === Simpan Log ke File ===
def simpan_log(payload: dict, output_dir: str):
    log_path = os.path.join(output_dir, "log_payload.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== LOG DETEKSI PLAT NOMOR ===\n")
        f.write(f"Waktu       : {payload['timestamp']}\n")
        f.write(f"Plat Nomor  : {payload['plat_nomor']}\n")
        f.write(f"Confidence  : {payload['confidence']}%\n")
        f.write(f"Device ID   : {payload['device_id']}\n\n")
        f.write("--- Enkripsi OCR ---\n")
        f.write(f"Nonce       : {payload['ocr']['nonce']}\n")
        f.write(f"Ciphertext  : {payload['ocr']['ciphertext']}\n")
        f.write(f"Encrypt Time: {payload['ocr']['encrypt_time_ms']} ms\n")
        f.write(f"Tag Poly1305: {payload['ocr']['poly1305_tag']}\n\n")
        f.write("--- Enkripsi Gambar ---\n")
        f.write(f"Nama File   : {payload['gambar']['nama_file']}\n")
        f.write(f"Ukuran Asli : {payload['gambar']['ukuran_byte']} bytes\n")
        f.write(f"Ukuran Enkr : {payload['gambar']['ukuran_terenkripsi']} bytes\n")
        f.write(f"Nonce       : {payload['gambar']['nonce']}\n")
        f.write(f"Ciphertext  : {payload['gambar']['ciphertext']}\n")
        f.write(f"Encrypt Time: {payload['gambar']['encrypt_time_ms']} ms\n")
        f.write(f"Tag Poly1305: {payload['gambar']['poly1305_tag']}\n\n")
        f.write("✅ Payload berhasil diproses dan dikirim ke MQTT.\n")


# === Load Model YOLO & OCR ===
model = YOLO("best.pt")
ocr = PaddleOCR(use_angle_cls=True, lang='en')

# === Pilih Gambar
Tk().withdraw()
image_path = filedialog.askopenfilename(
    title="Pilih gambar plat nomor",
    filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
)

if not image_path:
    print("❌ Tidak ada file dipilih.")
    exit()

frame = cv2.imread(image_path)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = os.path.join("output", timestamp)
os.makedirs(output_dir, exist_ok=True)

# === Deteksi Plat Nomor
results = model.predict(source=frame, conf=0.5)
annotated = results[0].plot()

for box in results[0].boxes:
    label = results[0].names[int(box.cls[0])]
    confidence = float(box.conf[0]) * 100

    if label.lower() == "plat nomor":
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        margin = 10
        x1, y1 = max(0, x1 - margin), max(0, y1 - margin)
        x2, y2 = min(frame.shape[1], x2 + margin), min(frame.shape[0], y2 + margin)
        crop = frame[y1:y2, x1:x2]
        crop_resized = cv2.resize(crop, (400, 130))

        crop_path = os.path.join(output_dir, f"crop_{timestamp}.jpg")
        annotated_path = os.path.join(output_dir, f"annotated_{timestamp}.jpg")
        cv2.imwrite(crop_path, crop_resized)
        cv2.imwrite(annotated_path, annotated)

        result_ocr = ocr.ocr(crop_resized, cls=True)
        if result_ocr:
            texts = []
            for line in result_ocr:
                for box, (text, prob) in line:
                    texts.append(f"{text.strip()} ({prob:.2f})")
                    print(f"📄 OCR: {text.strip()} | Prob: {prob:.2f}")

            ocr_text = " | ".join(texts)
            ocr_encrypted = encrypt_text(ocr_text, KEY)
            img_encrypted = encrypt_file(crop_path, KEY, output_dir)

            payload = {
                "timestamp": datetime.now().isoformat(),
                "plat_nomor": texts[0].split()[0] if texts else "UNKNOWN",
                "confidence": round(confidence, 2),
                "device_id": 1,
                "ocr": {
                    "nonce": ocr_encrypted["nonce"],
                    "ciphertext": ocr_encrypted["ciphertext"],
                    "encrypt_time_ms": ocr_encrypted["encrypt_time_ms"],
                    "poly1305_tag": ocr_encrypted["poly1305_tag"]
                },
                "gambar": img_encrypted
            }

            print(json.dumps(payload, indent=2))
            kirim_ke_mqtt(payload)
            simpan_log(payload, output_dir)
        else:
            print("❌ Tidak ada teks terdeteksi oleh OCR.")
