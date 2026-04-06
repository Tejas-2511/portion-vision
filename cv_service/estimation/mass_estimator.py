"""
End-to-end mass estimation pipeline.

Orchestrates: Detection → Scale → Depth → Segmentation → Volume → Mass

When debug=True, creates a timestamped run directory and saves every
intermediate image, NumPy array, and a final HTML report.
"""

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
from segmentation.sam_segmenter import segment_full_image_sam
from depth.depth_estimator import estimate_depth, normalize_depth_to_plate, depth_to_cm
from config.density_map import get_density
from config.macro_map import get_macros

logger = logging.getLogger(__name__)


def estimate_food_mass(
    image_bgr: np.ndarray,
    expected_items: list[str] = None,
    plate_profile: str = None,
    debug: bool = False,
) -> dict:
    """
    Full pipeline: Preprocessing → Compartments → Depth → Segmentation → Volume → Mass.

    Args:
        image_bgr:      Input BGR image (numpy array).
        expected_items:  Optional list of food names for labeling.
        plate_profile:   Plate type key (defaults to auto-detect).
        debug:           When True, saves ALL intermediates to outputs/ and
                         generates an HTML report. When False, saves only
                         the final annotated image and results.json.

    Returns:
        dict with "food_items" and "confidence" keys.
    """
    pipeline_t0 = time.perf_counter()

    # ── Initialize run context ───────────────────────────────────────────
    ctx = RunContext(debug=debug)
    logger.info(f"Pipeline run {ctx.run_id} (debug={debug})")

    # ── Save original input ──────────────────────────────────────────────
    t0 = time.perf_counter()
    ctx.save_image("input", "original.png", image_bgr)
    h, w = image_bgr.shape[:2]
    ctx.save_json("input", "metadata.json", {
        "resolution": f"{w}x{h}",
        "channels": image_bgr.shape[2] if len(image_bgr.shape) == 3 else 1,
        "dtype": str(image_bgr.dtype),
        "expected_items": expected_items,
        "plate_profile": plate_profile,
        "debug": debug,
    })
    ctx.log("Input", "Original image saved",
            {"resolution": f"{w}x{h}"},
            elapsed=time.perf_counter() - t0,
            output_file="original.png")

    # ── Step 1: Preprocessing & Perspective Warp ─────────────────────────
    ctx.log("Pipeline", "Step 1 — Preprocessing & Perspective Warp")
    t0 = time.perf_counter()
    top_down = process_image(image_bgr, ctx=ctx)
    img_h, img_w = top_down.shape[:2]
    ctx.log("Preprocessing", "Complete",
            {"output_size": f"{img_w}x{img_h}"},
            elapsed=time.perf_counter() - t0)

    # ── Step 2: Detecting compartments & Scale ───────────────────────────
    ctx.log("Pipeline", "Step 2 — Detecting compartments & Scale")
    t0 = time.perf_counter()
    raw_compartments = find_compartments(top_down, ctx=ctx)
    cm_per_pixel = compute_scale(raw_compartments, top_down.shape, plate_profile)
    pixel_area_cm2 = cm_per_pixel ** 2

    compartments = match_compartments_to_profile(raw_compartments, plate_profile)
    elapsed_comp = time.perf_counter() - t0
    ctx.log("Compartment Detection", "Scale computed",
            {"cm_per_pixel": round(cm_per_pixel, 5),
             "pixel_area_cm2": round(pixel_area_cm2, 8),
             "compartments": len(compartments)},
            elapsed=elapsed_comp)

    # Save compartment labels as JSON (features)
    comp_data = []
    for c in compartments:
        comp_data.append({
            "label": c["label"],
            "bbox": list(c["bbox"]),
            "area_px": c["area_px"],
            "depth_cm": c.get("depth_cm", 2.0),
            "max_volume_ml": c.get("max_volume_ml", 200),
        })
    if debug:
        ctx.save_json("features", "compartments.json", comp_data)

    # ── Step 3: Depth Estimation ─────────────────────────────────────────
    ctx.log("Pipeline", "Step 3 — Depth Estimation")
    t0 = time.perf_counter()
    raw_depth = estimate_depth(top_down, ctx=ctx)

    # Build a rim/divider mask for baseline
    plate_mask = np.ones((img_h, img_w), dtype=bool)
    # Also build a per-pixel well depth map
    well_depth_map = np.zeros((img_h, img_w), dtype=np.float32)

    for comp in compartments:
        x, y, w, h = comp["bbox"]
        depth = comp.get("depth_cm", 2.0)
        plate_mask[y:y+h, x:x+w] = False

        if comp.get("contour") is not None:
            cv2.drawContours(well_depth_map, [comp["contour"]], -1, depth, -1)
        else:
            # Fallback to bbox if contour detection missed the exact shape
            well_depth_map[y:y+h, x:x+w] = depth

    height_relative = normalize_depth_to_plate(raw_depth, plate_mask, ctx=ctx)
    height_from_divider = depth_to_cm(height_relative, raw_depth, cm_per_pixel, img_w, ctx=ctx)

    elapsed_depth = time.perf_counter() - t0
    ctx.log("Depth Estimation", "Complete",
            elapsed=elapsed_depth)

    # ── Step 4: Full-Plate Segmentation ──────────────────────────────────
    ctx.log("Pipeline", "Step 4 — Full-Plate Segmentation")
    t0 = time.perf_counter()
    food_masks = segment_full_image_sam(top_down, ctx=ctx)
    elapsed_seg = time.perf_counter() - t0

    if not food_masks:
        ctx.log("Segmentation", "No food items detected", elapsed=elapsed_seg)
        result = {"food_items": [], "confidence": 0.0}
        # Still save what we can
        ctx.save_json("volume", "results.json", result)
        ctx.generate_report()
        return result

    ctx.log("Segmentation", f"{len(food_masks)} food items found",
            elapsed=elapsed_seg)

    # ── Step 5: Volume & Mass Estimation ─────────────────────────────────
    ctx.log("Pipeline", "Step 5 — Volume & Mass estimation")
    t0 = time.perf_counter()
    food_items = []
    total_conf = 0.0

    for f_idx, item in enumerate(food_masks):
        mask = item["mask"]
        score = item["score"]
        total_conf += score

        # Calc volume using per-pixel well depth
        pixel_heights = height_from_divider[mask] + well_depth_map[mask]
        pixel_heights = np.clip(pixel_heights, 0.1, 10.0)  # avoid impossible numbers
        
        volume_ml = np.sum(pixel_heights) * pixel_area_cm2

        # Identify which compartment this item belongs to (by majority area)
        best_label = "unknown"
        max_overlap = -1
        
        for comp in compartments:
            cx, cy, cw, ch = comp["bbox"]
            overlap = np.sum(mask[cy:cy+ch, cx:cx+cw])
            if overlap > max_overlap:
                max_overlap = overlap
                best_label = comp["label"]
        
        # Override name if expected_items provided
        food_name = best_label
        if expected_items and f_idx < len(expected_items):
            food_name = expected_items[f_idx]

        density = get_density(food_name)
        mass_g = volume_ml * density

        # Calculate macros
        m = get_macros(food_name)
        calories = mass_g * m["calories"]
        protein = mass_g * m["protein"]
        carbs = mass_g * m["carbs"]
        fat = mass_g * m["fat"]

        food_item = {
            "name": food_name,
            "volume_ml": round(float(volume_ml), 1),
            "mass_g": round(float(mass_g), 1),
            "calories": round(float(calories), 1),
            "protein": round(float(protein), 1),
            "carbs": round(float(carbs), 1),
            "fat": round(float(fat), 1),
            "confidence": round(score, 2),
        }
        food_items.append(food_item)

        # Save per-item features
        if debug:
            ctx.save_json("features", f"item_{f_idx+1}_{food_name}.json", {
                "item_id": f"{food_name}_{f_idx+1}",
                "area_pixels": int(item["area"]),
                "estimated_height_cm": round(float(np.mean(pixel_heights)), 3),
                "volume_estimate_ml": round(float(volume_ml), 1),
                "density": density,
                "mass_g": round(float(mass_g), 1),
            })

    elapsed_vol = time.perf_counter() - t0

    avg_confidence = total_conf / len(food_masks)

    result = {
        "food_items": food_items,
        "confidence": round(avg_confidence, 2),
    }

    ctx.log("Volume Estimation", f"Computed mass for {len(food_items)} items",
            {"total_items": len(food_items)},
            elapsed=elapsed_vol)

    # ── Save height map visualization ────────────────────────────────────
    if debug:
        # Pixel-height heatmap
        h_vis = np.clip(height_from_divider, 0, 10)
        h_norm = cv2.normalize(h_vis, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        h_colored = cv2.applyColorMap(h_norm, cv2.COLORMAP_TURBO)
        idx = ctx.next_index("volume")
        ctx.save_image("volume", f"{idx:02d}_height_map.png", h_colored)

    # ── Final annotated overlay (always saved) ───────────────────────────
    annotated = top_down.copy()
    colors = [
        (66, 133, 244), (52, 168, 83), (234, 67, 53),
        (251, 188, 4), (154, 78, 174), (0, 172, 193),
        (255, 112, 67), (121, 134, 203),
    ]
    for f_idx, item in enumerate(food_masks):
        mask_bool = item["mask"]
        color = colors[f_idx % len(colors)]
        color_layer = np.zeros_like(annotated)
        color_layer[mask_bool] = color
        annotated = cv2.addWeighted(annotated, 1.0, color_layer, 0.35, 0)

        # Draw contour
        mask_u8 = mask_bool.astype(np.uint8)
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(annotated, contours, -1, color, 2)

        # Label with name + grams
        M = cv2.moments(mask_u8)
        if M["m00"] > 0:
            cx_pos = int(M["m10"] / M["m00"])
            cy_pos = int(M["m01"] / M["m00"])
            fi = food_items[f_idx]
            label = f"{fi['name']}: {fi['mass_g']}g"
            # Background rectangle for readability
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(annotated,
                          (cx_pos - 4, cy_pos - th - 6),
                          (cx_pos + tw + 4, cy_pos + 4),
                          (0, 0, 0), -1)
            cv2.putText(annotated, label,
                        (cx_pos, cy_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255), 2)

    idx = ctx.next_index("volume")
    ctx.save_image("volume", f"{idx:02d}_final_annotated.png", annotated)

    # ── Save results JSON (always) ───────────────────────────────────────
    ctx.save_json("volume", "results.json", result)

    # ── Pipeline complete ────────────────────────────────────────────────
    pipeline_elapsed = time.perf_counter() - pipeline_t0
    ctx.log("Pipeline", "✅ Pipeline complete",
            {"total_food_items": len(food_items),
             "avg_confidence": round(avg_confidence, 2)},
            elapsed=pipeline_elapsed)

    # Generate HTML report
    report_path = ctx.generate_report()
    logger.info(f"Report: {report_path}")

    # Attach run metadata to the result
    result["_debug"] = {
        "run_id": ctx.run_id,
        "run_dir": ctx.run_dir,
        "report": report_path,
        "pipeline_time_s": round(pipeline_elapsed, 3),
    }

    return result
