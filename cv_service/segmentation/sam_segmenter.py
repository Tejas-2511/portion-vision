"""
SAM-based food segmentation using Full Segment Anything Model (SAM).

Enhancements over baseline:
  • #8  Per-compartment segmentation — SAM is optionally run inside each
        detected compartment region, then masks are stitched back to full-
        image coordinates. This avoids false positives from table/tray edges
        and is faster than running the full-image generator.

The original segment_full_image_sam() is kept intact as a fallback.
"""

from __future__ import annotations

import time
import logging
import numpy as np
import cv2
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# ── Lazy-loaded global model singletons ──────────────────────────────────────
_sam_model       = None
_mask_generator  = None
_sam_predictor   = None   # SamPredictor instance used for per-compartment mode


def _load_sam_generator():
    """Load Full SAM automatic mask generator (downloads weights on first run)."""
    global _sam_model, _mask_generator

    if _mask_generator is not None:
        return _mask_generator

    try:
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
        import urllib.request
        import os

        checkpoint_dir  = os.path.join(os.path.dirname(__file__), "..", "weights")
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpoint_path = os.path.join(checkpoint_dir, "sam_vit_h_4b8939.pth")

        if not os.path.exists(checkpoint_path):
            url = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
            logger.info("Downloading Full SAM (vit_h) weights...")
            urllib.request.urlretrieve(url, checkpoint_path)
            logger.info("Full SAM weights downloaded.")

        device      = "cuda" if torch.cuda.is_available() else "cpu"
        _sam_model  = sam_model_registry["vit_h"](checkpoint=checkpoint_path)
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
        logger.info(f"Full SAM Mask Generator loaded on {device}")

    except ImportError:
        logger.warning(
            "segment_anything not installed — falling back to color-based segmentation. "
            "Install with: pip install git+https://github.com/facebookresearch/segment-anything.git"
        )
        _mask_generator = None

    return _mask_generator


def _load_sam_predictor():
    """Load Full SAM SamPredictor used for per-compartment prompting."""
    global _sam_predictor

    if _sam_predictor is not None:
        return _sam_predictor

    # Ensure the base model is already loaded
    generator = _load_sam_generator()
    if generator is None or _sam_model is None:
        return None

    try:
        from segment_anything import SamPredictor
        _sam_predictor = SamPredictor(_sam_model)
        logger.info("Full SAM SamPredictor loaded")
    except Exception as exc:
        logger.warning(f"Could not load SamPredictor: {exc}")
        _sam_predictor = None

    return _sam_predictor


# ── Public API ────────────────────────────────────────────────────────────────

def segment_full_image_sam(image_bgr: np.ndarray, ctx=None) -> list[dict]:
    """
    Segment all food items in the full plate image (original baseline method).

    Uses the automatic mask generator on the full image, then applies
    'foodness' heuristics to filter out plate/tray/background regions.
    """
    debug = ctx is not None and ctx.debug
    t0    = time.perf_counter()

    generator = _load_sam_generator()
    if generator is None:
        results = _segment_color_fallback(image_bgr)
        if debug:
            _save_segmentation_debug(image_bgr, results, ctx,
                                     time.perf_counter() - t0,
                                     method="color_fallback")
        return results

    rgb       = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    masks_data = generator.generate(rgb)

    gray      = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    laplacian = np.abs(cv2.Laplacian(gray, cv2.CV_32F))
    hsv       = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    sat       = hsv[:, :, 1]

    results    = []
    h, w       = image_bgr.shape[:2]
    used_area  = np.zeros((h, w), dtype=bool)
    rejected   = 0

    masks_data.sort(key=lambda x: x["stability_score"], reverse=True)

    for data in masks_data:
        mask  = data["segmentation"]
        area  = int(data["area"])
        img_a = h * w

        if area < img_a * 0.002 or area > img_a * 0.4:
            rejected += 1
            continue

        m_sat = np.mean(sat[mask])
        m_var = np.mean(laplacian[mask])
        if m_sat < 12 and m_var < 15:
            rejected += 1
            continue

        new_area = (mask & ~used_area).sum()
        if new_area < area * 0.25:
            rejected += 1
            continue

        used_area |= mask
        results.append({
            "mask":  mask,
            "area":  area,
            "score": float(data["stability_score"]),
        })

    elapsed = time.perf_counter() - t0

    if debug:
        _save_segmentation_debug(image_bgr, results, ctx, elapsed,
                                 method="FullSAM",
                                 total_candidates=len(masks_data),
                                 rejected=rejected)

    return results


