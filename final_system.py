# final_system.py

import cv2
import numpy as np
import easyocr
from ultralytics import YOLO
import csv
from datetime import datetime
import os
import django
import sys
from django.utils.timezone import make_aware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vehicle_dashboard.settings')
django.setup()
from django.core.mail import send_mail

reader = easyocr.Reader(['en'])
model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yolov8m.pt')
model = YOLO(model_path)

PIXELS_PER_METER = 20
FRAME_RATE = 30

def calculate_speed(track, fps=30):
    if len(track) < 2:
        return 0
    dist_pixels = np.linalg.norm(np.array(track[-1]) - np.array(track[0]))
    dist_meters = dist_pixels / PIXELS_PER_METER
    time_sec = len(track) / fps
    speed_kmph = (dist_meters / time_sec) * 3.6
    return speed_kmph

def extract_plate(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    results = reader.readtext(gray)
    for (bbox, text, prob) in results:
        text = text.upper().replace(' ', '')
        if len(text) >= 6 and any(c.isdigit() for c in text) and any(c.isalpha() for c in text):
            return text
    return "UNKNOWN"

def run_integrated_system(video_path, output_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    tracks = {}
    violations = []
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model.track(frame, persist=True, classes=[2, 3, 5, 7])
        if results and results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            ids = results[0].boxes.id.cpu().numpy().astype(int)

            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = map(int, box)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                if track_id not in tracks:
                    tracks[track_id] = []
                tracks[track_id].append((cx, cy))

                if len(tracks[track_id]) > 10:
                    tracks[track_id].pop(0)

                if len(tracks[track_id]) >= 5:
                    speed = calculate_speed(tracks[track_id], FRAME_RATE)
                    print(f"Track {track_id}: Estimated speed = {speed:.2f} km/h")
                    color = (0, 255, 0) if speed <= 10 else (0, 0, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, f"{speed:.1f} km/h", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    if speed > 10:
                        vehicle_img = frame[y1:y2, x1:x2]
                        plate = extract_plate(vehicle_img)
                        timestamp = make_aware(datetime.now())
                        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                        location = 'Highway A'
                        violations.append({
                            'TrackID': track_id,
                            'Timestamp': timestamp_str,
                            'Vehicle': 'Car',
                            'Speed (km/h)': round(speed, 2),
                            'License Plate': plate,
                            'Location': location
                        })
                        send_mail(
                            'Speed Violation Detected',
                            f'At {timestamp_str}, Vehicle {plate} detected speeding at {round(speed, 2)} km/h on {location}.',
                            'your_email@gmail.com',
                            ['recipient@example.com'],
                            fail_silently=True
                        )
        frame_count += 1
        if frame_count % 50 == 0:
            print(f"Processed {frame_count} frames...")

        out.write(frame)

    cap.release()
    out.release()

    if os.path.exists(output_path):
        print(f"Output video successfully saved at: {output_path}")
    else:
        print(f"Error: Output video file {output_path} not found!")

    with open('speed_violations.csv', 'w', newline='') as f:
        fieldnames = ['TrackID', 'Timestamp', 'Vehicle', 'Speed (km/h)', 'License Plate', 'Location']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(violations)

    print(f"\n✅ Done! {len(violations)} violations saved.")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        video_file = sys.argv[1]
        output_file = sys.argv[2]
        run_integrated_system(video_file, output_file)
    else:
        print("Usage: python final_system.py <input_video> <output_video>")
