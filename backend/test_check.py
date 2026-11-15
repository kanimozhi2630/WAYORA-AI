import cv2, numpy as np, sys
from pathlib import Path
from app.services.detect import detect_image

image_path = Path('test_img.jpg')
if not image_path.is_file():
    print('test_img.jpg not found')
    sys.exit(1)

with open(image_path, 'rb') as f:
    data = f.read()
print('File size (bytes):', len(data))
# try decoding with OpenCV
np_arr = np.frombuffer(data, np.uint8)
img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
if img is None:
    print('OpenCV failed to decode image')
    sys.exit(1)
print('OpenCV decode OK, shape:', img.shape)
# run detection
try:
    dets = detect_image(data)
    print('Detections:', dets)
except Exception as e:
    print('Detection error:', e)
