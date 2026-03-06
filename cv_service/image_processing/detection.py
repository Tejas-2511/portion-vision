import cv2
import numpy as np

def find_compartments(image: np.ndarray) -> list:
    """
    Find internal tray compartments using contour detection.
    Returns a list of (x, y, w, h) bounding boxes for each detected compartment.
    """
    # 1. Grayscale and Blur
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 2. Extract edges directly instead of adaptive thresholding which can be too noisy
    edges = cv2.Canny(blurred, 30, 100)

    # 3. Dilate edges to close gaps
    kernel = np.ones((5,5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # 4. Find Contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 5. Filter contours logically (must be of a certain size to be a real compartment)
    height, width = image.shape[:2]
    min_area = (width * height) * 0.02 # At least 2% of tray area
    
    compartments = []
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > min_area:
            x, y, w, h = cv2.boundingRect(cnt)
            # Ensure it's not simply the entire image border
            if w < width * 0.95 and h < height * 0.95:
                compartments.append((x, y, w, h))
                
    # Sort compartments generically from top-left to bottom-right
    compartments.sort(key=lambda b: b[1] * width + b[0])
    
    return compartments
