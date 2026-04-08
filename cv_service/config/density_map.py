"""
Food density lookup table.

Maps food names (lowercase) to density in g/ml (≈ g/cm³).
Used for: mass_g = volume_ml × density.

Densities are approximate averages for cooked Indian mess food.

Enhancement #6 — Dynamic Density:
    Use get_dynamic_density(food_name, mask_region_bgr) instead of
    get_density() to adjust density based on visual features
    (brightness, saturation, texture) of the actual food pixels.
"""

from __future__ import annotations

import cv2
import numpy as np

FOOD_DENSITIES = {
    # ── Grains / Carbs ──
    "rice":             1.10,   # cooked white rice, moderately packed
    "sada rice":        1.10,
    "steam rice":       1.08,
    "jeera rice":       1.05,
    "fried rice":       0.95,
    "biryani":          1.00,
    "pulao":            1.00,
    "khichdi":          1.10,
    "chapati":          0.85,   # flat bread, solid
    "roti":             0.85,
    "naan":             0.80,
    "paratha":          0.90,
    "poha":             0.65,
    "upma":             0.85,
    "idli":             0.95,
    "dosa":             0.55,   # thin, less dense
    "oats":             0.80,
    "bread":            0.35,

    # ── Dals / Lentils ──
    "dal":              1.05,
    "dal palak":        1.05,
    "dal amritsari":    1.05,
    "dal fry":          1.05,
    "dal tadka":        1.05,
    "dal makhani":      1.08,
    "sambar":           1.02,
    "rasam":            1.00,
    "rajma":            1.10,
    "chole":            1.08,
    "chana":            1.08,

    # ── Curries / Protein ──
    "chicken curry":    1.05,
    "chicken":          1.05,
    "egg curry":        1.02,
    "egg":              1.03,
    "fish curry":       1.05,
    "mutton":           1.06,
    "paneer":           1.03,
    "paneer do pyaza":  1.03,
    "paneer butter masala": 1.02,
    "kofta":            1.00,

    # ── Sabzis / Sides ──
    "sabji":            0.90,
    "sabzi":            0.90,
    "aloo":             1.00,
    "aloo capsicum":    0.95,
    "aloo gobi":        0.92,
    "dal vada curry":   1.02,
    "gobi":             0.85,
    "bhindi":           0.80,
    "baingan":          0.85,
    "mixed veg":        0.90,
    "poriyal":          0.85,
    "bhaji":            0.80,

    # ── Accompaniments / Condiments ──
    "raita":            1.02,
    "curd":             1.03,
    "salad":            0.60,
    "pickle":           1.10,
    "chutney":          1.05,
    "tomato chutney":   1.05,
    "papad":            0.30,   # very light, crispy

    # ── Sweets ──
    "halwa":            1.10,
    "gulab jamun":      1.15,
    "kheer":            1.05,
    "laddu":            1.05,
    "barfi":            1.10,

    # ── Beverages ──
    "milk":             1.03,
    "lassi":            1.04,
    "chaas":            1.01,
}

# Fallback density when food name is not found
DEFAULT_DENSITY = 1.0  # g/ml (approximately water density)


def get_density(food_name: str) -> float:
    """
    Lookup density for a food item.
    Tries exact match first, then substring match, then returns default.
    """
    key = food_name.strip().lower()

    if key in FOOD_DENSITIES:
        return FOOD_DENSITIES[key]

    for name, density in FOOD_DENSITIES.items():
        if name in key or key in name:
            return density

    return DEFAULT_DENSITY


def get_dynamic_density(
    food_name: str,
    mask_region_bgr: np.ndarray | None = None,
) -> float:
    """
    Enhancement #6 — Dynamic density adjustment based on visual features.

    Extracts brightness, saturation, and texture from the food's pixel region
    and adjusts the base density accordingly.  Falls back to get_density()
    if mask_region_bgr is not provided or too small.

    Args:
        food_name:        Canonical food name.
        mask_region_bgr:  BGR crop of just the food pixels (can contain grey
                          background outside the mask — see classifier.py).
                          Pass None to use static density.

    Returns:
        Adjusted density in g/ml.
    """
    base_density = get_density(food_name)

    if mask_region_bgr is None or mask_region_bgr.size < 100:
        return base_density

    try:
        hsv = cv2.cvtColor(mask_region_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
        mean_brightness = float(np.mean(hsv[:, :, 2]))   # 0–255
        mean_saturation = float(np.mean(hsv[:, :, 1]))   # 0–255

        gray    = cv2.cvtColor(mask_region_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        texture = float(np.var(cv2.Laplacian(gray, cv2.CV_32F)))

    except cv2.error:
        return base_density

    key = food_name.strip().lower()

    # ── Per-food visual adjustment rules ─────────────────────────────────────
    # Rice: bright (white) = less packed, darker = more packed
    if "rice" in key:
        if mean_brightness > 200:       # very white/fluffy
            return max(base_density - 0.15, 0.70)
        elif mean_brightness > 160:     # typical steamed rice
            return base_density
        else:                           # darker, drier, more compact
            return min(base_density + 0.10, 1.25)

    # Dal / sambar: more liquid → lower density (thin dal is close to water)
    if "dal" in key or "sambar" in key or "rasam" in key:
        if mean_saturation < 40:        # very pale / watery dal
            return max(base_density - 0.10, 0.90)
        elif texture > 200:             # chunky / thick dal
            return min(base_density + 0.08, 1.20)
        return base_density

    # Sabzi / curries: high texture = chunky = denser
    if any(k in key for k in ("sabzi", "sabji", "gobi", "aloo", "chicken", "paneer")):
        if texture > 300:
            return min(base_density + 0.10, 1.20)
        elif texture < 50:
            return max(base_density - 0.05, 0.75)
        return base_density

    # Roti / chapati: highly textured = freshly puffed = slightly less dense
    if any(k in key for k in ("roti", "chapati", "naan", "paratha")):
        if texture > 500:
            return max(base_density - 0.10, 0.65)
        return base_density

    return base_density
