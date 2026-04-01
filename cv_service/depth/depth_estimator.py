"""
Monocular depth estimation using MiDaS (via torch.hub).

Produces a relative depth map and normalizes it so the plate surface
is the zero-height baseline.
"""

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


def estimate_depth(image_bgr: np.ndarray) -> np.ndarray:
    """
    Run MiDaS depth estimation on a BGR image.

    Returns a depth map (H, W) as float32.
    Higher values = closer to camera (i.e., taller objects).
    """
    _load_midas()

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    input_batch = _midas_transform(rgb).to(_midas_device)

    with torch.no_grad():
        prediction = _midas_model(input_batch)

    # Resize prediction to match input image dimensions
    depth = prediction.squeeze().cpu().numpy()
    depth = cv2.resize(depth, (image_bgr.shape[1], image_bgr.shape[0]))

    return depth.astype(np.float32)


def normalize_depth_to_plate(
    depth_map: np.ndarray,
    plate_mask: np.ndarray = None,
) -> np.ndarray:
    """
    Normalize the depth map relative to the plate surface.
    Returns the difference in depth values from the baseline (dividers/rim).

    In MiDaS, higher values = closer to camera.
    """
    if plate_mask is not None and plate_mask.any():
        # Use simple median of dividers/rim as baseline
        baseline = np.median(depth_map[plate_mask])
    else:
        baseline = np.median(depth_map)

    # Return depth relative to baseline (can be negative if below divider)
    # height_relative = depth_pixel - baseline
    height_map_rel = depth_map - baseline
    return height_map_rel


def depth_to_cm(
    height_map_relative: np.ndarray,
    raw_depth: np.ndarray,
    cm_per_pixel: float,
    image_width_px: int,
) -> np.ndarray:
    """
    Convert relative depth differences to real-world centimeters.

    Uses a pinhole camera heuristic:
    Dist_to_plate (Z) is roughly 1.2 * image_width (pixels) * scale (cm/px).
    Height_cm = (delta_depth / current_depth) * Z_plate.

    This is much more accurate than a fixed height range because it scales
    with the actual plate size and camera distance.
    """
    # Estimated distance to plate in cm
    z_plate = 1.2 * image_width_px * cm_per_pixel

    # Avoid division by zero
    depth_safe = np.where(raw_depth > 0, raw_depth, 1e-6)

    # Metric height = (depth_rel / depth_absolute) * Z_plate
    # Note: height_map_relative is (D_food - D_plate)
    # Formula: H = (D_f - D_p)/D_f * Z_p
    height_cm = (height_map_relative / depth_safe) * z_plate

    # Smooth out noise but keep negative values (below divider)
    return height_cm.astype(np.float32)
