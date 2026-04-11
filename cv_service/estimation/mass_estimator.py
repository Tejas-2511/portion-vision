"""
End-to-end mass estimation pipeline.

Orchestrates all enhancements:

  #1  Hybrid depth (MiDaS + food geometric priors)
  #2  Food classification via MobileNetV3
  #3  OCR→CV fusion (OCR labels constrain classifier)
  #4  Ellipse-based scale calibration
  #5  Depth smoothing (inside depth_estimator.estimate_depth)
  #6  Dynamic density mapping
  #7  Input quality gate (inside preprocess.process_image)
  #8  Per-compartment SAM segmentation
  #9  Hungarian algorithm optimal mask↔label assignment
  #10 Composite confidence score

When debug=True, creates a timestamped run directory and saves every
intermediate image, NumPy array, and a final HTML report.
"""

from __future__ import annotations

import time
import logging
import cv2
import numpy as np

from diagnostics.run_context import RunContext
from image_processing.preprocess import process_image
from image_processing.detection import (
    find_compartments,
    compute_scale,
    match_compartments_to_profile,
)
from segmentation.sam_segmenter import (
    segment_per_compartment_sam,
    segment_full_image_sam,
)
from depth.depth_estimator import (
    estimate_depth,
    normalize_depth_to_plate,
    depth_to_cm,
    apply_food_height_prior,
    calibrate_scale_from_ellipse,
)
from classification.classifier import classify_mask_region
from config.density_map import get_density, get_dynamic_density
from config.macro_map import get_macros

logger = logging.getLogger(__name__)


# ── Hungarian assignment helper ───────────────────────────────────────────────

def _hungarian_assign(
    food_masks: list[dict],
    expected_items: list[str],
    compartments: list[dict],
) -> list[str]:
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

    for i, mask_data in enumerate(food_masks):
        mask     = mask_data["mask"]
        mask_h, mask_w = mask.shape

        for j, expected in enumerate(expected_items):
            c = 0.0

            # Component 1: compartment label mismatch
            comp_label = mask_data.get("comp_label", "")
            if expected.lower() not in comp_label.lower():
                c += 1.0

            # Component 2: classifier confidence mismatch
            class_label = mask_data.get("class_label", "").lower()
            expected_lower = expected.lower()
            class_conf  = mask_data.get("class_conf",  0.0)
            if class_label not in expected_lower and expected_lower not in class_label:
                c += (1.0 - class_conf) * 2.0

            # Component 3: spatial — penalise masks far from compartments
            # (already handled by per-compartment segmentation; lighter weight here)
            best_overlap = 0.0
            for comp in compartments:
                cx, cy, cw, ch = comp["bbox"]
                overlap = float(np.sum(mask[cy:cy+ch, cx:cx+cw]))
                frac    = overlap / max(float(mask.sum()), 1)
                if frac > best_overlap:
                    best_overlap = frac
            c += (1.0 - best_overlap) * 1.0

            cost[i, j] = c

    row_ind, col_ind = linear_sum_assignment(cost)

    labels = []
    for i in range(n_masks):
        labels.append(food_masks[i].get("class_label", "unknown"))
        
    for r, c in zip(row_ind, col_ind):
        if r < n_masks and c < n_items:
            labels[r] = expected_items[c]

    return labels


