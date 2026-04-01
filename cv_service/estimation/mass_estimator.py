"""
End-to-end mass estimation pipeline.

Orchestrates: Detection → Scale → Depth → Segmentation → Volume → Mass
"""

import logging
import cv2
import numpy as np

from image_processing.preprocess import process_image
from image_processing.detection import (
    find_compartments,
    compute_scale,
    match_compartments_to_profile,
)
from segmentation.sam_segmenter import segment_full_image_sam
from depth.depth_estimator import estimate_depth, normalize_depth_to_plate, depth_to_cm
from config.density_map import get_density
from config.macro_map import get_macros

logger = logging.getLogger(__name__)


def estimate_food_mass(
    image_bgr: np.ndarray,
    expected_items: list[str] = None,
    plate_profile: str = None,
) -> dict:
    """
    Improved pipeline: full-image segmentation with per-pixel well mapping and macro estimation.
    """
    logger.info("Step 1: Preprocessing & Perspective Warp")
    top_down = process_image(image_bgr)
    img_h, img_w = top_down.shape[:2]

    logger.info("Step 2: Detecting compartments & Scale")
    raw_compartments = find_compartments(top_down)
    cm_per_pixel = compute_scale(raw_compartments, top_down.shape, plate_profile)
    pixel_area_cm2 = cm_per_pixel ** 2
    logger.info(f"Scale: {cm_per_pixel:.4f} cm/px")

    compartments = match_compartments_to_profile(raw_compartments, plate_profile)

    logger.info("Step 3: Depth Estimation")
    raw_depth = estimate_depth(top_down)

    # Build a rim/divider mask for baseline
    plate_mask = np.ones((img_h, img_w), dtype=bool)
    # Also build a per-pixel well depth map
    well_depth_map = np.zeros((img_h, img_w), dtype=np.float32)

    for comp in compartments:
        x, y, w, h = comp["bbox"]
        depth = comp.get("depth_cm", 2.0)
        plate_mask[y:y+h, x:x+w] = False

        if comp.get("contour") is not None:
            cv2.drawContours(well_depth_map, [comp["contour"]], -1, depth, -1)
        else:
            # Fallback to bbox if contour detection missed the exact shape
            well_depth_map[y:y+h, x:x+w] = depth

    height_relative = normalize_depth_to_plate(raw_depth, plate_mask)
    height_from_divider = depth_to_cm(height_relative, raw_depth, cm_per_pixel, img_w)

    logger.info("Step 4: Full-Plate Segmentation")
    food_masks = segment_full_image_sam(top_down)

    if not food_masks:
        logger.warning("No food items detected in the entire plate")
        return {"food_items": [], "confidence": 0.0}

    # Step 5: Assign food items to compartments & calculate volume
    food_items = []
    total_conf = 0.0

    for f_idx, item in enumerate(food_masks):
        mask = item["mask"]
        score = item["score"]
        total_conf += score

        # Calc volume using per-pixel well depth
        pixel_heights = height_from_divider[mask] + well_depth_map[mask]
        pixel_heights = np.clip(pixel_heights, 0.1, 10.0) # avoid impossible numbers
        
        volume_ml = np.sum(pixel_heights) * pixel_area_cm2

        # Identify which compartment this item belongs to (by majority area)
        best_label = "unknown"
        max_overlap = -1
        
        for comp in compartments:
            cx, cy, cw, ch = comp["bbox"]
            # Overlap in px
            overlap = np.sum(mask[cy:cy+ch, cx:cx+cw])
            if overlap > max_overlap:
                max_overlap = overlap
                best_label = comp["label"]
        
        # Override name if expected_items provided
        food_name = best_label
        if expected_items and f_idx < len(expected_items):
            food_name = expected_items[f_idx]

        density = get_density(food_name)
        mass_g = volume_ml * density

        # Calculate macros
        m = get_macros(food_name)
        calories = mass_g * m["calories"]
        protein = mass_g * m["protein"]
        carbs = mass_g * m["carbs"]
        fat = mass_g * m["fat"]

        food_items.append({
            "name": food_name,
            "volume_ml": round(float(volume_ml), 1),
            "mass_g": round(float(mass_g), 1),
            "calories": round(float(calories), 1),
            "protein": round(float(protein), 1),
            "carbs": round(float(carbs), 1),
            "fat": round(float(fat), 1),
            "confidence": round(score, 2)
        })

    avg_confidence = total_conf / len(food_masks)
    
    return {
        "food_items": food_items,
        "confidence": round(avg_confidence, 2),
    }
