from PIL import Image
import numpy as np
# Create a 100x100 white image
arr = np.full((100, 100, 3), 255, dtype=np.uint8)
img = Image.fromarray(arr)
img.save('test_img.jpg', format='JPEG')
print('Created test_img.jpg, size:', img.size)
