import cv2, numpy as np, sys
from pathlib import Path

image_path = Path('zidane_real.jpg')
if not image_path.is_file():
    print('zidane_real.jpg not found')
    sys.exit(1)
size = image_path.stat().st_size
print('File size (bytes):', size)
if size <= 10*1024:
    print('Warning: file smaller than 10KB')
with open(image_path, 'rb') as f:
    data = f.read()
print('First 3 bytes (hex):', data[:3].hex())
# OpenCV decode
np_arr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
if img is None:
    print('OpenCV failed to decode')
else:
    print('OpenCV decode OK, shape:', img.shape)
# Run detection
from app.services.detect import detect_image
try:
    dets = detect_image(data)
    print('Detections:', dets)
except Exception as e:
    print('Detection error:', e)
