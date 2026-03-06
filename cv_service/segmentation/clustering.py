import cv2
import numpy as np
from sklearn.cluster import KMeans

def segment_food_kmeans(image_crop: np.ndarray, k: int = 3) -> float:
    """
    Segments the food from the background using K-Means clustering.
    Returns the fill ratio (food pixels / total pixels).
    """
    if image_crop.size == 0:
        return 0.0
        
    # 1. Reshape image to a 2D array of pixels
    pixels = image_crop.reshape((-1, 3))
    pixels = np.float32(pixels)
    
    # 2. Run KMeans clustering
    # Using sklearn for compliance.
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=5)
    labels = kmeans.fit_predict(pixels)
    
    # 3. Identify food vs tray background.
    # Heuristic: The background (tray) is likely the most common color (largest cluster).
    
    unique, counts = np.unique(labels, return_counts=True)
    largest_cluster_idx = unique[np.argmax(counts)]
    
    # Calculate mask of food (everything NOT the background cluster)
    food_pixels = 0
    total_pixels = len(labels)
    
    for cluster_id in unique:
        if cluster_id != largest_cluster_idx:
            food_pixels += counts[cluster_id]
            
    fill_ratio = food_pixels / total_pixels
    
    # Safety bounds
    fill_ratio = max(0.0, min(1.0, fill_ratio))
    
    return fill_ratio
