"""
PortionVision - Food Identification & Segmentation Visualizer.

Pure Python command-line visual inspection tool (no web framework / no Streamlit).
Runs SAM 3 concept grounding and food-aware segmentation.

Outputs:
  cv_service/outputs/open_vocab_<timestamp>/
    - annotated.png: Mask contours, bounding boxes, labels, and summary banner
    - results.json: Full structured output with modular confidence decomposition
    - crops/: Individual cropped dish images
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys
import time
import cv2
import numpy as np

# Ensure cv_service root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from open_vocab.pipeline import OpenVocabFoodSegmenter


def find_default_image() -> str | None:
    """Find a candidate sample image in cv_service/outputs/ or plate-photos/."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    patterns = [
        os.path.join(base_dir, "outputs", "*", "input", "original.png"),
        os.path.join(base_dir, "outputs", "*", "input", "*.jpg"),
        os.path.join(base_dir, "plate-photos", "*.jpg"),
        os.path.join(base_dir, "plate-photos", "*.png"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            matches.sort(key=os.path.getmtime, reverse=True)
            return matches[0]
    return None


def get_color_for_status(status: str) -> tuple[int, int, int]:
    """
    BGR colors:
      - recognized (menu match): Green
      - unlisted (extra food item): Bright Orange/Amber
      - uncertain (low confidence / ambiguous): Red
    """
    if status == "recognized":
        return (60, 200, 60)   # Vibrant Green
    elif status == "unlisted":
        return (0, 140, 255)   # Vibrant Orange
    else:
        return (60, 60, 230)   # Red


def draw_detection_overlay(
    image_bgr: np.ndarray,
    food_items: list[dict],
    stats: dict
) -> np.ndarray:
    """Renders segmentation masks, colored contours, bounding boxes, and label tags."""
    h, w = image_bgr.shape[:2]
    overlay = image_bgr.copy()

    palette = [
        (40, 180, 40), (0, 165, 255), (200, 50, 50),
        (255, 120, 0), (180, 40, 200), (0, 220, 220),
        (220, 180, 30), (160, 120, 255), (100, 220, 120)
    ]

    # 1. Alpha-blend instance masks
    mask_layer = image_bgr.copy()
    for idx, item in enumerate(food_items):
        mask = item.get("mask")
        if mask is None:
            continue
        mask_bool = mask.astype(bool) if isinstance(mask, np.ndarray) else np.zeros((h, w), dtype=bool)
        color = palette[idx % len(palette)]
        mask_layer[mask_bool] = color

    cv2.addWeighted(mask_layer, 0.45, overlay, 0.55, 0, overlay)

    # 2. Draw contours, bounding boxes, and badges
    for idx, item in enumerate(food_items, 1):
        status = item.get("identification_status", "uncertain")
        status_color = get_color_for_status(status)
        mask = item.get("mask")

        if mask is not None and isinstance(mask, np.ndarray):
            mask_u8 = (mask.astype(np.uint8)) * 255
            contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, status_color, 2)

        # Bounding Box
        bbox = item.get("bounding_box", [0, 0, 0, 0])
        bx, by, bw, bh = bbox
        cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), status_color, 2)

        # Label Text & Badge
        name = item.get("food_name", "unknown")
        conf = item.get("confidence", 0.0)
        prefix = ""
        if status == "unlisted":
            prefix = "[!] "
        elif status == "uncertain":
            prefix = "[?] "

        label = f"{idx}. {prefix}{name} ({int(conf * 100)}%)"

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        badge_y1 = max(0, by - th - 8)
        badge_y2 = by
        badge_x1 = bx
        badge_x2 = min(w, bx + tw + 10)

        cv2.rectangle(overlay, (badge_x1, badge_y1), (badge_x2, badge_y2), status_color, -1)
        cv2.putText(
            overlay,
            label,
            (badge_x1 + 5, badge_y2 - 4),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    # 3. Top Banner with Global Summary
    banner_height = 42
    banner = np.zeros((banner_height, w, 3), dtype=np.uint8)
    banner[:] = (30, 30, 30)

    summary_text = (
        f"Detected: {stats.get('total_items', len(food_items))} items  |  "
        f"Recognized: {stats.get('recognized_count', 0)}  |  "
        f"Unlisted: {stats.get('unlisted_count', 0)}  |  "
        f"Uncertain: {stats.get('uncertain_count', 0)}  |  "
        f"Time: {stats.get('elapsed_seconds', 0.0):.2f}s"
    )
    cv2.putText(
        banner,
        summary_text,
        (15, 27),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (240, 240, 240),
        1,
        cv2.LINE_AA,
    )

    final_image = np.vstack([banner, overlay])
    return final_image


def main():
    parser = argparse.ArgumentParser(
        description="PortionVision: Food Segmentation & Identification Visualizer"
    )
    parser.add_argument(
        "image",
        nargs="?",
        default=None,
        help="Path to plate photo. If omitted, selects newest sample image from cv_service/outputs/.",
    )
    parser.add_argument(
        "--menu",
        default=None,
        help="Optional comma-separated daily mess menu (e.g. 'steamed rice, dal tadka, chapati').",
    )
    parser.add_argument(
        "--meal",
        default="lunch",
        help="Meal slot ('breakfast', 'lunch', 'snacks', 'dinner'). Default: lunch.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda"],
        help="Inference device (cpu or cuda). Default: cpu.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save visual overlays and metrics. Defaults to cv_service/outputs/open_vocab_<timestamp>/.",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("  PORTIONVISION - SAM 3 FOOD INSPECTION & VISUALIZER")
    print("=" * 80)

    # 1. Resolve Image Path
    image_path = args.image
    if not image_path:
        image_path = find_default_image()
        if not image_path:
            print("[ERROR] No image provided and no sample images found in cv_service/outputs/.")
            print("   Usage: python visualize_open_vocab.py <path/to/plate.png>")
            sys.exit(1)
        print(f"[INPUT] Auto-selected newest sample plate: {image_path}")
    else:
        if not os.path.exists(image_path):
            print(f"[ERROR] Image not found: {image_path}")
            sys.exit(1)

    # 2. Parse Menu
    menu_items = None
    if args.menu and args.menu.strip().lower() not in ("none", "null", ""):
        menu_items = [m.strip() for m in args.menu.split(",") if m.strip()]
        print(f"[MENU] Contextual Mess Menu: {menu_items}")
    else:
        print("[MENU] Contextual Mess Menu: None (Open-plate zero-shot mode)")

    # 3. Setup Output Directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    outputs_base = os.path.join(base_dir, "outputs")
    os.makedirs(outputs_base, exist_ok=True)

    if args.output_dir:
        out_dir = os.path.abspath(args.output_dir)
    else:
        out_dir = os.path.join(outputs_base, f"{timestamp}_vis")
    os.makedirs(out_dir, exist_ok=True)
    seg_dir = os.path.join(out_dir, "segmentation")
    os.makedirs(seg_dir, exist_ok=True)
    crops_dir = os.path.join(seg_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)

    print(f"[OUTPUT] Target Output Dir:    {out_dir}")
    print(f"[CONFIG] Inference Device:     {args.device.upper()}")
    print(f"[CONFIG] Engine:               SAM 3.1 Unified Grounding + Segmentation")
    print("-" * 80)

    # 4. Load Image
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"[ERROR] Failed to decode image: {image_path}")
        sys.exit(1)

    print(f"[RUN] Processing image of size {img_bgr.shape[1]}x{img_bgr.shape[0]}...")
    pipeline = OpenVocabFoodSegmenter(device=args.device)

    t0 = time.perf_counter()
    res = pipeline.process_plate(img_bgr, menu_items=menu_items, meal_type=args.meal, output_dir=seg_dir)
    elapsed = time.perf_counter() - t0

    food_items = res.get("food_items", [])
    print(
        f"\n[DONE] Pipeline Complete in {elapsed:.2f}s | "
        f"Detected: {len(food_items)} ({res['recognized_count']} recognized, "
        f"{res['unlisted_count']} unlisted, {res['uncertain_count']} uncertain)"
    )
    print("=" * 80)

    # 5. Formatted Table Output with Modular Confidence Decomposition
    header = (
        f"{'#':<3} | {'Food Name':<20} | {'Status':<10} | {'Menu Match':<10} | "
        f"{'CompConf':<8} | {'ID Conf':<8} | {'SegConf':<8} | {'AssocConf':<9} | {'Area (px)'}"
    )
    print(header)
    print("-" * len(header))

    serializable_items = []

    for idx, item in enumerate(food_items, 1):
        name = item.get("food_name", "unknown")
        status = item.get("identification_status", "uncertain")
        match = "Yes" if item.get("menu_match") else "No"
        comp_conf = item.get("confidence", 0.0)
        id_conf = item.get("identification_confidence", 0.0)
        seg_conf = item.get("segmentation_confidence", 0.0)
        assoc_conf = item.get("association_confidence", 0.0)
        area = item.get("area_pixels", 0)
        bbox = item.get("bounding_box", [0, 0, 0, 0])
        bx, by, bw, bh = bbox

        print(
            f"{idx:<3} | {name:<20} | {status:<10} | {match:<10} | "
            f"{comp_conf * 100:>7.1f}% | {id_conf * 100:>7.1f}% | {seg_conf * 100:>7.1f}% | {assoc_conf * 100:>8.1f}% | {area}"
        )

        # Save individual crop
        crop = img_bgr[by : by + bh, bx : bx + bw]
        safe_name = name.replace(" ", "_").replace("/", "_")
        crop_filename = f"item_{idx:02d}_{safe_name}.png"
        crop_path = os.path.join(crops_dir, crop_filename)
        if crop.size > 0:
            cv2.imwrite(crop_path, crop)

        # Build JSON-serializable item dict
        item_copy = dict(item)
        if "mask" in item_copy:
            mask_arr = item_copy["mask"]
            if isinstance(mask_arr, np.ndarray):
                item_copy["mask_shape"] = list(mask_arr.shape)
                item_copy["mask_nonzeros"] = int(np.count_nonzero(mask_arr))
            item_copy["mask"] = None
        item_copy["crop_path"] = os.path.relpath(crop_path, out_dir)
        serializable_items.append(item_copy)

    print("-" * len(header))

    # 6. Generate Annotated Overlay Image
    annotated_img = draw_detection_overlay(img_bgr, food_items, res)
    annotated_path = os.path.join(out_dir, "annotated.png")
    cv2.imwrite(annotated_path, annotated_img)

    # 7. Write Structured JSON Result
    output_dict = {
        "source_image": os.path.abspath(image_path),
        "menu_items": menu_items,
        "image_dimensions": res.get("image_dimensions", [img_bgr.shape[1], img_bgr.shape[0]]),
        "total_items": len(food_items),
        "recognized_count": res.get("recognized_count", 0),
        "unlisted_count": res.get("unlisted_count", 0),
        "uncertain_count": res.get("uncertain_count", 0),
        "elapsed_seconds": round(elapsed, 3),
        "diagnostics": res.get("diagnostics", {}),
        "food_items": serializable_items,
    }
    json_path = os.path.join(out_dir, "results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_dict, f, indent=2)

    print(f"\n[SAVED] Outputs successfully written to: {out_dir}")
    print(f"   * Annotated Visual Overlay:  {annotated_path}")
    print(f"   * Structured JSON Results:  {json_path}")
    print(f"   * Individual Item Crops:    {crops_dir} ({len(food_items)} crops)")
    print("=" * 80)


if __name__ == "__main__":
    main()
