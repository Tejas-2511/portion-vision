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
from segmentation.sam_segmenter import segment_compartment_sam
from depth.depth_estimator import estimate_depth, normalize_depth_to_plate, depth_to_cm
from volume.volume_calculator import compute_volume_with_cap
from config.density_map import get_density

logger = logging.getLogger(__name__)


def estimate_food_mass(
    image_bgr: np.ndarray,
    expected_items: list[str] = None,
    plate_profile: str = None,
    max_food_height_cm: float = 3.0,
) -> dict:
    """
    Full pipeline: image → food mass estimates.

    Args:
        image_bgr:          Raw BGR image of the plate.
        expected_items:     Optional list of food names for labeling.
        plate_profile:      Name of plate profile from config (or None for default).
        max_food_height_cm: Assumed max food height for depth scaling.

    Returns:
        {
            "food_items": [
                {"name": "dal", "volume_ml": 120.5, "mass_g": 126.5},
                ...
            ],
            "confidence": float,
        }
    """

    # ── Step 1: Preprocess (resize + perspective warp) ───────────────────
    logger.info("Step 1: Preprocessing image")
    top_down = process_image(image_bgr)

    # ── Step 2: Detect compartments & compute scale ──────────────────────
    logger.info("Step 2: Detecting compartments")
    raw_compartments = find_compartments(top_down)

    if not raw_compartments:
        # Fallback: treat entire image as a single compartment
        h, w = top_down.shape[:2]
        raw_compartments = [{
            "bbox": (0, 0, w, h),
            "contour": None,
            "area_px": w * h,
        }]
        logger.warning("No compartments detected — using full image as single section")

    cm_per_pixel = compute_scale(raw_compartments, top_down.shape, plate_profile)
    logger.info(f"Scale: {cm_per_pixel:.4f} cm/px")

    compartments = match_compartments_to_profile(raw_compartments, plate_profile)

    # ── Step 3: Depth estimation (full image) ────────────────────────────
    logger.info("Step 3: Running depth estimation")
    raw_depth = estimate_depth(top_down)

    # Build a rough plate mask (non-food regions) from all compartment borders
    plate_mask = np.ones(top_down.shape[:2], dtype=bool)
    for comp in compartments:
        x, y, w, h = comp["bbox"]
        plate_mask[y:y+h, x:x+w] = False  # compartment interiors are NOT plate surface

    height_relative = normalize_depth_to_plate(raw_depth, plate_mask)
    height_cm = depth_to_cm(height_relative, max_food_height_cm)

    # ── Step 4: Per-compartment segmentation + volume + mass ─────────────
    logger.info("Step 4: Segmenting and estimating per compartment")
    food_items = []
    total_confidence = 0.0

    for idx, comp in enumerate(compartments):
        x, y, w, h = comp["bbox"]
        label = comp.get("label", f"section_{idx + 1}")
        max_vol = comp.get("max_volume_ml", 300)
        comp_depth_cm = comp.get("depth_cm", 2.0)

        # Determine food name
        if expected_items and idx < len(expected_items):
            food_name = expected_items[idx]
        else:
            food_name = label

        # Crop compartment
        crop = top_down[y:y+h, x:x+w]
        if crop.size == 0:
            continue

        # Segment food within this compartment
        masks = segment_compartment_sam(crop)

        if not masks:
            logger.debug(f"Compartment {label}: no food detected")
            continue

        # Combine all food masks in this compartment
        combined_mask = np.zeros((h, w), dtype=bool)
        comp_confidence = 0.0

        for m in masks:
            combined_mask |= m["mask"]
            comp_confidence = max(comp_confidence, m["score"])

        total_confidence += comp_confidence

        # Extract the height map for this compartment
        comp_height_cm = height_cm[y:y+h, x:x+w]

        # Cap height to compartment physical depth
        comp_height_cm = np.clip(comp_height_cm, 0, comp_depth_cm)

        # Compute volume
        volume_ml = compute_volume_with_cap(
            combined_mask,
            comp_height_cm,
            cm_per_pixel,
            max_volume_ml=max_vol,
        )

        # Compute mass
        density = get_density(food_name)
        mass_g = volume_ml * density

        food_items.append({
            "name": food_name,
            "volume_ml": round(volume_ml, 1),
            "mass_g": round(mass_g, 1),
        })

    # Average confidence across compartments
    avg_confidence = (total_confidence / len(compartments)) if compartments else 0.5

    return {
        "food_items": food_items,
        "confidence": round(avg_confidence, 2),
    }
