"""
SAM-based food segmentation using MobileSAM.

Generates per-food binary masks within each compartment using
the Segment Anything architecture (lightweight MobileSAM variant).
"""

import time
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


def segment_full_image_sam(image_bgr: np.ndarray, ctx=None) -> list[dict]:
    """
    Segment all food items in the full plate image using a global SAM run
    combined with the 'foodness' heuristic.
    """
    debug = ctx is not None and ctx.debug
    t0 = time.perf_counter()

    generator = _load_sam_generator()
    if generator is None:
        results = _segment_color_fallback(image_bgr)
        if debug:
            _save_segmentation_debug(image_bgr, results, ctx, time.perf_counter() - t0,
                                     method="color_fallback")
        return results

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

    rejected_count = 0
    for data in masks_data:
        mask = data['segmentation']
        area = int(data['area'])
        img_area = h * w

        # Global size filters (ignore tiny noise or massive table-regions)
        if area < img_area * 0.002 or area > img_area * 0.4:
            rejected_count += 1
            continue

        # Foodness check: stainless steel is smooth (low var) and colorless (low sat)
        m_sat = np.mean(sat[mask])
        m_var = np.mean(laplacian[mask])

        # Plate: low sat, low edge density. Food: higher of either.
        # Thresh 12 for saturation, 15 for texture density
        if m_sat < 12 and m_var < 15:
            rejected_count += 1
            continue

        # Deduplication (ignore sub-masks of already tracked items)
        new_area = (mask & ~used_area).sum()
        if new_area < area * 0.25:
            rejected_count += 1
            continue

        used_area |= mask
        results.append({
            "mask": mask,
            "area": area,
            "score": float(data['stability_score']),
        })

    elapsed = time.perf_counter() - t0

    if debug:
        _save_segmentation_debug(image_bgr, results, ctx, elapsed,
                                 method="MobileSAM",
                                 total_candidates=len(masks_data),
                                 rejected=rejected_count)

    return results


def _save_segmentation_debug(
    image_bgr: np.ndarray,
    results: list[dict],
    ctx,
    elapsed: float,
    method: str = "unknown",
    total_candidates: int = 0,
    rejected: int = 0,
):
    """Save individual masks and a combined overlay for debugging."""
    h, w = image_bgr.shape[:2]

    # ── Save individual binary masks ─────────────────────────────────────
    for i, item in enumerate(results):
        mask_uint8 = (item["mask"].astype(np.uint8)) * 255
        idx = ctx.next_index("segmentation")
        ctx.save_image("segmentation", f"{idx:02d}_mask_item_{i+1}.png", mask_uint8)

    # ── Save combined overlay ────────────────────────────────────────────
    overlay = image_bgr.copy()
    # Generate distinct colors for each mask
    colors = [
        (66, 133, 244),   # blue
        (52, 168, 83),    # green
        (234, 67, 53),    # red
        (251, 188, 4),    # yellow
        (154, 78, 174),   # purple
        (0, 172, 193),    # teal
        (255, 112, 67),   # orange
        (121, 134, 203),  # indigo
    ]

    for i, item in enumerate(results):
        color = colors[i % len(colors)]
        mask_bool = item["mask"]
        # Semi-transparent color fill
        color_layer = np.zeros_like(overlay)
        color_layer[mask_bool] = color
        overlay = cv2.addWeighted(overlay, 1.0, color_layer, 0.4, 0)
        # Draw contour border
        mask_u8 = mask_bool.astype(np.uint8)
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, color, 2)
        # Label
        M = cv2.moments(mask_u8)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.putText(overlay, f"#{i+1} ({item['score']:.2f})",
                        (cx - 30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 2)

    idx = ctx.next_index("segmentation")
    fname = f"{idx:02d}_segmentation_overlay.png"
    ctx.save_image("segmentation", fname, overlay)

    ctx.log("Segmentation", f"{len(results)} food items segmented",
            {"method": method,
             "total_candidates": total_candidates,
             "rejected": rejected,
             "accepted": len(results)},
            elapsed=elapsed, output_file=fname)


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