def _greedy_assign(
    food_masks: list[dict],
    expected_items: list[str],
    compartments: list[dict],
) -> list[str]:
    """Simple greedy fallback (original behaviour)."""
    labels = []
    for f_idx, mask_data in enumerate(food_masks):
        if f_idx < len(expected_items):
            labels.append(expected_items[f_idx])
        else:
            labels.append(mask_data.get("class_label", "unknown"))
    return labels


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
                     otherwise raw MiDaS score heuristic.
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
    debug: bool = False,
) -> dict:
    """
    Full enhanced pipeline:
      0. Quality gate
      1. Preprocessing & perspective warp
      2. Compartment detection & scale (+ ellipse refinement)
      3. Depth estimation (MiDaS + smoothing)
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

    # #4 — Try ellipse-based calibration for higher accuracy
    ellipse_scale = calibrate_scale_from_ellipse(top_down)
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

    height_relative    = normalize_depth_to_plate(raw_depth, plate_mask, ctx=ctx)
    height_from_divider = depth_to_cm(height_relative, raw_depth, cm_per_pixel, img_w, ctx=ctx)

    ctx.log("Depth Estimation", "Complete", elapsed=time.perf_counter() - t0)

    # ── Step 4: Segmentation ──────────────────────────────────────────────────
    ctx.log("Pipeline", "Step 4 — Segmentation")
    t0 = time.perf_counter()

    # #8 — prefer per-compartment mode when compartments were detected
    if compartments:
        food_masks = segment_per_compartment_sam(top_down, compartments, ctx=ctx)
    else:
        food_masks = segment_full_image_sam(top_down, ctx=ctx)

    if not food_masks:
        ctx.log("Segmentation", "No food items detected",
                elapsed=time.perf_counter() - t0)
        result = {"food_items": [], "confidence": 0.0}
        ctx.save_json("volume", "results.json", result)
        ctx.generate_report()
        return result

    ctx.log("Segmentation", f"{len(food_masks)} food items found",
            elapsed=time.perf_counter() - t0)

    # Sort masks by area (largest first)
    food_masks = sorted(food_masks, key=lambda m: m["area"], reverse=True)

    # ── Step 5: Classification & OCR Fusion ──────────────────────────────────
    ctx.log("Pipeline", "Step 5 — Food Classification (OCR-constrained)")
    t0 = time.perf_counter()

    for f_idx, item in enumerate(food_masks):
        # Determine which compartment this mask belongs to
        comp_label  = "unknown"
        max_overlap = -1
        for comp in compartments:
            cx2, cy2, cw2, ch2 = comp["bbox"]
            overlap = np.sum(item["mask"][cy2:cy2+ch2, cx2:cx2+cw2])
            if overlap > max_overlap:
                max_overlap = overlap
                comp_label  = comp["label"]

        item["comp_label"] = comp_label

        # #2/#3 — Classify with OCR label constraint
        cls_result           = classify_mask_region(
            top_down, item["mask"],
            allowed_labels=expected_items,
            top_k=3,
        )
        item["class_label"] = cls_result["label"]
        item["class_conf"]  = cls_result["confidence"]
        item["class_top_k"] = cls_result["top_k"]

    ctx.log("Classification", "Complete",
            {"n_items": len(food_masks),
             "ocr_labels_used": bool(expected_items)},
            elapsed=time.perf_counter() - t0)

    # ── Step 6: Optimal Assignment (Hungarian) ────────────────────────────────
    ctx.log("Pipeline", "Step 6 — Hungarian Label Assignment")
    if expected_items:
        assigned_names = _hungarian_assign(food_masks, expected_items, compartments)
    else:
        # No expected list — use classifier output directly
        assigned_names = [
            item.get("class_label", "unknown")
            for item in food_masks
        ]

    # ── Step 7: Volume & Mass Estimation ─────────────────────────────────────
    ctx.log("Pipeline", "Step 7 — Volume & Mass Estimation")
    t0         = time.perf_counter()
    food_items = []
    total_conf = 0.0

    for f_idx, item in enumerate(food_masks):
        mask       = item["mask"]
        seg_score  = item["score"]
        food_name  = assigned_names[f_idx]
        class_conf = item.get("class_conf", 0.5)

        # Raw per-pixel heights
        pixel_heights = height_from_divider[mask] + well_depth_map[mask]

        # #1 — Fuse with food-specific geometric prior
        food_heights_fused = apply_food_height_prior(pixel_heights, food_name)
        pixel_heights      = np.clip(food_heights_fused, 0.1, 10.0)

        # #5 — depth stability: 1.0 if prior was found (clamp changed range)
        from depth.depth_estimator import FOOD_HEIGHT_PRIORS
        food_key = food_name.strip().lower()
        has_prior = (food_key in FOOD_HEIGHT_PRIORS) or any(
            k in food_key or food_key in k for k in FOOD_HEIGHT_PRIORS
        )
        depth_stability = 1.0 if has_prior else 0.65

        volume_ml = float(np.sum(pixel_heights) * pixel_area_cm2)

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
            })

    avg_confidence = total_conf / len(food_masks) if food_masks else 0.0
    ctx.log("Volume Estimation", f"Computed mass for {len(food_items)} items",
            {"total_items": len(food_items)},
            elapsed=time.perf_counter() - t0)

    # ── Height map visualisation ──────────────────────────────────────────────
    if debug:
        h_vis     = np.clip(height_from_divider, 0, 10)
        h_norm    = cv2.normalize(h_vis, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        h_colored = cv2.applyColorMap(h_norm, cv2.COLORMAP_TURBO)
        idx = ctx.next_index("volume")
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

    # ── Results JSON ─────────────────────────────────────────────────────────
    result = {
        "food_items": food_items,
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
