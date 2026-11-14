"""
PortionVision — Physics-Informed Volumetric Voxel Integration Module.

Implements rigorous pixel-level volume integration:
    V = Σ (H_i × A_i)

Where:
    - H_i: Corrected food height at pixel i, in centimeters (above support floor/rim).
    - A_i: Physical surface area represented by pixel i, in cm² (with perspective scaling).
    - V  : Estimated volume in cubic centimeters (equivalent to millilitres, ml).

Preserves and improves the 5 distinct food geometric archetypes:
    I.   Planar Laminate   (roti, chapati, naan, paratha, papad)
    II.  Sliced Salad      (cucumber, tomato, onion, beetroot)
    III. Liquid in Well    (dal, sambar, rasam, curd, dahi, seviyan)
    IV.  Mounded Grain     (steamed rice, biryani, pulao, khichdi)
    V.   Chunky Suspension (mixed vegetable sabzi, paneer, chunky curries)
    VI.  Condiment Dollop  (pickle, achar, chutney)
"""

from __future__ import annotations

import logging
from typing import Any, Tuple, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Archetype Identifiers
ARCHETYPE_PLANAR = "planar_laminate"
ARCHETYPE_SALAD = "sliced_salad"
ARCHETYPE_LIQUID = "liquid_in_well"
ARCHETYPE_MOUND = "mounded_grain"
ARCHETYPE_CHUNK = "chunky_suspension"
ARCHETYPE_CONDIMENT = "condiment_dollop"


# ── Archetype Classification & Physical Priors ──────────────────────────────

def classify_archetype(food_name: str) -> Tuple[str, str]:
    """
    Selects the physically appropriate geometric archetype for a food dish.

    Returns:
        (archetype_name, justification_string)
    """
    f = food_name.lower().strip()

    # Planar laminate
    if any(k in f for k in ["roti", "chapati", "phulka", "naan", "paratha", "papad", "dosa", "puri", "bhatura", "bread", "thepla"]):
        return ARCHETYPE_PLANAR, f"Thin approximately planar sheet structure; surface area dominates ({food_name})"

    # Sliced salad
    if any(k in f for k in ["cucumber", "salad", "tomato", "onion", "beetroot", "kachumber", "radish"]):
        return ARCHETYPE_SALAD, f"Discrete planar vegetable slices with calibrated cut-thickness floor ({food_name})"

    # Condiment / dollop
    if any(k in f for k in ["pickle", "achar", "chutney", "sauce", "condiment"]):
        return ARCHETYPE_CONDIMENT, f"Concentrated viscous dollop on plate surface ({food_name})"

    # Mounded grain (check composite grains before liquids to ensure dal-rice or khichdi are treated as mounds)
    if any(k in f for k in ["rice", "biryani", "pulao", "khichdi", "poha", "upma", "chawal"]):
        return ARCHETYPE_MOUND, f"Granular cohesive mound filling compartment bed + curved dome above rim ({food_name})"

    # Liquid in well
    if any(k in f for k in ["dal", "daal", "sambar", "rasam", "curd", "dahi", "raita", "kheer", "soup", "seviyan", "semiya", "sewai", "payasam"]):
        return ARCHETYPE_LIQUID, f"Conformal fluid filling molded compartment well; flat free surface ({food_name})"

    # Default fallback: Chunky suspension
    return ARCHETYPE_CHUNK, f"Irregular 3D solids suspended in gravy within compartment ({food_name})"


def get_planar_sheet_thickness_cm(food_name: str) -> float:
    """Returns the calibrated single-sheet physical thickness in cm."""
    f = food_name.lower().strip()
    if "papad" in f:
        return 0.15
    if any(k in f for k in ["paratha", "naan", "bhatura"]):
        return 0.38
    return 0.25  # Standard Indian chapati / phulka thickness


def get_salad_slice_thickness_cm(food_name: str) -> float:
    """Returns the calibrated single-slice physical thickness floor in cm."""
    f = food_name.lower().strip()
    if any(k in f for k in ["cucumber", "salad", "kachumber"]):
        return 0.75  # Cucumber slices (often slightly overlapping)
    if "tomato" in f:
        return 0.70
    if "onion" in f:
        return 0.55
    return 0.65


