"""
End-to-end mass estimation pipeline.

Orchestrates all vision pipeline stages:

  #1  Meta SAM 3 unified open-vocabulary food identification and instance segmentation
  #2  Depth Anything 3 (DA3METRIC-LARGE) physical metric depth estimation
  #3  Ellipse-based scale calibration (px -> cm)
  #4  2D Planar Surface Normal Fitting (tilt-invariant baseline zeroing)
  #5  Hybrid depth reconstruction (DA3 metric depth + 486 food geometric priors)
  #6  5-Archetype volumetric voxel integration (planar, salad, liquid, mound, chunk)
  #7  Multi-instance canonical dish aggregation (unified items + piece count badges)
  #8  Multi-spectral dynamic density mapping (g/cm³) via HSV & Laplacian texture
  #9  Composite confidence scoring (segmentation, classification, depth, scale)
  #10 Nutritional macronutrient calculation (calories, protein, carbs, fats)

When debug=True, creates a timestamped run directory and saves every
intermediate image, NumPy array, and a final HTML report.
"""

from __future__ import annotations

import os
import time
import logging
import re
from typing import Any
import cv2
import numpy as np

from diagnostics.run_context import RunContext
from image_processing.preprocess import process_image
from image_processing.detection import (
    find_compartments,
    compute_scale,
    match_compartments_to_profile,
)
from depth.depth_estimator import (
    estimate_depth,
    normalize_depth_to_plate,
    depth_to_cm,
    apply_food_height_prior,
    calibrate_scale_from_ellipse,
    FOOD_HEIGHT_PRIORS,
)
from config.synonym_map import SYNONYM_GROUPS
from config.density_map import get_dynamic_density
from config.macro_map import get_macros
from config.plate_config import get_plate_profile

logger = logging.getLogger(__name__)


# ── Food Geometric Archetype Helpers ──────────────────────────────────────────

def _is_planar_food(food_name: str) -> bool:
    f = food_name.lower()
    return any(k in f for k in ["roti", "chapati", "phulka", "naan", "paratha", "papad", "dosa", "puri", "bhatura", "bread"])


def _is_liquid_food(food_name: str) -> bool:
    f = food_name.lower()
    # Composite dishes with rice/khichdi form semi-solid mounds, not conformal liquids
    if any(k in f for k in ["rice", "chawal", "khichdi", "biryani", "pulao"]):
        return False
    return any(k in f for k in ["dal", "daal", "sambar", "rasam", "curd", "dahi", "raita", "kheer", "soup", "seviyan", "semiya", "sewai", "payasam"])


def _is_condiment_food(food_name: str) -> bool:
    f = food_name.lower()
    return any(k in f for k in ["pickle", "achar", "chutney", "sauce", "condiment"])


def _is_mound_food(food_name: str) -> bool:
    f = food_name.lower()
    return any(k in f for k in ["rice", "biryani", "pulao", "khichdi", "poha", "upma", "chawal", "dal rice", "dal chawal"])


def _get_planar_thickness_cm(food_name: str) -> float:
    f = food_name.lower()
    if "papad" in f:
        return 0.15
    if any(k in f for k in ["paratha", "naan", "bhatura"]):
        return 0.38
    return 0.25  # standard Indian chapati / roti thickness


def _is_sliced_salad_food(food_name: str) -> bool:
    f = food_name.lower()
    return any(k in f for k in ["cucumber", "salad", "tomato", "onion", "beetroot", "kachumber"])


def _get_salad_slice_thickness_cm(food_name: str) -> float:
    f = food_name.lower()
    if "cucumber" in f or "salad" in f or "kachumber" in f:
        return 0.75  # calibrated cucumber / salad slice bed (accounting for overlapping slices)
    if "tomato" in f:
        return 0.70
    if "onion" in f:
        return 0.55
    return 0.65


# ── Fuzzy & Synonym Matching Helper ──────────────────────────────────────────

def _is_label_match(expected_name: str, class_label: str) -> tuple[bool, float]:
    """
    Checks if an expected item matches a classifier label using:
    1. Exact or substring match (e.g. 'rice' in 'jeera rice')
    2. Token set overlap (e.g. 'aloo gobi' & 'gobi masala')
    3. Canonical Indian food synonym clusters from classifier.SYNONYM_GROUPS
    Returns (is_match, match_affinity_multiplier)
    """
    e = expected_name.lower().strip()
    d = class_label.lower().strip()
    if not e or not d:
        return False, 0.0

    if e == d:
        return True, 1.0

    if e in d or d in e:
        return True, 0.95

    # Check token overlap
    e_tokens = set(re.findall(r"\w+", e))
    d_tokens = set(re.findall(r"\w+", d))
    if e_tokens and d_tokens and (e_tokens & d_tokens):
        return True, 0.85

    # Check unified synonym groups
    for group in SYNONYM_GROUPS:
        if any(term in e for term in group) and any(term in d for term in group):
            return True, 0.75

    return False, 0.0


