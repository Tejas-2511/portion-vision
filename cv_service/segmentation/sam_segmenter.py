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


def segment_full_image_sam(image_bgr: np.ndarray) -> list[dict]:
    """
    Segment all food items in the full plate image using a global SAM run
    combined with the 'foodness' heuristic.
    """
    predictor = _load_sam()
    if predictor is None:
        # For full-image fallback, we use the color/texture method directly
        return _segment_color_fallback(image_bgr)

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    predictor.set_image(rgb)

    h, w = image_bgr.shape[:2]

    # Generate a grid of points for the whole image (more points)
    grid_points = []
    step_x, step_y = max(w // 15, 1), max(h // 15, 1)
    for y in range(step_y, h, step_y):
        for x in range(step_x, w, step_x):
            grid_points.append([x, y])

    point_coords = np.array(grid_points)
    point_labels = np.ones(len(grid_points), dtype=np.int32)

    masks, scores, _ = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )

    # Heuristics setup
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_32F)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]

    results = []
    used_area = np.zeros((h, w), dtype=bool)

    order = np.argsort(-scores)
    for idx in order:
        mask = masks[idx].astype(bool)
        area = int(mask.sum())
        img_area = h * w

        # Global size filters
        if area < img_area * 0.001 or area > img_area * 0.5:
            continue

        # Foodness check
        m_sat = np.mean(sat[mask])
        m_var = np.var(laplacian[mask])

        # Plate: low sat, low var. Food: high sat OR high var.
        # Adjusted for global view: food is usually quite textured here.
        if m_sat < 12 and m_var < 300:
            continue

        # Deduplication
        new_area = (mask & ~used_area).sum()
        if new_area < area * 0.2:
            continue

        used_area |= mask
        results.append({
            "mask": mask,
            "area": area,
            "score": float(scores[idx]),
        })

    return results


def segment_compartment_sam(compartment_crop: np.ndarray) -> list[dict]:
    """
    Backwards compatibility: Just runs the full scan on the crop.
    """
    return segment_full_image_sam(compartment_crop)


def _segment_color_fallback(image_crop: np.ndarray) -> list[dict]:
    """
    Improved fallback using broader color/texture heuristic.
    """
    if image_crop.size == 0:
        return []

    hsv = cv2.cvtColor(image_crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F))

    # Saturation > 12 OR high texture
    food_mask = (hsv[:, :, 1] > 12) | (lap > 25)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    food_mask = cv2.morphologyEx(food_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=2)
    food_mask = cv2.morphologyEx(food_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    food_mask = food_mask.astype(bool)

    area = int(food_mask.sum())
    if area < (image_crop.shape[0] * image_crop.shape[1]) * 0.01:
        return []

    return [{
        "mask": food_mask,
        "area": area,
        "score": 0.5,
    }]
