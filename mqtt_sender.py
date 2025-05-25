import hashlib  
import cv2
from ultralytics import YOLO
from paddleocr import PaddleOCR
from datetime import datetime
import os
import base64
import secrets
import json
import time
import paho.mqtt.client as mqtt
import certifi
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

# === MQTT Configuration ===
MQTT_BROKER = "0fc5ab61ae91429d80cc08fc224eb005.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "tirta71"
MQTT_PASSWORD = "hero1234"
MQTT_TOPIC = "plat/ocr"

# === MQTT Sender Function ===
def kirim_ke_mqtt(payload: dict):
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(ca_certs=certifi.where())

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
        time.sleep(2)  # Memberi waktu publish sebelum disconnect
        client.loop_stop()
        client.disconnect()
        print("📤 Payload berhasil dikirim ke topik MQTT.")
    except Exception as e:
        print(f"❌ Gagal menghubungkan ke MQTT: {e}")

# === Static Key ===
key_b64 = "kKgTWK1FuLFlHrxRX8xlE7e9IYvqqMaI8CyZGhmmu6c="
key = base64.b64decode(key_b64)

# === Encryption Functions ===
def encrypt_text(text: str, key: bytes) -> dict:
    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)

    start_time = time.perf_counter()
    ciphertext = chacha.encrypt(nonce, text.encode(), None)
    encrypt_time_ms = round((time.perf_counter() - start_time) * 1000, 3)

    poly1305_tag = ciphertext[-16:]
    return {
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "encrypt_time_ms": encrypt_time_ms,
        "poly1305_tag": base64.b64encode(poly1305_tag).decode()
    }


def encrypt_file_bytes(file_path: str, key: bytes, output_dir: str) -> dict:
    with open(file_path, "rb") as f:
        data = f.read()

    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)

    start_time = time.perf_counter()
    ciphertext = chacha.encrypt(nonce, data, None)
    encrypt_time_ms = round((time.perf_counter() - start_time) * 1000, 3)

    poly1305_tag = ciphertext[-16:]

    enc_filename = os.path.basename(file_path) + ".enc"
    enc_path = os.path.join(output_dir, enc_filename)
    with open(enc_path, "wb") as ef:
        ef.write(ciphertext)

    return {
        "filename": os.path.basename(file_path),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "size_plain": len(data),
        "size_encrypted": len(ciphertext),
        "encrypt_time_ms": encrypt_time_ms,
        "poly1305_tag": base64.b64encode(poly1305_tag).decode()
    }


# === Load YOLO Model & PaddleOCR ===
model_path = "best.pt"
ocr = PaddleOCR(use_angle_cls=True, lang='en')
model = YOLO(model_path)

# === Camera On ===
cap = cv2.VideoCapture(0)
print("📸 Kamera aktif. Tekan 's' untuk simpan & kirim, 'q' untuk keluar.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Gagal akses kamera.")
        break

    cv2.imshow("Tekan 's' untuk kirim ke MQTT | 'q' keluar", frame)
    keypress = cv2.waitKey(1)

    if keypress == ord('q'):
        break
    elif keypress == ord('s'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = os.path.join("output", timestamp)
        os.makedirs(output_folder, exist_ok=True)

        image_path = os.path.join(output_folder, f"capture_{timestamp}.jpg")
        cv2.imwrite(image_path, frame)

        results = model.predict(source=frame, conf=0.5)
        annotated = results[0].plot()

        for box in results[0].boxes:
            label = results[0].names[int(box.cls[0])]
            confidence = float(box.conf[0]) * 100

            if label.lower() == "plat nomor":
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                margin = 10
                x1 = max(0, x1 - margin)
                y1 = max(0, y1 - margin)
                x2 = min(frame.shape[1], x2 + margin)
                y2 = min(frame.shape[0], y2 + margin)
                cropped = frame[y1:y2, x1:x2]
                cropped_resized = cv2.resize(cropped, (400, 130))

                crop_path = os.path.join(output_folder, f"crop_{timestamp}.jpg")
                annotated_path = os.path.join(output_folder, f"annotated_{timestamp}.jpg")
                cv2.imwrite(crop_path, cropped)
                cv2.imwrite(annotated_path, annotated)

                results_ocr = ocr.ocr(cropped_resized, cls=True)
                if results_ocr:
                    texts = []
                    for line in results_ocr:
                        for box, (text, prob) in line:
                            texts.append(f"{text.strip()} ({prob:.2f})")
                            print(f"📄 OCR: {text.strip()} | Prob: {prob:.2f}")

                    ocr_text = " | ".join(texts)
                    ocr_encrypted = encrypt_text(ocr_text, key)
                    img_encrypted = encrypt_file_bytes(crop_path, key, output_folder)

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
                        "gambar": {
                            "nama_file": img_encrypted["filename"],
                            "ukuran_byte": img_encrypted["size_plain"],
                            "ukuran_terenkripsi": img_encrypted["size_encrypted"],
                            "nonce": img_encrypted["nonce"],
                            "ciphertext": img_encrypted["ciphertext"],
                            "encrypt_time_ms": img_encrypted["encrypt_time_ms"],
                            "poly1305_tag": img_encrypted["poly1305_tag"]
                        }
                    }


                    print(json.dumps(payload, indent=2))
                    kirim_ke_mqtt(payload)
                else:
                    print("❌ Tidak ada teks terdeteksi oleh OCR.")
cap.release()
cv2.destroyAllWindows()