def segment_per_compartment_sam(
    image_bgr: np.ndarray,
    compartments: list[dict],
    ctx=None,
) -> list[dict]:
    """
    Enhancement #8 — Per-compartment SAM segmentation.

    Runs SAM inside each detected compartment region separately, then maps
    masks back into full-image coordinates.  Avoids false positives from
    plate rims / table edges outside compartments.

    Falls back to segment_full_image_sam() if:
    - SamPredictor unavailable
    - No compartments provided
    """
    debug = ctx is not None and ctx.debug

    if not compartments:
        logger.info("No compartments — falling back to full-image SAM")
        return segment_full_image_sam(image_bgr, ctx=ctx)

    predictor = _load_sam_predictor()
    if predictor is None:
        logger.info("SamPredictor unavailable — falling back to full-image SAM")
        return segment_full_image_sam(image_bgr, ctx=ctx)

    t0     = time.perf_counter()
    h_full, w_full = image_bgr.shape[:2]
    results        = []
    used_area      = np.zeros((h_full, w_full), dtype=bool)

    rgb_full = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    for comp_idx, comp in enumerate(compartments):
        cx, cy, cw, ch = comp["bbox"]

        # Guard against zero-area bbox
        if cw < 10 or ch < 10:
            continue

        # Crop compartment
        crop_rgb = rgb_full[cy:cy+ch, cx:cx+cw]

        try:
            predictor.set_image(crop_rgb)
        except Exception as exc:
            logger.warning(f"Compartment {comp_idx}: predictor.set_image failed: {exc}")
            continue

        # Grid of point prompts inside the compartment
        pts_x = np.linspace(cw * 0.2, cw * 0.8, 3, dtype=int)
        pts_y = np.linspace(ch * 0.2, ch * 0.8, 3, dtype=int)
        grid_pts = np.array([[px, py] for py in pts_y for px in pts_x])
        labels   = np.ones(len(grid_pts), dtype=int)  # foreground

        try:
            masks_pred, scores, _ = predictor.predict(
                point_coords=grid_pts,
                point_labels=labels,
                multimask_output=True,
            )
        except Exception as exc:
            logger.warning(f"Compartment {comp_idx}: predict failed: {exc}")
            continue

        # Pick the highest-scoring mask
        best_idx  = int(np.argmax(scores))
        crop_mask = masks_pred[best_idx]   # (ch, cw) bool
        score     = float(scores[best_idx])

        # Map back to full-image coordinates
        full_mask = np.zeros((h_full, w_full), dtype=bool)
        full_mask[cy:cy+ch, cx:cx+cw] = crop_mask

        # Deduplication
        area     = int(full_mask.sum())
        new_area = int((full_mask & ~used_area).sum())
        if area < 50 or new_area < area * 0.25:
            continue

        used_area |= full_mask
        results.append({
            "mask":           full_mask,
            "area":           area,
            "score":          score,
            "compartment_idx": comp_idx,
        })

    elapsed = time.perf_counter() - t0

    # If we got nothing, fall back to full-image mode
    if not results:
        logger.info("Per-compartment SAM found no masks — falling back to full-image SAM")
        return segment_full_image_sam(image_bgr, ctx=ctx)

    if debug:
        _save_segmentation_debug(image_bgr, results, ctx, elapsed,
                                 method="FullSAM-per-compartment",
                                 total_candidates=len(compartments),
                                 rejected=len(compartments) - len(results))

    return results


# ── Debug helpers ─────────────────────────────────────────────────────────────

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

    for i, item in enumerate(results):
        mask_uint8 = (item["mask"].astype(np.uint8)) * 255
        idx = ctx.next_index("segmentation")
        ctx.save_image("segmentation", f"{idx:02d}_mask_item_{i+1}.png", mask_uint8)

    overlay = image_bgr.copy()
    colors  = [
        (66, 133, 244), (52, 168, 83),  (234, 67, 53),
        (251, 188, 4),  (154, 78, 174), (0, 172, 193),
        (255, 112, 67), (121, 134, 203),
    ]

    for i, item in enumerate(results):
        color       = colors[i % len(colors)]
        mask_bool   = item["mask"]
        color_layer = np.zeros_like(overlay)
        color_layer[mask_bool] = color
        overlay = cv2.addWeighted(overlay, 1.0, color_layer, 0.4, 0)
        mask_u8 = mask_bool.astype(np.uint8)
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, color, 2)
        M = cv2.moments(mask_u8)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            label_text = item.get("label", f"#{i+1}")
            cv2.putText(overlay, f"{label_text} ({item['score']:.2f})",
                        (cx - 30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 2)

    idx  = ctx.next_index("segmentation")
    fname = f"{idx:02d}_segmentation_overlay.png"
    ctx.save_image("segmentation", fname, overlay)

    ctx.log("Segmentation", f"{len(results)} food items segmented",
            {"method": method,
             "total_candidates": total_candidates,
             "rejected": rejected,
             "accepted": len(results)},
            elapsed=elapsed, output_file=fname)


# ── Color-based fallback (unchanged) ─────────────────────────────────────────

def _segment_color_fallback(image_crop: np.ndarray) -> list[dict]:
    """Improved fallback using broader color/texture heuristic."""
    if image_crop.size == 0:
        return []

    hsv  = cv2.cvtColor(image_crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
    lap  = np.abs(cv2.Laplacian(gray, cv2.CV_32F))

    food_mask = (hsv[:, :, 1] > 12) | (lap > 20)

    kernel    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    food_mask = cv2.morphologyEx(food_mask.astype(np.uint8),
                                  cv2.MORPH_CLOSE, kernel, iterations=2)
    food_mask = cv2.morphologyEx(food_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    food_mask = food_mask.astype(bool)

    area = int(food_mask.sum())
    if area < (image_crop.shape[0] * image_crop.shape[1]) * 0.01:
        return []

    return [{"mask": food_mask, "area": area, "score": 0.5}]
