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
    Normalize the depth map so the plate surface is zero height.

    In MiDaS output, higher values = closer to camera.
    Food sits above the plate, so food pixels should have higher depth values
    than the plate surface.

    The function computes:
        height = depth_pixel - depth_plate_surface
        (clamp negatives to 0)

    Args:
        depth_map: raw MiDaS output (H, W), float32
        plate_mask: optional bool mask where True = plate surface (non-food).
                    If None, the median depth is used as baseline.

    Returns:
        height_map (H, W) float32, in relative units (0 = plate surface).
    """
    if plate_mask is not None and plate_mask.any():
        baseline = np.median(depth_map[plate_mask])
    else:
        # Use the overall median as a rough plate baseline
        baseline = np.median(depth_map)

    # Food is closer to camera → higher depth values in MiDaS
    height_map = depth_map - baseline
    height_map = np.clip(height_map, 0, None)  # no negative heights

    return height_map


def depth_to_cm(
    height_map_relative: np.ndarray,
    max_food_height_cm: float = 3.0,
) -> np.ndarray:
    """
    Convert relative height map to approximate centimeters.

    Since MiDaS gives relative (not metric) depth, we scale the range
    so the maximum observed height maps to `max_food_height_cm`.

    This is an approximation — for true metric depth, a stereo/structured-
    light sensor would be needed.
    """
    peak = height_map_relative.max()
    if peak <= 0:
        return np.zeros_like(height_map_relative)

    return (height_map_relative / peak) * max_food_height_cm
