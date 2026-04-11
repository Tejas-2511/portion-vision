"""
Monocular depth estimation using Depth Anything.

Enhancements over baseline:
  • #1  Hybrid depth — fuses Depth Anything output with per-food geometric priors
  • #4  Ellipse-based scale calibration — fits an ellipse to the plate rim
        for a more accurate cm-per-pixel estimate
  • #5  Gaussian smoothing before returning the depth map to suppress noise

Produces a relative depth map and normalizes it so the plate surface
is the zero-height baseline.
"""

from __future__ import annotations

import time
import logging
import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)

# ── Lazy-loaded global model ─────────────────────────────────────────────────
_depth_pipeline  = None
_depth_device    = None

# ── Food-specific height priors (min_cm, max_cm) ─────────────────────────────
# Used by apply_food_height_prior() to clamp and blend Depth Anything output.
FOOD_HEIGHT_PRIORS: dict[str, tuple[float, float]] = {
    # Flat / thin items
    "roti":     (0.4, 1.5),
    "chapati":  (0.4, 1.5),
    "naan":     (0.5, 1.8),
    "paratha":  (0.5, 2.0),
    "dosa":     (0.3, 0.8),
    "papad":    (0.2, 0.5),
    # Moderate mounds
    "rice":     (1.5, 4.5),
    "sada rice":(1.5, 4.5),
    "steam rice":(1.5, 4.0),
    "jeera rice":(1.5, 4.0),
    "fried rice":(1.5, 4.0),
    "biryani":  (2.0, 5.0),
    "pulao":    (1.5, 4.5),
    "khichdi":  (2.0, 5.0),
    "upma":     (2.0, 4.5),
    "poha":     (1.5, 3.5),
    # Liquid / semi-liquid
    "dal":      (1.5, 3.5),
    "dal fry":  (1.5, 3.5),
    "dal tadka":(1.5, 3.5),
    "dal makhani":(1.5, 3.5),
    "dal palak":(1.5, 3.5),
    "sambar":   (1.5, 3.0),
    "rasam":    (1.0, 2.5),
    "rajma":    (2.0, 4.0),
    "chole":    (2.0, 4.0),
    "chana":    (2.0, 4.0),
    "raita":    (1.5, 3.0),
    "curd":     (1.5, 3.0),
    # Sabzis / curries
    "sabzi":    (2.0, 5.0),
    "sabji":    (2.0, 5.0),
    "aloo":     (2.0, 5.0),
    "gobi":     (2.0, 4.5),
    "bhindi":   (2.0, 4.5),
    "baingan":  (2.0, 4.5),
    "mixed veg":(2.0, 4.5),
    "chicken curry":(2.5, 5.5),
    "chicken":  (2.5, 5.0),
    "egg curry":(2.0, 4.5),
    "paneer":   (2.5, 5.0),
    "mutton":   (2.5, 5.5),
    "fish curry":(2.0, 4.5),
    # Sweets / misc
    "halwa":    (2.0, 4.0),
    "kheer":    (1.5, 3.5),
    "gulab jamun":(3.0, 5.5),
    "salad":    (1.0, 3.0),
    "chutney":  (0.5, 2.0),
    "pickle":   (0.5, 2.0),
}

# Blending weights for hybrid depth
_DEPTH_ALPHA = 0.70   # weight given to raw depth output
_PRIOR_BETA  = 0.30   # weight given to the geometric prior mid-point

# Assumed plate outer diameter in cm — used by ellipse calibrator
_PLATE_DIAMETER_CM = 26.0


# ── Depth model ───────────────────────────────────────────────────────────────

def _load_depth_model() -> None:
    """Load Depth Anything model via transformers pipeline."""
    global _depth_pipeline, _depth_device

    if _depth_pipeline is not None:
        return

    from transformers import pipeline

    _depth_device = 0 if torch.cuda.is_available() else -1

    # Depth Anything V2 small, state of the art relative depth
    _depth_pipeline = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=_depth_device)

    logger.info(f"Depth Anything loaded on device factor {_depth_device}")