# ── Hungarian assignment helper ───────────────────────────────────────────────

def _hungarian_assign(
    food_masks: list[dict],
    expected_items: list[str],
    compartments: list[dict] | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Enhancement #9 — Optimal mask ↔ expected-item assignment.

    Builds a cost matrix where entry (i, j) = dissimilarity between
    mask i and expected item j, then uses scipy's linear_sum_assignment
    (Hungarian algorithm) to find the globally optimal matching.

    Cost components:
    - Compartment label match (0 if compartment label contains food keyword)
    - Spatial overlap with compartment bbox (less overlap = higher cost)
    - Classification confidence (lower = higher cost)

    Returns a list of food-name strings, one per mask, in the same order.
    """
    n_masks  = len(food_masks)
    n_items  = len(expected_items)
    n        = max(n_masks, n_items)

    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        logger.warning("scipy not available — falling back to greedy assignment")
        return _greedy_assign(food_masks, expected_items, compartments)

    # Cost matrix (float, shape n×n, padded with zeros)
    cost = np.zeros((n, n), dtype=np.float64)

    def _get_category(food_name: str) -> str:
        f = food_name.lower()
        if any(k in f for k in ["chapati", "roti", "naan", "paratha", "flatbread", "phulka", "bread", "idli", "dosa", "poha", "upma", "puri", "bhatura", "thepla", "vada", "uttapam"]):
            return "bread"
        if any(k in f for k in ["rice", "biryani", "pulao", "khichdi"]):
            return "rice"
        if any(k in f for k in ["dal", "daal", "sambar", "curry", "veg", "sabzi", "sabji", "paneer", "chole", "rajma", "gobi", "aloo", "bhindi", "rasam"]):
            return "curry"
        if any(k in f for k in ["samosa", "pakoda", "cutlet", "bonda", "chaat", "snack"]):
            return "snack"
        if any(k in f for k in ["halwa", "gulab jamun", "kheer", "payasam", "jalebi", "laddu", "barfi", "sweet", "dessert"]):
            return "sweet"
        if any(k in f for k in ["banana", "apple", "papaya", "watermelon", "orange", "fruit"]):
            return "fruit"
        return "side"

    for i, mask_data in enumerate(food_masks):
        mask   = mask_data["mask"]
        area   = mask_data.get("area", int(mask.sum()))
        mask_h, mask_w = mask.shape

        rows_m, cols_m = np.where(mask)
        cy = float(np.mean(rows_m)) if len(rows_m) > 0 else mask_h / 2.0
        cx = float(np.mean(cols_m)) if len(cols_m) > 0 else mask_w / 2.0

        for j, expected in enumerate(expected_items):
            c = 0.0
            expected_lower = expected.lower()
            class_label    = mask_data.get("class_label", "").lower()
            class_conf     = mask_data.get("class_conf",  0.0)
            cat            = _get_category(expected)

            # Component 1: Classifier label match with fuzzy & synonym support
            is_match, match_affinity = _is_label_match(expected_lower, class_label)
            if is_match:
                c -= class_conf * 3.0 * match_affinity
            else:
                c += (1.0 - class_conf) * 1.5

            # Component 2: Food Category & Relative Area affinity (resolution-independent)
            total_plate_area = float(mask_h * mask_w)
            area_frac = area / max(total_plate_area, 1.0)

            if area_frac > 0.075:
                # Large area (>7.5% of plate) — main carb base (roti or rice)
                if cat in ["bread", "rice"]:
                    c -= 3.0
                    # Spatial vertical prior: roti stack usually sits on top of rice mound
                    if cat == "bread" and cy < 0.42 * mask_h:
                        c -= 1.5
                    elif cat == "rice" and cy >= 0.38 * mask_h:
                        c -= 1.5
                else:
                    c += 5.0
            elif 0.025 <= area_frac <= 0.075:
                # Medium area (2.5% to 7.5%) — well-sized curry, dal, or sabzi
                if cat == "curry":
                    c -= 2.0
                else:
                    c += 2.5
            else:
                # Small area (<2.5% of plate) — side, chutney, dessert, or salad
                if cat == "side":
                    c -= 2.5
                elif cat in ["bread", "rice"]:
                    c += 6.0
                else:
                    c += 2.0

            # Component 3: Spatial layout on standard Indian mess tray
            # Right column (cx > 0.48 * mask_w) contains the circular curry/dal wells
            if cx > 0.48 * mask_w and cat == "curry":
                c -= 1.5
            # Left column contains the large carb compartment
            if cx <= 0.48 * mask_w and cat in ["bread", "rice"]:
                c -= 1.5

            # Component 4: Compartment bbox overlap (when compartments are detected)
            if compartments:
                best_overlap = 0.0
                for comp in compartments:
                    bx, by, bw, bh = comp["bbox"]
                    overlap = float(np.sum(mask[by:by+bh, bx:bx+bw]))
                    frac    = overlap / max(float(area), 1)
                    if frac > best_overlap:
                        best_overlap = frac
                c += (1.0 - best_overlap) * 1.0

            cost[i, j] = c

    row_ind, col_ind = linear_sum_assignment(cost)
    hungarian_mapping = {r: c for r, c in zip(row_ind, col_ind)}

    # Natural multi-portion staples where duplicates are very common on mess plates
    NATURAL_DUPLICATE_CATEGORIES = {"bread", "rice", "curry", "snack", "fruit"}

    assigned_labels = []
    for i, mask_data in enumerate(food_masks):
        class_label = mask_data.get("class_label", "").lower()
        class_conf = mask_data.get("class_conf", 0.0)

        # 1. Best unconstrained candidate index for this mask
        best_j = int(np.argmin(cost[i, :n_items])) if n_items > 0 else -1
        best_label = expected_items[best_j] if best_j >= 0 else (class_label or "unknown")
        best_cost = cost[i, best_j] if best_j >= 0 else 0.0

        # 2. Hungarian unique matching candidate
        h_j = hungarian_mapping.get(i, -1)
        h_label = expected_items[h_j] if (0 <= h_j < n_items) else best_label
        h_cost = cost[i, h_j] if (0 <= h_j < n_items) else best_cost

        # 3. Determine if forcing uniqueness produces a severe mismatch
        h_cat = _get_category(h_label)
        best_cat = _get_category(best_label)
        cost_diff = h_cost - best_cost

        # If forcing uniqueness tries to turn a second portion of bread/curry into a mismatched item,
        # or if the classifier has high confidence (>0.50) matching the best label, allow the duplicate!
        if best_cat in NATURAL_DUPLICATE_CATEGORIES and cost_diff > 1.8:
            chosen_label = best_label
        elif class_conf >= 0.50 and _is_label_match(best_label, class_label)[0]:
            chosen_label = best_label
        else:
            chosen_label = h_label

        assigned_labels.append(chosen_label)

    # Return all masks and their assigned labels (never drop detected masks)
    return food_masks, assigned_labels


def _greedy_assign(
    food_masks: list[dict],
    expected_items: list[str],
    compartments: list[dict],
) -> tuple[list[dict], list[str]]:
    """Greedy 1-to-1 matching up to min(n_masks, n_items)."""
    k = min(len(food_masks), len(expected_items))
    selected_masks = [food_masks[i] for i in range(k)]
    labels         = [expected_items[i] for i in range(k)]
    return selected_masks, labels


# ── Composite confidence ──────────────────────────────────────────────────────

def _composite_confidence(
    seg_score: float,
    class_conf: float,
    depth_stability: float,
    scale_confidence: float,
) -> float:
    """
    Enhancement #10 — Composite confidence score.

    All inputs are in [0, 1].  Geometric mean used so that a single very
    poor score drags the overall result down.

    depth_stability: 1.0 if depth was stable (prior was applied),
                     otherwise raw Depth score heuristic.
    scale_confidence: 1.0 if ellipse calibration succeeded, 0.7 otherwise.
    """
    product = seg_score * class_conf * depth_stability * scale_confidence
    # Geometric mean of 4 factors
    return round(float(product ** 0.25), 4)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def estimate_food_mass(
    image_bgr: np.ndarray,
    expected_items: list[str] = None,
    plate_profile: str = None,
    meal_type: str = None,
    debug: bool = True,
    use_open_vocab: bool = True,
) -> dict:
    """
    Full enhanced pipeline:
      0. Quality gate
      1. Preprocessing & perspective warp
      2. Compartment detection & scale (+ ellipse refinement)
      3. Depth estimation (Depth Anything + smoothing)
      4. Per-compartment SAM segmentation
      5. Food classification (+ OCR-constrained re-ranking)
      6. Hungarian assignment
      7. Hybrid depth fusion (with food priors)
      8. Dynamic density → volume → mass → nutrition
      9. Composite confidence

    Args:
        image_bgr:      Input BGR image (numpy array).
        expected_items: Optional list of food names from OCR (used for
                        classification re-ranking and Hungarian assignment).
        plate_profile:  Plate type key (auto-detected when None).
        debug:          When True, saves ALL intermediates and generates HTML.

    Returns:
        {
            "food_items": [
                {
                    "name", "volume_ml", "mass_g",
                    "calories", "protein", "carbs", "fat",
                    "confidence",          # composite score
                    "class_label",         # classifier output
                    "class_confidence",    # raw classifier confidence
                },
                ...
            ],
            "confidence": float,   # mean composite confidence
        }
    """
    pipeline_t0 = time.perf_counter()

    ctx = RunContext(debug=debug)
    logger.info(f"Pipeline run {ctx.run_id} (debug={debug})")

    # ── Save original input ───────────────────────────────────────────────────
    t0 = time.perf_counter()
    ctx.save_image("input", "original.png", image_bgr)
    h, w = image_bgr.shape[:2]
    ctx.save_json("input", "metadata.json", {
        "resolution": f"{w}x{h}",
        "channels":   image_bgr.shape[2] if len(image_bgr.shape) == 3 else 1,
        "dtype":      str(image_bgr.dtype),
        "expected_items": expected_items,
        "plate_profile":  plate_profile,
        "debug": debug,
    })
    ctx.log("Input", "Original image saved",
            {"resolution": f"{w}x{h}"},
            elapsed=time.perf_counter() - t0,
            output_file="original.png")

    # ── Step 1: Preprocessing & Perspective Warp ──────────────────────────────
    ctx.log("Pipeline", "Step 1 — Preprocessing & Perspective Warp")
    t0 = time.perf_counter()
    try:
        top_down = process_image(image_bgr, ctx=ctx)
    except ValueError as qc_err:
        # Quality gate failure — surface a clean error to the API caller
        ctx.log("Pipeline", f"❌ Quality gate rejected image: {qc_err}")
        result = {
            "food_items": [],
            "confidence": 0.0,
            "error":      str(qc_err),
            "error_type": "image_quality",
        }
        ctx.save_json("volume", "results.json", result)
        ctx.generate_report()
        return result

    img_h, img_w = top_down.shape[:2]
    ctx.log("Preprocessing", "Complete",
            {"output_size": f"{img_w}x{img_h}"},
            elapsed=time.perf_counter() - t0)

    # ── Step 2: Compartments & Scale ─────────────────────────────────────────
    ctx.log("Pipeline", "Step 2 — Compartments & Scale")
    t0 = time.perf_counter()
    raw_compartments = find_compartments(top_down, ctx=ctx)
    cm_per_pixel     = compute_scale(raw_compartments, top_down.shape, plate_profile)
    scale_confidence = 0.70   # default: bbox-based calibration

    # #4 — Try ellipse-based calibration for higher accuracy (with profile support)
    ellipse_scale = calibrate_scale_from_ellipse(top_down, plate_profile=get_plate_profile(plate_profile))
    if ellipse_scale is not None:
        cm_per_pixel     = ellipse_scale
        scale_confidence = 1.00
        ctx.log("Scale Calibration", "Ellipse-based calibration succeeded",
                {"cm_per_pixel": round(cm_per_pixel, 5), "method": "ellipse"})
    else:
        ctx.log("Scale Calibration", "Fallback to bbox-based calibration",
                {"cm_per_pixel": round(cm_per_pixel, 5), "method": "bbox"})

    pixel_area_cm2 = cm_per_pixel ** 2
    compartments   = match_compartments_to_profile(raw_compartments, plate_profile)

    ctx.log("Compartment Detection", "Scale computed",
            {"cm_per_pixel": round(cm_per_pixel, 5),
             "pixel_area_cm2": round(pixel_area_cm2, 8),
             "compartments": len(compartments),
             "scale_confidence": scale_confidence},
            elapsed=time.perf_counter() - t0)

    if debug:
        ctx.save_json("features", "compartments.json", [
            {"label": c["label"], "bbox": list(c["bbox"]),
             "area_px": c["area_px"], "depth_cm": c.get("depth_cm", 2.0),
             "max_volume_ml": c.get("max_volume_ml", 200)}
            for c in compartments
        ])

    # ── Step 3: Depth Estimation ──────────────────────────────────────────────
    ctx.log("Pipeline", "Step 3 — Depth Estimation")
    t0 = time.perf_counter()
    raw_depth = estimate_depth(top_down, ctx=ctx)

    if compartments:
        plate_mask     = np.ones((img_h, img_w), dtype=bool)
        well_depth_map = np.zeros((img_h, img_w), dtype=np.float32)

        for comp in compartments:
            x, y, cw, ch = comp["bbox"]
            depth_val     = comp.get("depth_cm", 2.0)
            plate_mask[y:y+ch, x:x+cw] = False
            if comp.get("contour") is not None:
                cv2.drawContours(well_depth_map, [comp["contour"]], -1, depth_val, -1)
            else:
                well_depth_map[y:y+ch, x:x+cw] = depth_val
    else:
        # Zero compartments detected: pass None so planar fitting uses outer tray rim
        plate_mask     = None
        well_depth_map = np.zeros((img_h, img_w), dtype=np.float32)

    height_relative    = normalize_depth_to_plate(raw_depth, plate_mask, ctx=ctx)
    height_from_divider = depth_to_cm(height_relative, raw_depth, cm_per_pixel, img_w, ctx=ctx)

    ctx.log("Depth Estimation", "Complete", elapsed=time.perf_counter() - t0)

    # ── SAM 3 Food Identification & Concept Segmentation ─────────────────
    ctx.log("Pipeline", "Step 4–6 — SAM 3 Food Identification & Segmentation")
    t0 = time.perf_counter()
    from open_vocab.pipeline import OpenVocabFoodSegmenter
    ov_segmenter = OpenVocabFoodSegmenter()
    seg_output_dir = os.path.join(ctx.run_dir, "segmentation") if (ctx and ctx.run_dir) else None
    ov_res = ov_segmenter.process_plate(
        image_bgr=top_down,
        menu_items=expected_items,
        compartments=compartments,
        meal_type=meal_type or "lunch",
        output_dir=seg_output_dir,
    )
    verified_items = ov_res.get("food_items", [])
    ctx.log("SAM3", f"Identified {len(verified_items)} food items "
                    f"({ov_res.get('recognized_count', 0)} recognized, "
                    f"{ov_res.get('unlisted_count', 0)} unlisted, "
                    f"{ov_res.get('uncertain_count', 0)} uncertain)",
            output_file="segmentation/01_sam3_segmentation_overlay.png" if seg_output_dir else None,
            elapsed=time.perf_counter() - t0)

    if not verified_items:
        result = {"food_items": [], "confidence": 0.0}
        ctx.save_json("volume", "results.json", result)
        ctx.generate_report()
        return result

    food_masks = []
    assigned_names = []
    for it in verified_items:
        m = it["mask"]
        item_entry = {
            "mask": m,
            "area": int(it["area_pixels"]),
            "score": float(it.get("segmentation_confidence", 0.90)),
            "class_label": it["food_name"],
            "class_conf": float(it.get("identification_confidence", it["confidence"])),
            "class_top_k": it.get("top_k", []),
            "identification_status": it.get("identification_status", "uncertain"),
            "menu_match": it.get("menu_match", False),
            "matched_menu_item": it.get("matched_menu_item"),
            "identification_confidence": float(it.get("identification_confidence", 0.0)),
            "segmentation_confidence": float(it.get("segmentation_confidence", 0.90)),
            "association_confidence": float(it.get("association_confidence", 0.0)),
            "menu_match_confidence": float(it.get("menu_match_confidence", 0.0)),
            "diagnostics": it.get("diagnostics", {}),
            "fragment_count": it.get("fragment_count", 1),
        }
        # Assign compartment overlap
        comp_label = "unknown"
        comp_max_vol = 500
        max_overlap = -1
        for comp in compartments:
            cx2, cy2, cw2, ch2 = comp["bbox"]
            overlap = np.sum(m[cy2:cy2+ch2, cx2:cx2+cw2])
            if overlap > max_overlap:
                max_overlap = overlap
                comp_label = comp["label"]
                comp_max_vol = comp.get("max_volume_ml", 500)
        item_entry["comp_label"] = comp_label
        item_entry["comp_max_volume_ml"] = comp_max_vol

        food_masks.append(item_entry)
        assigned_names.append(it["food_name"])

    # ── Step 7: Volume & Mass Estimation ─────────────────────────────────────
    ctx.log("Pipeline", "Step 7 — Volume & Mass Estimation")
    t0         = time.perf_counter()
    food_items = []
    total_conf = 0.0
    fused_height_map = np.zeros((img_h, img_w), dtype=np.float32)

    for f_idx, item in enumerate(food_masks):
        mask       = item["mask"]
        seg_score  = item["score"]
        food_name  = assigned_names[f_idx]
        class_conf = item.get("class_conf", 0.5)

        # Compute physical volume and mass for all segmented food masks
        # (even if generic/unknown, estimate mass using standard food density so grams are never zero)
        raw_food_relief = height_relative[mask]
        well_offset = float(np.mean(well_depth_map[mask])) if (well_depth_map is not None and mask.any()) else 0.0
        comp_depth = max(well_offset, 2.0)

        # Measure true 3D surface relief variation relative to food's support base.
        # Use normalized surface variation around nominal physiological prior height
        # to ensure calibrated mass while rendering continuous 3D dome/surface relief.
        if len(raw_food_relief) > 0:
            p5 = float(np.percentile(raw_food_relief, 5))
            p95 = float(np.percentile(raw_food_relief, 95))
            span = max(p95 - p5, 0.05)
            # Normalized surface shape from base to peak (0.0 to 1.0)
            norm_relief = np.clip((raw_food_relief - p5) / span, 0.0, 1.0)
            shape_delta = norm_relief - float(np.mean(norm_relief))
        else:
            shape_delta = np.zeros_like(raw_food_relief)

        # Baseline nominal calibrated physiological height from prior
        k_food = food_name.strip().lower()
        prior_tuple = FOOD_HEIGHT_PRIORS.get(k_food)
        if prior_tuple is None:
            for pk, pv in FOOD_HEIGHT_PRIORS.items():
                if pk in k_food or k_food in pk:
                    prior_tuple = pv
                    break
        if prior_tuple is not None:
            nominal_h = float(prior_tuple[0] + 0.35 * (prior_tuple[1] - prior_tuple[0]))
        else:
            nominal_h = 1.5

        if _is_mound_food(food_name):
            # Rice mound dome: gentle dome peaking ~0.20-0.45cm above rim
            food_heights_cm = np.clip(0.20 + shape_delta * 0.35, 0.05, 0.90)
        elif _is_planar_food(food_name):
            food_heights_cm = np.clip(nominal_h + shape_delta * 0.30, 0.1, 1.5)
        elif _is_sliced_salad_food(food_name):
            food_heights_cm = np.clip(nominal_h + shape_delta * 0.25, 0.3, 1.8)
        elif _is_condiment_food(food_name):
            food_heights_cm = np.clip(nominal_h + shape_delta * 0.30, 0.4, 2.0)
        else:
            # Curry / gravy / sabzi: bowl surface ripple and chunk relief
            food_heights_cm = np.clip(nominal_h + shape_delta * 0.45, 0.2, 3.5)

        # Continuous 3D topographic relief map for visualization:
        eff_well_offset = max(well_offset, 1.6) if (_is_mound_food(food_name) or _is_liquid_food(food_name)) else well_offset
        fused_height_map[mask] = food_heights_cm + (eff_well_offset if not _is_sliced_salad_food(food_name) else 0.0)

        # Add the physical well depth offset (how deep the compartment is)
        pixel_heights = np.clip(food_heights_cm + eff_well_offset, 0.05, 8.0)

        # Depth stability: 1.0 if prior was found, 0.75 otherwise
        food_key = food_name.strip().lower()
        has_prior = (food_key in FOOD_HEIGHT_PRIORS) or any(
            k in food_key or food_key in k for k in FOOD_HEIGHT_PRIORS
        )
        depth_stability = 1.0 if has_prior else 0.75

        # ── Physical Geometric Volume Calculation ─────────────────────────
        area_cm2 = float(np.sum(mask) * pixel_area_cm2)
        comp_max_vol = item.get("comp_max_volume_ml", 500)
        if area_cm2 <= 85.0 and comp_max_vol >= 400:
            # Standard small circular/square mess compartment capacity (~150-180ml)
            comp_max_vol = area_cm2 * 2.2 * 0.95

        if _is_planar_food(food_name):
            # Planar archetype (roti/chapati): does NOT fill compartment depth.
            # Volume = Surface Area × Calibrated Sheet Thickness × Layer Count.
            unit_thickness = _get_planar_thickness_cm(food_name)
            # Estimate stack layers from detected height above plate
            layers = max(1.0, float(np.median(food_heights_cm)) / unit_thickness)
            layers = min(layers, 3.5)  # stack limit
            volume_ml = area_cm2 * unit_thickness * layers

        elif _is_sliced_salad_food(food_name):
            # Salad slice archetype (cucumber/tomato/onion/salad slices):
            # Discrete planar slices laid flat or overlapping in compartment.
            # Physical Volume = Area × Calibrated Slice Bed Thickness (0.65 - 0.85 cm)
            slice_thickness = _get_salad_slice_thickness_cm(food_name)
            eff_height = max(slice_thickness, float(np.median(food_heights_cm)))
            eff_height = min(eff_height, 1.6)  # realistic max cucumber stack on plate
            volume_ml = area_cm2 * eff_height

        elif _is_condiment_food(food_name):
            # Condiment / dollop archetype (pickle / achar / chutney):
            # Concentrated dollop (0.8 - 1.2 cm thick)
            condiment_h = float(np.clip(np.median(food_heights_cm), 0.75, 1.35))
            volume_ml = area_cm2 * condiment_h * 0.85

        elif _is_liquid_food(food_name):
            # Liquid archetype (dal/sambar/curd/seviyan): conforms to compartment well
            # Liquid surface cannot rise significantly above the tray rim.
            well_depth = max(well_offset, 2.0)
            avg_h = float(np.clip(np.mean(food_heights_cm), 0.0, well_depth))
            fill_ratio = float(np.clip(0.50 + 0.30 * (avg_h / well_depth), 0.40, 0.90))
            # Frustum taper factor for molded circular/rectangular wells ≈ 0.88
            volume_ml = area_cm2 * (well_depth * fill_ratio) * 0.88

        elif _is_mound_food(food_name):
            # Mound archetype (rice/pulao): fills base well + curved dome above rim
            well_depth = max(well_offset, 1.6)
            base_vol = area_cm2 * (well_depth * 0.78)
            mound_vol = float(np.sum(food_heights_cm) * pixel_area_cm2) * 0.85
            volume_ml = base_vol + mound_vol

        else:
            # Chunk/curry archetype (sabzi/paneer/chicken):
            # In a compartment well, volume is bounded by physical well depth
            well_depth = max(well_offset, 2.0)
            volume_ml = float(np.sum(food_heights_cm) * pixel_area_cm2) * 0.82
            volume_ml = min(volume_ml, area_cm2 * (well_depth * 0.90))

        # Cap volume to the physical compartment capacity
        volume_ml = min(volume_ml, comp_max_vol)

        # Extract mask crop for visual density analysis
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if rows.any() and cols.any():
            r0, r1 = np.where(rows)[0][[0, -1]]
            c0, c1 = np.where(cols)[0][[0, -1]]
            mask_region = top_down[r0:r1+1, c0:c1+1].copy()
            mask_region[~mask[r0:r1+1, c0:c1+1]] = 127
        else:
            mask_region = None

        # #6 — Dynamic density
        density = get_dynamic_density(food_name, mask_region)
        mass_g  = volume_ml * density

        # Macros
        m        = get_macros(food_name)
        calories = mass_g * m["calories"]
        protein  = mass_g * m["protein"]
        carbs    = mass_g * m["carbs"]
        fat      = mass_g * m["fat"]

        # Ensure macro consistency
        macro_cals = (protein * 4.0) + (carbs * 4.0) + (fat * 9.0)
        if macro_cals > calories:
            calories = macro_cals
        if mass_g >= 1.0 and calories < 1.0:
            calories = 1.0

        # #10 — Composite confidence
        conf = _composite_confidence(
            seg_score        = seg_score,
            class_conf       = class_conf,
            depth_stability  = depth_stability,
            scale_confidence = scale_confidence,
        )
        total_conf += conf

        food_item = {
            "name":             food_name,
            "volume_ml":        round(volume_ml, 1),
            "mass_g":           round(mass_g, 1),
            "calories":         round(calories, 1),
            "protein":          round(protein, 1),
            "carbs":            round(carbs, 1),
            "fat":              round(fat, 1),
            "confidence":       round(conf, 4),
            "class_label":      item.get("class_label", "unknown"),
            "class_confidence": round(class_conf, 4),
            "top_k":            item.get("class_top_k", []),
            # --- Open-World Additive Verification Fields ---
            "identification_status": item.get("identification_status", "uncertain"),
            "menu_match":            item.get("menu_match", False),
            "matched_menu_item":     item.get("matched_menu_item"),
            "identification_confidence": item.get("identification_confidence", round(class_conf, 4)),
            "segmentation_confidence":   item.get("segmentation_confidence", round(seg_score, 4)),
            "association_confidence":    item.get("association_confidence", 0.0),
            "menu_match_confidence":     item.get("menu_match_confidence", 0.0),
            "depth_confidence":          depth_stability,
            "scale_confidence":          scale_confidence,
            "diagnostics":               item.get("diagnostics", {}),
            "fragment_count":            item.get("fragment_count", 1),
        }
        food_items.append(food_item)

        if debug:
            ctx.save_json("features", f"item_{f_idx+1}_{food_name}.json", {
                "item_id":              f"{food_name}_{f_idx+1}",
                "area_pixels":          int(item["area"]),
                "estimated_height_cm":  round(float(np.mean(pixel_heights)), 3),
                "volume_estimate_ml":   round(volume_ml, 1),
                "density":              density,
                "mass_g":               round(mass_g, 1),
                "class_label":          item.get("class_label", "unknown"),
                "class_confidence":     round(class_conf, 4),
                "depth_stability":      depth_stability,
                "scale_confidence":     scale_confidence,
                "composite_confidence": round(conf, 4),
                "prior_applied":        has_prior,
                "diagnostics":          item.get("diagnostics", {}),
                "fragment_count":       item.get("fragment_count", 1),
            })

    avg_confidence = total_conf / len(food_masks) if food_masks else 0.0
    ctx.log("Volume Estimation", f"Computed mass for {len(food_items)} items",
            {"total_items": len(food_items)},
            elapsed=time.perf_counter() - t0)

    # ── Height map visualisation ──────────────────────────────────────────────
    if debug:
        idx = ctx.next_index("volume")
        ctx.save_npy("volume", f"{idx:02d}_fused_height_map.npy", fused_height_map)

        # Render true fused 2D height map preserving food internal curvature
        food_mask_all = (fused_height_map > 0)
        h_colored = np.zeros((img_h, img_w, 3), dtype=np.uint8)
        if food_mask_all.any():
            food_vals = fused_height_map[food_mask_all]
            h_min = float(np.percentile(food_vals, 1))
            h_max = float(np.percentile(food_vals, 99))
            spread = max(h_max - h_min, 0.1)
            h_norm_2d = np.clip((fused_height_map - h_min) / spread * 255.0, 0, 255).astype(np.uint8)
            turbo = cv2.applyColorMap(h_norm_2d, cv2.COLORMAP_TURBO)
            h_colored[food_mask_all] = turbo[food_mask_all]
            # Subtle dark tone for non-food background
            h_colored[~food_mask_all] = [20, 20, 25]
        ctx.save_image("volume", f"{idx:02d}_height_map.png", h_colored)

    # ── Final annotated overlay ───────────────────────────────────────────────
    annotated = top_down.copy()
    colors    = [
        (66, 133, 244), (52, 168, 83),  (234, 67, 53),
        (251, 188, 4),  (154, 78, 174), (0, 172, 193),
        (255, 112, 67), (121, 134, 203),
    ]
    for f_idx, item in enumerate(food_masks):
        mask_bool   = item["mask"]
        color       = colors[f_idx % len(colors)]
        color_layer = np.zeros_like(annotated)
        color_layer[mask_bool] = color
        annotated = cv2.addWeighted(annotated, 1.0, color_layer, 0.35, 0)

        mask_u8 = mask_bool.astype(np.uint8)
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(annotated, contours, -1, color, 2)

        M = cv2.moments(mask_u8)
        if M["m00"] > 0:
            cx_pos = int(M["m10"] / M["m00"])
            cy_pos = int(M["m01"] / M["m00"])
            fi     = food_items[f_idx]
            label  = f"{fi['name']}: {fi['mass_g']}g ({fi['confidence']:.2f})"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(annotated,
                          (cx_pos - 4, cy_pos - th - 6),
                          (cx_pos + tw + 4, cy_pos + 4),
                          (0, 0, 0), -1)
            cv2.putText(annotated, label,
                        (cx_pos, cy_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 2)

    idx = ctx.next_index("volume")
    ctx.save_image("volume", f"{idx:02d}_final_annotated.png", annotated)

    # ── Aggregate multiple detections of the same food item ──────────────────
    # Combines multi-instance items (e.g. 5 cucumber slices, multiple bread pieces)
    aggregated_items: dict[str, dict[str, Any]] = {}
    for it in food_items:
        key = it["name"].strip().lower()
        if key not in aggregated_items:
            item_copy = dict(it)
            item_copy["food_name"] = it.get("name") or it.get("food_name", "Unknown")
            item_copy["instance_count"] = 1
            aggregated_items[key] = item_copy
        else:
            agg = aggregated_items[key]
            agg["volume_ml"] = round(agg["volume_ml"] + it["volume_ml"], 1)
            agg["mass_g"] = round(agg["mass_g"] + it["mass_g"], 1)
            agg["calories"] = round(agg["calories"] + it["calories"], 1)
            agg["protein"] = round(agg["protein"] + it["protein"], 1)
            agg["carbs"] = round(agg["carbs"] + it["carbs"], 1)
            agg["fat"] = round(agg["fat"] + it["fat"], 1)
            agg["confidence"] = max(agg["confidence"], it["confidence"])
            agg["instance_count"] = agg.get("instance_count", 1) + 1

    combined_list = list(aggregated_items.values())
    # Omit negligible 0g micro-noise detections if substantial food items exist
    substantial = [it for it in combined_list if it["mass_g"] >= 1.0 or it["calories"] >= 1.0]
    final_food_items = substantial if substantial else combined_list

    # ── Results JSON ─────────────────────────────────────────────────────────
    result = {
        "food_items": final_food_items,
        "raw_detections": food_items,
        "confidence": round(avg_confidence, 4),
    }
    ctx.save_json("volume", "results.json", result)

    # ── Pipeline complete ─────────────────────────────────────────────────────
    pipeline_elapsed = time.perf_counter() - pipeline_t0
    ctx.log("Pipeline", "✅ Pipeline complete",
            {"total_food_items":  len(food_items),
             "avg_confidence":    round(avg_confidence, 4),
             "scale_method":      "ellipse" if ellipse_scale else "bbox"},
            elapsed=pipeline_elapsed)

    report_path = ctx.generate_report()
    logger.info(f"Report: {report_path}")

    result["_debug"] = {
        "run_id":           ctx.run_id,
        "run_dir":          ctx.run_dir,
        "report":           report_path,
        "pipeline_time_s":  round(pipeline_elapsed, 3),
        "scale_method":     "ellipse" if ellipse_scale else "bbox",
    }

    return result
