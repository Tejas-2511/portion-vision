"""
Monocular depth estimation using MiDaS (via torch.hub).

Produces a relative depth map and normalizes it so the plate surface
is the zero-height baseline.
"""

import time
import logging
import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)

# ── Lazy-loaded global model ─────────────────────────────────────────────
_midas_model = None
_midas_transform = None
_midas_device = None


def _load_midas():
    """Load MiDaS small model via torch.hub (downloads on first run)."""
    global _midas_model, _midas_transform, _midas_device

    if _midas_model is not None:
        return

    _midas_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Use MiDaS v2.1 Small — fast and good enough for relative depth
    _midas_model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True)
    _midas_model.to(_midas_device)
    _midas_model.eval()

    midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
    _midas_transform = midas_transforms.small_transform

    logger.info(f"MiDaS loaded on {_midas_device}")


def estimate_depth(image_bgr: np.ndarray, ctx=None) -> np.ndarray:
    """
    Run MiDaS depth estimation on a BGR image.

    Returns a depth map (H, W) as float32.
    Higher values = closer to camera (i.e., taller objects).
    """
    debug = ctx is not None and ctx.debug
    t0 = time.perf_counter()

    _load_midas()

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    input_batch = _midas_transform(rgb).to(_midas_device)

    with torch.no_grad():
        prediction = _midas_model(input_batch)

    # Resize prediction to match input image dimensions
    depth = prediction.squeeze().cpu().numpy()
    depth = cv2.resize(depth, (image_bgr.shape[1], image_bgr.shape[0]))
    depth = depth.astype(np.float32)

    elapsed = time.perf_counter() - t0

    if debug:
        # Save raw depth as .npy
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_raw_depth.npy", depth)

        # Save normalized grayscale visualization
        d_norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        idx = ctx.next_index("depth")
        ctx.save_image("depth", f"{idx:02d}_depth_normalized.png", d_norm)

        # Save colored depth visualization (INFERNO colormap)
        d_colored = cv2.applyColorMap(d_norm, cv2.COLORMAP_INFERNO)
        idx = ctx.next_index("depth")
        fname = f"{idx:02d}_depth_colored.png"
        ctx.save_image("depth", fname, d_colored)

        ctx.log("Depth Estimation", "MiDaS depth map computed",
                {"device": str(_midas_device),
                 "shape": list(depth.shape),
                 "min": round(float(depth.min()), 3),
                 "max": round(float(depth.max()), 3)},
                elapsed=elapsed, output_file=fname)

    return depth


def normalize_depth_to_plate(
    depth_map: np.ndarray,
    plate_mask: np.ndarray = None,
    ctx=None,
) -> np.ndarray:
    """
    Normalize the depth map relative to the plate surface.
    Returns the difference in depth values from the baseline (dividers/rim).

    In MiDaS, higher values = closer to camera.
    """
    debug = ctx is not None and ctx.debug
    t0 = time.perf_counter()

    if plate_mask is not None and plate_mask.any():
        # Use simple median of dividers/rim as baseline
        baseline = np.median(depth_map[plate_mask])
    else:
        baseline = np.median(depth_map)

    # Return depth relative to baseline (can be negative if below divider)
    height_map_rel = depth_map - baseline

    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_height_relative.npy", height_map_rel)

        # Visualize: shift to 0-255 range for display
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
    Convert relative depth differences to real-world centimeters.

    Uses a pinhole camera heuristic:
    Dist_to_plate (Z) is roughly 1.2 * image_width (pixels) * scale (cm/px).
    Height_cm = (delta_depth / current_depth) * Z_plate.
    """
    debug = ctx is not None and ctx.debug
    t0 = time.perf_counter()

    # Estimated distance to plate in cm
    z_plate = 1.2 * image_width_px * cm_per_pixel

    # Avoid division by zero
    depth_safe = np.where(raw_depth > 0, raw_depth, 1e-6)

    # Metric height = (depth_rel / depth_absolute) * Z_plate
    height_cm = (height_map_relative / depth_safe) * z_plate

    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_height_cm.npy", height_cm.astype(np.float32))
        ctx.log("Depth → cm Conversion", "Height map converted to centimeters",
                {"z_plate_cm": round(z_plate, 2),
                 "cm_per_pixel": round(cm_per_pixel, 5)},
                elapsed=elapsed)

    # Smooth out noise but keep negative values (below divider)
    return height_cm.astype(np.float32)