def estimate_depth(image_bgr: np.ndarray, ctx=None) -> np.ndarray:
    """
    Run Depth Anything depth estimation on a BGR image.

    Returns a depth map (H, W) as float32.
    Higher values = closer to camera (i.e., taller objects).

    Enhancement #5: Gaussian smoothing is applied before returning to
    reduce per-pixel noise that would otherwise inflate volume estimates.
    """
    debug = ctx is not None and ctx.debug
    t0 = time.perf_counter()

    _load_depth_model()

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    from PIL import Image
    pil_img = Image.fromarray(rgb)

    prediction = _depth_pipeline(pil_img)
    # Use raw tensor for geometric precision, not the normalized 0-255 PIL image
    pred_depth = prediction["predicted_depth"].squeeze().cpu().numpy()

    # Resize prediction to match input image dimensions
    depth = cv2.resize(pred_depth, (image_bgr.shape[1], image_bgr.shape[0]))
    depth = depth.astype(np.float32)

    # #5 — Smooth depth map before any downstream use
    depth = cv2.GaussianBlur(depth, (5, 5), 0)

    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_raw_depth.npy", depth)

        d_norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        idx = ctx.next_index("depth")
        ctx.save_image("depth", f"{idx:02d}_depth_normalized.png", d_norm)

        d_colored = cv2.applyColorMap(d_norm, cv2.COLORMAP_INFERNO)
        idx = ctx.next_index("depth")
        fname = f"{idx:02d}_depth_colored.png"
        ctx.save_image("depth", fname, d_colored)

        ctx.log("Depth Estimation", "Depth Anything depth map computed (smoothed)",
                {"device": str(_depth_device),
                 "shape": list(depth.shape),
                 "min": round(float(depth.min()), 3),
                 "max": round(float(depth.max()), 3)},
                elapsed=elapsed, output_file=fname)

    return depth


def apply_food_height_prior(
    height_map: np.ndarray,
    food_label: str,
    alpha: float = _DEPTH_ALPHA,
    beta: float = _PRIOR_BETA,
) -> np.ndarray:
    """
    Enhancement #1 — Hybrid depth fusion with food-specific geometric priors.

    Blends neural-derived height_map with a mid-point prior from
    FOOD_HEIGHT_PRIORS and then clamps to the physiologically valid range.

    Args:
        height_map:  Per-pixel height in cm (float32 array, same H×W as image).
        food_label:  Canonical food name (must match keys in FOOD_HEIGHT_PRIORS).
        alpha:       Weight for neural depth (default 0.70).
        beta:        Weight for prior mid-point (default 0.30).

    Returns:
        Fused + clamped height map (float32).
    """
    key = food_label.strip().lower()
    # Try exact match, then substring
    prior = None
    if key in FOOD_HEIGHT_PRIORS:
        prior = FOOD_HEIGHT_PRIORS[key]
    else:
        for k, v in FOOD_HEIGHT_PRIORS.items():
            if k in key or key in k:
                prior = v
                break

    if prior is None:
        # No known prior — return unchanged
        return height_map

    min_h, max_h = prior
    prior_mid = (min_h + max_h) / 2.0

    fused = alpha * height_map + beta * prior_mid
    clamped = np.clip(fused, min_h, max_h)
    return clamped.astype(np.float32)


