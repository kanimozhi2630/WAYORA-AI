from app.services.detect import detect_image
from pathlib import Path
import logging, sys

image_path = Path('sample_people.jpg')
if not image_path.is_file():
    print('sample_people.jpg not found')
    sys.exit(1)
with open(image_path, 'rb') as f:
    data = f.read()
print('File size:', len(data))
print('First 8 bytes:', data[:8].hex())
# Run detection
try:
    dets = detect_image(data)
    print('Detections:', dets)
except Exception as e:
    print('Detection error:', e)
