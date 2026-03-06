import cv2
import numpy as np
from image_processing.detection import find_compartments

# Create a dummy image
img = np.zeros((800, 800, 3), dtype=np.uint8)
# Add some white rectangles as "compartments" inside a grey tray
cv2.rectangle(img, (50, 50), (350, 350), (200, 200, 200), -1)
cv2.rectangle(img, (400, 50), (750, 350), (200, 200, 200), -1)
cv2.rectangle(img, (50, 400), (750, 750), (200, 200, 200), -1)

# Add some noise
noise = np.random.randint(0, 50, (800, 800, 3), dtype=np.uint8)
img = cv2.add(img, noise)

print("Running dynamic compartment detection on synthetic test image...")
compartments = find_compartments(img)

print(f"Detected {len(compartments)} compartments.")
for idx, (x, y, w, h) in enumerate(compartments):
    print(f"Compartment {idx+1}: x={x}, y={y}, width={w}, height={h}")