# ── Pixel Area Calibration & Perspective Scaling ────────────────────────────

def compute_physical_pixel_areas(
    mask_shape: Tuple[int, int],
    base_pixel_area_cm2: float,
    raw_depth_m: Optional[np.ndarray] = None,
    plate_depth_ref_m: Optional[float] = None,
) -> Tuple[np.ndarray, str]:
    """
    Computes physical surface area per pixel A_i in cm².

    When metric distance Z(x, y) is available from Depth Anything 3:
        A_i = base_pixel_area_cm2 * (Z(x, y) / Z_ref)²
    Where Z is distance from camera. Objects closer to camera image onto more pixels,
    so each pixel covers a smaller physical surface area.

    If metric depth is uncalibrated or plate reference is unavailable,
    returns uniform base_pixel_area_cm2.
    """
    H, W = mask_shape
    if (
        raw_depth_m is not None
        and plate_depth_ref_m is not None
        and plate_depth_ref_m > 0.10
        and raw_depth_m.shape == (H, W)
    ):
        # Scale ratio with safe clipping to prevent boundary artifacts (±15% max scale shift)
        z_ratio = np.clip(raw_depth_m / plate_depth_ref_m, 0.85, 1.15)
        pixel_areas = (base_pixel_area_cm2 * (z_ratio ** 2)).astype(np.float32)
        return pixel_areas, "perspective_depth_adjusted"

    # Default uniform area across rectified plate plane
    pixel_areas = np.full((H, W), base_pixel_area_cm2, dtype=np.float32)
    return pixel_areas, "plate_calibrated_uniform"


# ── Core Pixel-Level Volume Integrator ──────────────────────────────────────

