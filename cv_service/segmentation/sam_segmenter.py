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
_mask_generator = None


def _load_sam_generator():
    """Load MobileSAM model (downloads weights on first run)."""
    global _sam_model, _mask_generator

    if _mask_generator is not None:
        return _mask_generator

    try:
        from mobile_sam import sam_model_registry, SamAutomaticMaskGenerator
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
        
        _mask_generator = SamAutomaticMaskGenerator(
            model=_sam_model,
            points_per_side=16,
            pred_iou_thresh=0.86,
            stability_score_thresh=0.92,
            crop_n_layers=1,
            crop_n_points_downscale_factor=2,
            min_mask_region_area=100,
        )
        logger.info(f"MobileSAM Mask Generator loaded on {device}")

    except ImportError:
        logger.warning(
            "mobile_sam not installed — falling back to color-based segmentation. "
            "Install with: pip install mobile-sam"
        )
        _mask_generator = None

    return _mask_generator


def segment_full_image_sam(image_bgr: np.ndarray) -> list[dict]:
    """
    Segment all food items in the full plate image using a global SAM run
    combined with the 'foodness' heuristic.
    """
    generator = _load_sam_generator()
    if generator is None:
        return _segment_color_fallback(image_bgr)

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    
    # Run the generator to find all candidate objects
    masks_data = generator.generate(rgb)

    # Heuristics setup
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    # Edge density via Laplacian
    laplacian = np.abs(cv2.Laplacian(gray, cv2.CV_32F))
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]

    results = []
    h, w = image_bgr.shape[:2]
    used_area = np.zeros((h, w), dtype=bool)

    # Sort by confidence/stability
    masks_data.sort(key=lambda x: x['stability_score'], reverse=True)

    for data in masks_data:
        mask = data['segmentation']
        area = int(data['area'])
        img_area = h * w

        # Global size filters (ignore tiny noise or massive table-regions)
        if area < img_area * 0.002 or area > img_area * 0.4:
            continue

        # Foodness check: stainless steel is smooth (low var) and colorless (low sat)
        m_sat = np.mean(sat[mask])
        m_var = np.mean(laplacian[mask])

        # Plate: low sat, low edge density. Food: higher of either.
        # Thresh 12 for saturation, 15 for texture density
        if m_sat < 12 and m_var < 15:
            continue

        # Deduplication (ignore sub-masks of already tracked items)
        new_area = (mask & ~used_area).sum()
        if new_area < area * 0.25:
            continue

        used_area |= mask
        results.append({
            "mask": mask,
            "area": area,
            "score": float(data['stability_score']),
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
    food_mask = (hsv[:, :, 1] > 12) | (lap > 20)

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
