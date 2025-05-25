from ultralytics import YOLO
import cv2
import os
from datetime import datetime

# Load model hasil training
model = YOLO("best.pt")  # Ganti path ke model kamu

# Buka video
video_path = "test_video_plat.mp4"  # Ganti dengan nama file video kamu
cap = cv2.VideoCapture(video_path)

# Ambil properti video
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))
fps = cap.get(cv2.CAP_PROP_FPS)

# Siapkan folder penyimpanan dan output video
save_dir = "video_output"
os.makedirs(save_dir, exist_ok=True)

output_video = cv2.VideoWriter(
    f"{save_dir}/hasil_deteksi.mp4",
    cv2.VideoWriter_fourcc(*'mp4v'),
    fps,
    (frame_width, frame_height)
)

frame_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Deteksi setiap N frame (bisa diatur)
    frame_count += 1
    if frame_count % 2 == 0:  # percepat proses jika video panjang
        results = model.predict(source=frame, conf=0.5)
        annotated = results[0].plot()

        # Simpan video hasil deteksi
        output_video.write(annotated)

        # Tampilkan realtime (optional)
        cv2.imshow("Deteksi Video Plat", annotated)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
output_video.release()
cv2.destroyAllWindows()
