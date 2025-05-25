import cv2
from ultralytics import YOLO
from paddleocr import PaddleOCR
from datetime import datetime
import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

# === Kunci Statik ===
key_b64 = "kKgTWK1FuLFlHrxRX8xlE7e9IYvqqMaI8CyZGhmmu6c="
key = base64.b64decode(key_b64)

# === Fungsi Enkripsi ===
def encrypt_text(text: str, key: bytes) -> dict:
    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)
    ciphertext = chacha.encrypt(nonce, text.encode(), None)
    return {
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode()
    }

def encrypt_file_bytes(file_path: str, key: bytes, output_dir: str) -> dict:
    with open(file_path, "rb") as f:
        data = f.read()
    nonce = secrets.token_bytes(12)
    chacha = ChaCha20Poly1305(key)
    ciphertext = chacha.encrypt(nonce, data, None)

    enc_filename = os.path.basename(file_path) + ".enc"
    enc_path = os.path.join(output_dir, enc_filename)
    with open(enc_path, "wb") as ef:
        ef.write(ciphertext)

    return {
        "filename": os.path.basename(file_path),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext_file": enc_filename
    }

# === Setup Model YOLO dan PaddleOCR ===
model_path = "best.pt"
ocr = PaddleOCR(use_angle_cls=True, lang='en')
model = YOLO(model_path)

# === Kamera Aktif ===
cap = cv2.VideoCapture(0)
print("📸 Kamera aktif. Tekan 's' untuk simpan, 'q' untuk keluar.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Gagal akses kamera.")
        break

    cv2.imshow("Tekan 's' untuk simpan gambar | 'q' untuk keluar", frame)
    keypress = cv2.waitKey(1)

    if keypress == ord('q'):
        break
    elif keypress == ord('s'):
        # === Timestamp & Folder Output ===
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = os.path.join("output", timestamp)
        os.makedirs(output_folder, exist_ok=True)

        # === Simpan Gambar Mentah ===
        image_path = os.path.join(output_folder, f"capture_{timestamp}.jpg")
        cv2.imwrite(image_path, frame)
        print(f"📷 Gambar disimpan: {image_path}")

        # === Deteksi Plat Nomor ===
        results = model.predict(source=frame, conf=0.5)
        annotated = results[0].plot()
        log_entries = []
        image_entries = []

        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            label = results[0].names[cls_id]
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

                # === Jalankan OCR ===
                results_ocr = ocr.ocr(cropped_resized, cls=True)
                print(f"✅ Deteksi: {label} | Confidence: {confidence:.2f}%")
                if results_ocr:
                    ocr_lines = []
                    for line in results_ocr:
                        for box, (text, prob) in line:
                            ocr_lines.append(f"{text.strip()} ({prob:.2f})")
                            print(f"📄 OCR Hasil: {text.strip()} | Prob: {prob:.2f}")

                    # Gabungkan semua hasil OCR dan enkripsi dalam satu payload
                    full_ocr_text = " | ".join(ocr_lines)
                    payload = f"{datetime.now()} | OCR: {full_ocr_text}"
                    encrypted_text = encrypt_text(payload, key)
                    log_entries.append(encrypted_text)
                else:
                    print("❌ Tidak ada teks terdeteksi.")


                # === Simpan Gambar: Crop, Resize, Annotated ===
                crop_path = os.path.join(output_folder, f"crop_{timestamp}.jpg")
                resize_path = os.path.join(output_folder, f"resized_{timestamp}.jpg")
                annotated_path = os.path.join(output_folder, f"annotated_{timestamp}.jpg")

                cv2.imwrite(crop_path, cropped)
                cv2.imwrite(resize_path, cropped_resized)
                cv2.imwrite(annotated_path, annotated)

                # === Enkripsi Semua Gambar ===
                image_entries.append(encrypt_file_bytes(crop_path, key, output_folder))
                image_entries.append(encrypt_file_bytes(resize_path, key, output_folder))
                image_entries.append(encrypt_file_bytes(annotated_path, key, output_folder))

        # === Simpan Log Payload ===
        log_file = os.path.join(output_folder, f"log_payload_{timestamp}.txt")
        with open(log_file, "w") as f:
            f.write("==== Encrypted OCR Log ====\n")
            for entry in log_entries:
                f.write(f"Nonce: {entry['nonce']}\n")
                f.write(f"Ciphertext: {entry['ciphertext']}\n\n")
            f.write("==== Encrypted Image Files ====\n")
            for img in image_entries:
                f.write(f"File: {img['filename']}\n")
                f.write(f"Nonce: {img['nonce']}\n")
                f.write(f"Encrypted File: {img['ciphertext_file']}\n\n")

        print(f"📝 Semua file dan log disimpan dalam folder: {output_folder}")

cap.release()
cv2.destroyAllWindows()
