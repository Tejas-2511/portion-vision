"""
Per-pixel volume integration.

For each food mask:
  1. Iterate over mask pixels
  2. Compute pixel area using cm_per_pixel scale
  3. Multiply by the height at that pixel (from depth map, in cm)
  4. Sum → total volume in cm³ (≈ ml)
"""

import numpy as np


def compute_volume(
    food_mask: np.ndarray,
    height_map_cm: np.ndarray,
    cm_per_pixel: float,
) -> float:
    """
    Compute the volume (in cm³ ≈ ml) of a food item.

    Args:
        food_mask:      (H, W) bool — True where the food is.
        height_map_cm:  (H, W) float32 — food height above plate in cm.
        cm_per_pixel:   scale factor from pixel coords to real-world cm.

    Returns:
        volume in cm³ (≈ ml).
    """
    if food_mask is None or not food_mask.any():
        return 0.0

    # Area of a single pixel in cm²
    pixel_area_cm2 = cm_per_pixel ** 2

    # Heights within the food mask
    masked_heights = height_map_cm[food_mask]

    # Clamp negative heights (noise)
    masked_heights = np.clip(masked_heights, 0, None)

    # Volume = Σ (pixel_area × pixel_height)
    volume_cm3 = float(np.sum(masked_heights) * pixel_area_cm2)

    return volume_cm3


def compute_volume_with_cap(
    food_mask: np.ndarray,
    height_map_cm: np.ndarray,
    cm_per_pixel: float,
    max_volume_ml: float = None,
) -> float:
    """
    Compute volume and optionally clamp to a max physical limit
    (e.g., the compartment's known max capacity).
    """
    vol = compute_volume(food_mask, height_map_cm, cm_per_pixel)

    if max_volume_ml is not None and vol > max_volume_ml:
        vol = max_volume_ml

    return vol
