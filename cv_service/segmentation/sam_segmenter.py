"""
SAM-based food segmentation using MobileSAM.

Generates per-food binary masks within each compartment using
the Segment Anything architecture (lightweight MobileSAM variant).
"""

import logging
import numpy as np
import cv2
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# ── Lazy-loaded global model singletons ──────────────────────────────────
_sam_model = None
_sam_predictor = None


def _load_sam():
    """Load MobileSAM model (downloads weights on first run)."""
    global _sam_model, _sam_predictor

    if _sam_predictor is not None:
        return _sam_predictor

    try:
        from mobile_sam import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor
        import urllib.request
        import os

        checkpoint_dir = os.path.join(os.path.dirname(__file__), "..", "weights")
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpoint_path = os.path.join(checkpoint_dir, "mobile_sam.pt")

        # Download weights if not present
        if not os.path.exists(checkpoint_path):
            url = "https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt"
            logger.info("Downloading MobileSAM weights...")
            urllib.request.urlretrieve(url, checkpoint_path)
            logger.info("MobileSAM weights downloaded.")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _sam_model = sam_model_registry["vit_t"](checkpoint=checkpoint_path)
        _sam_model.to(device)
        _sam_model.eval()
        _sam_predictor = SamPredictor(_sam_model)
        logger.info(f"MobileSAM loaded on {device}")

    except ImportError:
        logger.warning(
            "mobile_sam not installed — falling back to color-based segmentation. "
            "Install with: pip install mobile-sam"
        )
        _sam_predictor = None

    return _sam_predictor


def segment_compartment_sam(compartment_crop: np.ndarray) -> list[dict]:
    """
    Segment food items in a single compartment crop using MobileSAM.

    Returns a list of masks:
        [{"mask": np.ndarray (H, W bool), "area": int, "score": float}, ...]
    """
    predictor = _load_sam()

    if predictor is None:
        # Fallback: use color-based segmentation
        return _segment_color_fallback(compartment_crop)

    # MobileSAM expects RGB
    rgb = cv2.cvtColor(compartment_crop, cv2.COLOR_BGR2RGB)
    predictor.set_image(rgb)

    h, w = compartment_crop.shape[:2]

    # Use automatic grid-point prompts across the compartment
    # Generate a grid of points as prompts
    grid_points = []
    step_x, step_y = max(w // 5, 1), max(h // 5, 1)
    for y in range(step_y, h - step_y, step_y):
        for x in range(step_x, w - step_x, step_x):
            grid_points.append([x, y])

    if not grid_points:
        # Very small crop — use center point
        grid_points = [[w // 2, h // 2]]

    point_coords = np.array(grid_points)
    point_labels = np.ones(len(grid_points), dtype=np.int32)  # all foreground

    masks, scores, _ = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )

    # Filter and deduplicate masks
    results = []
    used_area = np.zeros((h, w), dtype=bool)

    # Sort by score descending
    order = np.argsort(-scores)
    for idx in order:
        mask = masks[idx].astype(bool)
        score = float(scores[idx])

        # Skip masks that are too small (< 1% of compartment) or too large (> 95%)
        area = int(mask.sum())
        comp_area = h * w
        if area < comp_area * 0.01 or area > comp_area * 0.95:
            continue

        # Skip if heavily overlapping with already-used area
        overlap = (mask & used_area).sum()
        if overlap > area * 0.5:
            continue

        used_area |= mask
        results.append({
            "mask": mask,
            "area": area,
            "score": score,
        })

    # If SAM produced nothing useful, fall back
    if not results:
        return _segment_color_fallback(compartment_crop)

    return results


def _segment_color_fallback(image_crop: np.ndarray) -> list[dict]:
    """
    Fallback segmentation using HSV color thresholding.
    Separates food (colorful) from plate/tray (typically silver/white/grey).
    Returns a single mask for the entire food region.
    """
    if image_crop.size == 0:
        return []

    hsv = cv2.cvtColor(image_crop, cv2.COLOR_BGR2HSV)
    h, w = image_crop.shape[:2]

    # Plate/tray is typically low-saturation (grey/silver/white)
    # Food tends to have higher saturation
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    # Threshold: food has saturation > 30 and not pure black
    food_mask = (sat > 30) & (val > 40)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    food_mask = cv2.morphologyEx(food_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=2)
    food_mask = cv2.morphologyEx(food_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    food_mask = food_mask.astype(bool)

    area = int(food_mask.sum())
    if area < (h * w) * 0.01:
        return []

    return [{
        "mask": food_mask,
        "area": area,
        "score": 0.6,  # lower confidence for fallback
    }]
