import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path

# Load the YOLOv8n model once at import time
MODEL_PATH = Path(__file__).resolve().parents[2] / 'yolov8n.pt'
# If the model file is not present, Ultralytics will download it automatically when we instantiate the model
model = YOLO(str(MODEL_PATH))

def detect_image(image_bytes: bytes):
    """Run YOLOv8n on an image (provided as raw bytes) and return detections.
    Returns a list of dicts: {label, confidence, bbox: [x1, y1, x2, y2]}
    """
    # Convert bytes to a NumPy BGR image for OpenCV
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unable to decode image data")

    # Ultralytics expects RGB, so convert
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # Run inference – results is a list with one element for the single image
    results = model(img_rgb)
    detections = []
    for result in results:
        boxes = result.boxes
        for box in boxes:
            cls_id = int(box.cls[0]) if box.cls is not None else None
            label = result.names[cls_id] if cls_id is not None else "unknown"
            conf = float(box.conf[0]) if box.conf is not None else 0.0
            xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
            detections.append({
                "label": label,
                "confidence": round(conf, 4),
                "bbox": [round(coord, 2) for coord in xyxy]
            })
    return detections