def integrate_food_volume(
    height_relative: np.ndarray,
    food_mask: np.ndarray,
    base_pixel_area_cm2: float,
    food_name: str,
    well_offset_cm: float = 0.0,
    comp_max_vol_ml: float = 500.0,
    raw_depth_m: Optional[np.ndarray] = None,
    plate_depth_ref_m: Optional[float] = None,
) -> Tuple[float, np.ndarray, Dict[str, Any]]:
    """
    Executes physics-informed pixel-level volume integration:
        V = Σ_{i ∈ M_valid} (H_i^eff × A_i)

    Args:
        height_relative:     2D float32 array of relative heights in cm above plate rim plane.
        food_mask:           2D boolean array of segmented food pixels.
        base_pixel_area_cm2: Calibrated nominal pixel area in cm² (cm_per_pixel²).
        food_name:           Canonical or predicted name of the food item.
        well_offset_cm:      Measured or profile depth of the compartment well (cm).
        comp_max_vol_ml:     Physical containment capacity ceiling for the compartment (ml).
        raw_depth_m:         Optional metric depth in meters from camera.
        plate_depth_ref_m:   Optional reference plane depth in meters.

    Returns:
        (final_volume_ml, effective_height_map, diagnostics_dict)
    """
    diagnostics: Dict[str, Any] = {
        "food_name": food_name,
        "fallbacks_applied": [],
    }

    # Verify input shapes
    if food_mask.shape != height_relative.shape:
        raise ValueError(
            f"Shape mismatch: food_mask {food_mask.shape} vs height_relative {height_relative.shape}"
        )

    H, W = food_mask.shape
    raw_pixel_count = int(np.sum(food_mask))
    diagnostics["raw_pixel_count"] = raw_pixel_count

    # Empty mask guard
    if raw_pixel_count == 0:
        diagnostics["valid_pixel_count"] = 0
        diagnostics["empty_mask"] = True
        diagnostics["final_volume_ml"] = 0.0
        return 0.0, np.zeros((H, W), dtype=np.float32), diagnostics

    # 1. Classify Archetype
    archetype, justification = classify_archetype(food_name)
    diagnostics["archetype"] = archetype
    diagnostics["archetype_justification"] = justification

    # 2. Compute Physical Pixel Areas (Perspective-Aware)
    pixel_area_map, area_method = compute_physical_pixel_areas(
        mask_shape=(H, W),
        base_pixel_area_cm2=base_pixel_area_cm2,
        raw_depth_m=raw_depth_m,
        plate_depth_ref_m=plate_depth_ref_m,
    )
    diagnostics["pixel_area_method"] = area_method
    diagnostics["mean_pixel_area_cm2"] = float(np.mean(pixel_area_map[food_mask]))
    food_surface_area_cm2 = float(np.sum(pixel_area_map[food_mask]))
    diagnostics["food_surface_area_cm2"] = round(food_surface_area_cm2, 2)

    # 3. Robust Valid-Pixel Filtering & Outlier Rejection
    raw_heights = height_relative[food_mask]
    finite_mask = np.isfinite(raw_heights)
    if not np.any(finite_mask):
        diagnostics["fallbacks_applied"].append("ALL_PIXELS_NON_FINITE")
        diagnostics["valid_pixel_count"] = 0
        return 0.0, np.zeros((H, W), dtype=np.float32), diagnostics

    finite_heights = raw_heights[finite_mask]
    p1 = float(np.percentile(finite_heights, 1))
    p5 = float(np.percentile(finite_heights, 5))
    p25 = float(np.percentile(finite_heights, 25))
    p50 = float(np.median(finite_heights))
    p75 = float(np.percentile(finite_heights, 75))
    p95 = float(np.percentile(finite_heights, 95))
    p99 = float(np.percentile(finite_heights, 99))

    # Reject isolated specular spikes (e.g. wet reflections on food or metallic edges)
    # Filter within [p1 - 0.5, p99 + 0.5] inside the food mask
    h_min_bound = p1 - 0.5
    h_max_bound = p99 + 0.5

    valid_mask_2d = (
        food_mask
        & np.isfinite(height_relative)
        & (height_relative >= h_min_bound)
        & (height_relative <= h_max_bound)
    )
    valid_pixel_count = int(np.sum(valid_mask_2d))
    clipped_pixel_count = raw_pixel_count - valid_pixel_count

    diagnostics["valid_pixel_count"] = valid_pixel_count
    diagnostics["clipped_pixel_count"] = clipped_pixel_count
    diagnostics["valid_pixel_ratio"] = round(valid_pixel_count / max(raw_pixel_count, 1), 4)

    # Height distribution summary
    diagnostics["height_stats_cm"] = {
        "min": round(float(np.min(finite_heights)), 3),
        "p5": round(p5, 3),
        "p25": round(p25, 3),
        "median": round(p50, 3),
        "mean": round(float(np.mean(finite_heights)), 3),
        "p75": round(p75, 3),
        "p95": round(p95, 3),
        "max": round(float(np.max(finite_heights)), 3),
        "std": round(float(np.std(finite_heights)), 3),
    }

    # 4. Archetype-Specific Effective Height Calculation H_i^eff
    # Base reference: p5 represents the food's support plane (where food meets tray floor/well)
    H_val = height_relative[valid_mask_2d]
    delta_H = np.maximum(0.0, H_val - p5)  # True 3D elevation above support base
    span = max(p95 - p5, 0.05)

    eff_height_map = np.zeros((H, W), dtype=np.float32)

    if archetype == ARCHETYPE_PLANAR:
        # ── Archetype I: Planar Laminate ──
        # Physical Model: Thin flatbread sheet. Single sheet thickness t_sheet.
        # Folds add discrete/continuous layer multiples: L_i = 1.0 + (delta_H / t_sheet).
        t_sheet = get_planar_sheet_thickness_cm(food_name)
        diagnostics["unit_sheet_thickness_cm"] = t_sheet

        layer_ratio = 1.0 + np.clip(delta_H / t_sheet, 0.0, 2.5)
        H_eff = t_sheet * layer_ratio
        eff_height_map[valid_mask_2d] = H_eff

    elif archetype == ARCHETYPE_SALAD:
        # ── Archetype II: Sliced Salad ──
        # Physical Model: Planar vegetable slices with calibrated cut-thickness floor.
        t_slice = get_salad_slice_thickness_cm(food_name)
        diagnostics["slice_thickness_floor_cm"] = t_slice

        # Single slices never collapse below cut thickness; overlapping slices add elevation
        H_eff = t_slice + np.clip(delta_H, 0.0, 1.20)
        eff_height_map[valid_mask_2d] = H_eff

    elif archetype == ARCHETYPE_LIQUID:
        # ── Archetype III: Liquid in Well ──
        # Physical Model: Fluid filling a stamped tray well frustum.
        eff_well = max(well_offset_cm, 2.0)
        if eff_well != well_offset_cm:
            diagnostics["fallbacks_applied"].append(f"WELL_DEPTH_FLOORED_{eff_well:.1f}CM")
        diagnostics["effective_well_depth_cm"] = round(eff_well, 2)

        # Well fluid column with slight meniscus ripple + mold draft taper factor (0.88)
        fluid_depth = eff_well * 0.85 + np.clip(delta_H, 0.0, 1.0) * 0.40
        taper_factor = 0.88
        H_eff = fluid_depth * taper_factor
        eff_height_map[valid_mask_2d] = H_eff

    elif archetype == ARCHETYPE_MOUND:
        # ── Archetype IV: Mounded Grain ──
        # Physical Model: Base well bed + true continuous 3D dome rising above rim.
        eff_well = max(well_offset_cm, 1.8)
        if eff_well != well_offset_cm:
            diagnostics["fallbacks_applied"].append(f"MOUND_WELL_FLOORED_{eff_well:.1f}CM")
        diagnostics["effective_well_depth_cm"] = round(eff_well, 2)

        # Base well bed volume height
        base_bed_h = eff_well * 0.82
        # Above-rim 3D dome height: preserves true per-pixel measured surface topography
        s_dome = min(1.0, 1.80 / span)
        dome_h = np.clip(delta_H * s_dome, 0.0, 2.50) * 0.92
        H_eff = base_bed_h + dome_h
        eff_height_map[valid_mask_2d] = H_eff

    elif archetype == ARCHETYPE_CONDIMENT:
        # ── Archetype VI: Condiment Dollop ──
        # Physical Model: Concentrated viscous dollop (pickle, chutney) resting on tray.
        H_eff = np.clip(0.75 + delta_H * 0.40, 0.60, 1.60) * 0.85
        eff_height_map[valid_mask_2d] = H_eff

    else:
        # ── Archetype V: Chunky Suspension ──
        # Physical Model: Solid vegetable/paneer chunks in gravy inside compartment well.
        eff_well = max(well_offset_cm, 1.8)
        diagnostics["effective_well_depth_cm"] = round(eff_well, 2)

        s_chunk = min(1.0, 2.20 / span)
        chunk_depth = eff_well * 0.55 + np.clip(delta_H * s_chunk, 0.0, 2.50)
        solidity_factor = 0.85  # accounts for void spaces between chunks
        H_eff = chunk_depth * solidity_factor
        eff_height_map[valid_mask_2d] = H_eff

    # 5. Physics-Informed Pixel-Level Volume Integration
    # V = Σ (H_i^eff × A_i)
    pixel_volumes_ml = eff_height_map[valid_mask_2d] * pixel_area_map[valid_mask_2d]
    raw_integrated_vol_ml = float(np.sum(pixel_volumes_ml))
    diagnostics["raw_integrated_vol_ml"] = round(raw_integrated_vol_ml, 2)

    # 6. Containment Capacity Bounding
    final_vol_ml = raw_integrated_vol_ml
    if food_surface_area_cm2 <= 85.0 and comp_max_vol_ml >= 400:
        comp_max_vol_ml = food_surface_area_cm2 * 2.2 * 0.95

    if final_vol_ml > comp_max_vol_ml:
        diagnostics["compartment_capped"] = True
        diagnostics["cap_limit_ml"] = round(comp_max_vol_ml, 1)
        final_vol_ml = comp_max_vol_ml
    else:
        diagnostics["compartment_capped"] = False

    final_vol_ml = round(final_vol_ml, 1)
    diagnostics["final_volume_ml"] = final_vol_ml

    return final_vol_ml, eff_height_map, diagnostics
