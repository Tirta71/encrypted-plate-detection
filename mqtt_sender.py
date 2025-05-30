import os
import cv2
import time
import json
import base64
import secrets
import certifi
import paho.mqtt.client as mqtt
from datetime import datetime
from ultralytics import YOLO
from paddleocr import PaddleOCR
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

# === Konfigurasi MQTT ===
MQTT_BROKER = "0fc5ab61ae91429d80cc08fc224eb005.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "tirta71"
MQTT_PASSWORD = "hero1234"
MQTT_TOPIC = "plat/ocr"
MQTT_INVALID_TOPIC = "plat/ocr/invalid"

# === Kunci Enkripsi ===
KEY_B64 = "kKgTWK1FuLFlHrxRX8xlE7e9IYvqqMaI8CyZGhmmu6c="
KEY = base64.b64decode(KEY_B64)

# === Global Payload Terakhir ===
last_sent_payload = None

def encrypt_text(text: str, key: bytes, simulate_invalid=False) -> dict:
    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)
    start = time.perf_counter()
    ciphertext_full = chacha.encrypt(nonce, text.encode(), None)
    encrypt_time = round((time.perf_counter() - start) * 1000, 3)
    ciphertext = ciphertext_full[:-16]
    tag = ciphertext_full[-16:]
    if simulate_invalid:
        tag = secrets.token_bytes(16)
    return {
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "poly1305_tag": base64.b64encode(tag).decode(),
        "encrypt_time_ms": encrypt_time
    }

def encrypt_file(file_path: str, key: bytes, output_dir: str, simulate_invalid=False) -> dict:
    with open(file_path, "rb") as f:
        data = f.read()
    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)
    start = time.perf_counter()
    ciphertext_full = chacha.encrypt(nonce, data, None)
    encrypt_time = round((time.perf_counter() - start) * 1000, 3)
    ciphertext = ciphertext_full[:-16]
    tag = ciphertext_full[-16:]
    if simulate_invalid:
        tag = secrets.token_bytes(16)
    enc_path = os.path.join(output_dir, os.path.basename(file_path) + ".enc")
    with open(enc_path, "wb") as ef:
        ef.write(ciphertext_full)
    return {
        "nama_file": os.path.basename(file_path),
        "ukuran_byte": len(data),
        "ukuran_terenkripsi": len(ciphertext_full),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "poly1305_tag": base64.b64encode(tag).decode(),
        "encrypt_time_ms": encrypt_time
    }

def kirim_ke_mqtt(payload: dict):
    global last_sent_payload
    last_sent_payload = payload
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
        print("\U0001F4E4 Payload berhasil dikirim ke MQTT.")
    except Exception as e:
        print(f"❌ Gagal kirim MQTT: {e}")

def on_message(client, userdata, msg):
    global last_sent_payload
    try:
        response = json.loads(msg.payload.decode())
        print("🔁 Respons INVALID diterima dari server:", response)
        if response.get("status") == "invalid" and last_sent_payload:
            resend_count = last_sent_payload.get("resend_count", 0)
            if resend_count < 3:
                last_sent_payload["resend_count"] = resend_count + 1
                print(f"🔁 Mengirim ulang payload (percobaan ke-{resend_count + 1})...")
                kirim_ke_mqtt(last_sent_payload)
            else:
                print("❌ Gagal kirim ulang. Sudah mencapai batas maksimal 3 kali.")
    except Exception as e:
        print(f"❌ Error parsing response: {e}")

def mulai_subscriber_mqtt():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(ca_certs=certifi.where())
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(MQTT_INVALID_TOPIC, qos=1)
        client.loop_start()
        print("📡 Subscriber MQTT aktif untuk menerima respons invalid.")
    except Exception as e:
        print(f"❌ Gagal konek MQTT subscriber: {e}")

ocr = PaddleOCR(use_angle_cls=True, lang='en')
model = YOLO("best.pt")
mulai_subscriber_mqtt()
cap = cv2.VideoCapture(0)
print("📷 Kamera aktif. Tekan 's' untuk capture & kirim. Tekan 'q' untuk keluar.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Kamera gagal dibaca.")
        break
    cv2.imshow("Tekan 's' untuk simpan & kirim | 'q' keluar", frame)
    keypress = cv2.waitKey(1)
    if keypress == ord('q'):
        break
    elif keypress == ord('s'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join("output", timestamp)
        os.makedirs(output_dir, exist_ok=True)
        image_path = os.path.join(output_dir, f"capture_{timestamp}.jpg")
        cv2.imwrite(image_path, frame)
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
                cv2.imwrite(crop_path, crop_resized)
                cv2.imwrite(os.path.join(output_dir, f"annotated_{timestamp}.jpg"), annotated)
                result_ocr = ocr.ocr(crop_resized, cls=True)
                if result_ocr:
                    texts = []
                    for line in result_ocr:
                        for box, (text, prob) in line:
                            texts.append(f"{text.strip()} ({prob:.2f})")
                            print(f"🔠 OCR: {text.strip()} | Prob: {prob:.2f}")
                    simulate_invalid_ocr = input("Simulasikan tag Poly1305 OCR tidak valid? (y/n): ").strip().lower() == 'y'
                    simulate_invalid_img = input("Simulasikan tag Poly1305 GAMBAR tidak valid? (y/n): ").strip().lower() == 'y'
                    ocr_text = " | ".join(texts)
                    ocr_encrypted = encrypt_text(ocr_text, KEY, simulate_invalid_ocr)
                    img_encrypted = encrypt_file(crop_path, KEY, output_dir, simulate_invalid_img)
                    payload = {
                        "timestamp": datetime.now().isoformat(),
                        "plat_nomor": texts[0].split()[0] if texts else "UNKNOWN",
                        "confidence": round(confidence, 2),
                        "device_id": 1,
                        "ocr": ocr_encrypted,
                        "gambar": img_encrypted
                    }
                    print(json.dumps(payload, indent=2))
                    kirim_ke_mqtt(payload)
                else:
                    print("⚠️ Tidak ada teks yang terdeteksi OCR.")

cap.release()
cv2.destroyAllWindows()
