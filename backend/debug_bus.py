import cv2, numpy as np, sys
from pathlib import Path
from app.services.detect import detect_image

image_path = Path('bus.jpg')
if not image_path.is_file():
    print('bus.jpg not found')
    sys.exit(1)
with open(image_path, 'rb') as f:
    data = f.read()
print('File size:', len(data))
print('First 16 bytes:', data[:16].hex())
# OpenCV decode test
np_arr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
if img is None:
    print('OpenCV cannot decode')
else:
    print('OpenCV decoded shape:', img.shape)
# YOLO detection
try:
    dets = detect_image(data)
    print('Detections:', dets)
except Exception as e:
    print('Detection error:', e)
