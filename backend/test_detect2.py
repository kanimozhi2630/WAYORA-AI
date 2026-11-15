import sys
from pathlib import Path
from app.services.detect import detect_image

image_path = Path('bus.jpg')
if not image_path.is_file():
    print('bus.jpg not found')
    sys.exit(1)

with open(image_path, 'rb') as f:
    data = f.read()
print('Read bytes:', len(data))
try:
    detections = detect_image(data)
    print('Detections:', detections)
except Exception as e:
    print('Error:', e)