def calibrate_scale_from_ellipse(
    image_bgr: np.ndarray,
    known_diameter_cm: float = _PLATE_DIAMETER_CM,
) -> float | None:
    """
    Enhancement #4 — Estimate cm-per-pixel scale by fitting an ellipse to the
    detected plate rim.

    Returns cm_per_pixel if a credible ellipse is found, else None.
    Falls back gracefully to the bbox-based compute_scale() in detection.py.
    """
    gray    = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edges   = cv2.Canny(blurred, 30, 100)

    # Dilate to close small gaps in the plate rim
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h, w = image_bgr.shape[:2]
    img_area = h * w

    # Look for the contour that looks like the plate boundary
    best_cm_per_px = None
    best_area      = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        # Must be a large-ish region (at least 10 % of frame, not the whole frame)
        if area < img_area * 0.10 or area > img_area * 0.95:
            continue
        if len(cnt) < 5:
            continue   # fitEllipse needs ≥5 points

        try:
            (cx, cy), (major, minor), angle = cv2.fitEllipse(cnt)
            # Sanity: ellipse axes must be reasonably similar (plate is near-round)
            if minor < 1e-3:
                continue
            aspect = major / minor
            if aspect > 2.0:
                continue  # too elongated — not a plate
            # Use average axis as diameter estimate
            avg_axis_px = (major + minor) / 2.0
            cm_per_px   = known_diameter_cm / avg_axis_px

            if area > best_area:
                best_area      = area
                best_cm_per_px = cm_per_px

        except cv2.error:
            continue

    if best_cm_per_px is not None:
        logger.info(f"Ellipse scale calibration: {best_cm_per_px:.5f} cm/px "
                    f"(plate diameter assumed {known_diameter_cm} cm)")
    return best_cm_per_px


# ── Depth normalisation helpers (unchanged from baseline) ─────────────────────

def normalize_depth_to_plate(
    depth_map: np.ndarray,
    plate_mask: np.ndarray = None,
    ctx=None,
) -> np.ndarray:
    """
    Normalize the depth map relative to the plate surface.
    Returns the difference in depth values from the baseline (dividers/rim).

    In Depth Anything, higher values = closer to camera.
    """
    debug = ctx is not None and ctx.debug
    t0    = time.perf_counter()

    if plate_mask is not None and plate_mask.any():
        baseline = np.median(depth_map[plate_mask])
    else:
        baseline = np.median(depth_map)

    height_map_rel = depth_map - baseline

    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_height_relative.npy", height_map_rel)

        vis = height_map_rel - height_map_rel.min()
        if vis.max() > 0:
            vis = (vis / vis.max() * 255).astype(np.uint8)
        else:
            vis = np.zeros_like(height_map_rel, dtype=np.uint8)
        vis_colored = cv2.applyColorMap(vis, cv2.COLORMAP_JET)
        idx = ctx.next_index("depth")
        fname = f"{idx:02d}_height_relative_colored.png"
        ctx.save_image("depth", fname, vis_colored)

        ctx.log("Depth Normalization", "Baseline subtracted from depth",
                {"baseline": round(float(baseline), 3)},
                elapsed=elapsed, output_file=fname)

    return height_map_rel


def depth_to_cm(
    height_map_relative: np.ndarray,
    raw_depth: np.ndarray,
    cm_per_pixel: float,
    image_width_px: int,
    ctx=None,
) -> np.ndarray:
    """
    Convert relative depth differences to real-world centimetres.

    Uses a pinhole camera heuristic:
    Dist_to_plate (Z) is roughly 1.2 * image_width (pixels) * scale (cm/px).
    Height_cm = (delta_depth / current_depth) * Z_plate.
    """
    debug  = ctx is not None and ctx.debug
    t0     = time.perf_counter()

    z_plate    = 1.2 * image_width_px * cm_per_pixel
    depth_safe = np.where(raw_depth > 0, raw_depth, 1e-6)
    height_cm  = (height_map_relative / depth_safe) * z_plate

    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_height_cm.npy", height_cm.astype(np.float32))
        ctx.log("Depth → cm Conversion", "Height map converted to centimetres",
                {"z_plate_cm": round(z_plate, 2),
                 "cm_per_pixel": round(cm_per_pixel, 5)},
                elapsed=elapsed)

    return height_cm.astype(np.float32)
