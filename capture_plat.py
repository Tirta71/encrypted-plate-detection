from ultralytics import YOLO
import cv2
import os
from datetime import datetime
import time

# Load model
model = YOLO("best.pt")

# Buka webcam
cap = cv2.VideoCapture(0)

# Folder penyimpanan
save_dir = "captures"
os.makedirs(save_dir, exist_ok=True)

# Waktu terakhir simpan
last_capture_time = 0
min_delay = 3  # detik (supaya tidak simpan berulang terlalu cepat)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Deteksi objek
    results = model.predict(source=frame, conf=0.5)
    annotated = results[0].plot()

    current_time = time.time()

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        label = results[0].names[cls_id]

        if label == "Plat Nomor":
            # Simpan hanya jika cukup waktu berlalu sejak capture terakhir
            if current_time - last_capture_time >= min_delay:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{save_dir}/plat_{timestamp}.jpg"
                cv2.imwrite(filename, frame)
                print(f"[✔] Plat Nomor terdeteksi dan disimpan: {filename}")
                last_capture_time = current_time
            break  # hanya 1 simpan per frame

    cv2.imshow("Deteksi Plat Nomor", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
