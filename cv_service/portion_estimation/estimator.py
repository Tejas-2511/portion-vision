import numpy as np
from segmentation.clustering import segment_food_kmeans
from image_processing.detection import find_compartments

def estimate_portions(tray_image: np.ndarray, expected_items: list = None) -> dict:
    """
    Given a tray image, dynamically finds compartments, estimates fill ratio, and maps to items.
    """
    # 1. Dynamically find internal compartments
    compartments = find_compartments(tray_image)
    
    results = {}
    
    if not compartments:
        # Fallback to entire image if no compartments cleanly found
        compartments = [(0, 0, tray_image.shape[1], tray_image.shape[0])]
    
    # 2. Iterate through found bounding boxes
    for idx, (x, y, w, h) in enumerate(compartments):
        # We don't necessarily know what food this is. Assign a generic key or map to expected items.
        section_name = expected_items[idx] if expected_items and idx < len(expected_items) else f"compartment_{idx+1}"
        
        # Crop the compartment
        crop = tray_image[y:y+h, x:x+w]
        
        if crop.size == 0:
            results[section_name] = 0
            continue
            
        # Estimate fill ratio using k-means
        mini_crop = crop[::4, ::4] # Downsample by 4x for speed
        if mini_crop.size == 0:
            mini_crop = crop
            
        fill_ratio = segment_food_kmeans(mini_crop, k=3)
        
        # Calculate generic volume/grams. 
        # Standard assumption: max capacity scales roughly with compartment area relative to tray.
        tray_area = tray_image.shape[0] * tray_image.shape[1]
        comp_area = w * h
        area_ratio = comp_area / tray_area
        
        # Assume a standard average max tray capacity of 800g roughly split by area
        base_max_cap = 800 * area_ratio 
        
        portion_grams = fill_ratio * base_max_cap
        
        results[section_name] = int(round(portion_grams))
        
    return {
        "sections": results,
        "confidence": 0.85 # Mock confidence scoring
    }
