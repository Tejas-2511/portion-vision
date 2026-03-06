import cv2
import numpy as np

def process_image(image: np.ndarray) -> np.ndarray:
    """
    Preprocess image and apply perspective warp to get top-down tray view.
    """
    # 1. Resize to a specific resolution for consistency
    target_size = 1024
    height, width = image.shape[:2]
    
    scale = target_size / max(height, width)
    resized = cv2.resize(image, (int(width * scale), int(height * scale)))
    
    # 2. Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(resized, (5, 5), 0)
    
    # 3. Detect tray boundaries using Canny edge
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return resized # Fallback if no contours
        
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Approximate contour to a polygon
    epsilon = 0.02 * cv2.arcLength(largest_contour, True)
    approx = cv2.approxPolyDP(largest_contour, epsilon, True)
    
    # If we found a rectangle (4 points), apply perspective transform
    if len(approx) == 4:
        warped = four_point_transform(resized, approx.reshape(4, 2))
        return warped
        
    # Fallback if 4 points not found: just return blurred/resized image
    return resized

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)] # Top-left
    rect[2] = pts[np.argmax(s)] # Bottom-right
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # Top-right
    rect[3] = pts[np.argmax(diff)] # Bottom-left
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
        
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped
