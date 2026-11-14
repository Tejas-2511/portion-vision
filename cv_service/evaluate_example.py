"""
PortionVision — Example Plate Evaluation & Metrology CLI Guide

A standalone, production-ready utility to run PortionVision's full Computer Vision
pipeline on any plate photo with an optional contextual mess menu.

Features:
  1. Meta SAM 3 open-vocabulary instance segmentation & grounding.
  2. Depth Anything 3 metric depth estimation & 3D topographic relief mapping.
  3. 5-Archetype volumetric voxel integration (mound, liquid, salad, planar, chunk).
  4. Dynamic visual density & macronutrient calculation (Calories, Protein, Carbs, Fat).
  5. Automatic export of high-resolution visual artifacts to `cv_service/outputs/latest/`.

Usage Examples:
  # 1. Run on default example plate with a sample mess menu:
  python cv_service/evaluate_example.py

  # 2. Run on a custom plate image with specific menu items:
  python cv_service/evaluate_example.py --image "plate/use/IMG20260408201758.jpg" --menu "palak paneer, dal, steamed rice, green salad"

  # 3. Run in open-world discovery mode (no menu provided):
  python cv_service/evaluate_example.py --image "plate/use/IMG20260402200840.jpg" --open-world

Outputs generated in `cv_service/outputs/latest/`:
  - `latest_annotated.png`       : Final segmentation overlay with dish names, masses, and confidences.
  - `latest_height_map.png`      : 3D Topographic relief map (Turbo colormap) showing dome curvatures.
  - `latest_depth.png`           : Continuous metric depth map.
  - `latest_height_relative.png` : Tray-normalized height map.
  - `results.json`               : Machine-readable portion masses, volumes, and nutritional macros.
"""

from __future__ import annotations

import os
import sys
import argparse
import time
import json
import cv2
import numpy as np

# Add cv_service to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from estimation.mass_estimator import estimate_food_mass


def evaluate_plate(
    image_path: str,
    menu_items: list[str] | None = None,
    output_dir: str | None = None,
    debug: bool = True,
) -> dict:
    """
    Run the end-to-end PortionVision pipeline on a given plate image.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Plate image not found: {image_path}")

    print("=" * 75)
    print("  PORTIONVISION — COMPUTER VISION PORTION EVALUATION")
    print("=" * 75)
    print(f" Image Target : {os.path.abspath(image_path)}")
    print(f" Context Menu : {menu_items if menu_items else '(Open-world discovery mode)'}")
    print("-" * 75)

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Could not decode image at: {image_path}")

    t0 = time.perf_counter()
    res = estimate_food_mass(
        image_bgr=img_bgr,
        expected_items=menu_items,
        debug=debug,
        use_open_vocab=True,
    )
    total_time = time.perf_counter() - t0

    food_items = res.get("food_items", [])
    raw_dets = res.get("raw_detections", [])

    print("\n" + "=" * 75)
    print(f"  DETECTION & MACRONUTRIENT SUMMARY ({len(food_items)} dishes identified, {total_time:.2f}s)")
    print("=" * 75)
    print(f"  {'Food Item':<22} | {'Mass (g)':<9} | {'Vol (ml)':<9} | {'Conf':<6} | {'Calories':<9} | {'Macros (P/C/F)'}")
    print("  " + "-" * 73)

    total_mass = 0.0
    total_cal = 0.0
    total_p = 0.0
    total_c = 0.0
    total_f = 0.0

    for it in food_items:
        name = it["name"]
        mass = it["mass_g"]
        vol = it.get("volume_ml", 0.0)
        conf = it.get("confidence", 0.0)
        cal = it.get("calories", 0.0)
        p = it.get("protein", 0.0)
        c = it.get("carbs", 0.0)
        f = it.get("fat", 0.0)

        total_mass += mass
        total_cal += cal
        total_p += p
        total_c += c
        total_f += f

        print(f"  {name:<22} | {mass:>7.1f}g | {vol:>7.1f}ml | {conf * 100:>4.0f}% | {cal:>6.0f} kcal | {p:>4.1f}g / {c:>4.1f}g / {f:>4.1f}g")

    print("  " + "-" * 73)
    print(f"  {'TOTAL MEAL':<22} | {total_mass:>7.1f}g | {'':<9} | {'':<6} | {total_cal:>6.0f} kcal | {total_p:>4.1f}g / {total_c:>4.1f}g / {total_f:>4.1f}g")
    print("=" * 75)

    # Print output visualization paths
    target_out_dir = output_dir or os.path.join(BASE_DIR, "outputs", "latest")
    print("\n[VISUALIZATION ARTIFACTS]")
    if os.path.exists(target_out_dir):
        for fname in sorted(os.listdir(target_out_dir)):
            full_path = os.path.abspath(os.path.join(target_out_dir, fname))
            print(f"  • {fname:<25} -> {full_path}")
    print()

    return res


def main():
    parser = argparse.ArgumentParser(
        description="PortionVision Plate Evaluation & Metrology CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cv_service/evaluate_example.py
  python cv_service/evaluate_example.py --image "plate/use/IMG20260408201758.jpg" --menu "palak paneer, dal, steamed rice, green salad"
  python cv_service/evaluate_example.py --open-world
        """
    )
    default_img = os.path.join(os.path.dirname(BASE_DIR), "plate", "use", "IMG-20260402-WA0047.jpg")
    parser.add_argument(
        "--image", "-i",
        type=str,
        default=default_img,
        help=f"Path to plate image (default: {default_img})"
    )
    parser.add_argument(
        "--menu", "-m",
        type=str,
        default="dal, steamed rice, green salad",
        help="Comma-separated list of expected mess menu items (e.g. 'dal, steamed rice, green salad')"
    )
    parser.add_argument(
        "--open-world", "-w",
        action="store_true",
        help="Run without any menu constraints (pure open-set discovery)"
    )
    parser.add_argument(
        "--output_dir", "-o",
        type=str,
        default=None,
        help="Custom directory to export latest visualizations (default: cv_service/outputs/latest/)"
    )

    args = parser.parse_args()

    menu_list = None
    if not args.open_world and args.menu:
        menu_list = [item.strip() for item in args.menu.split(",") if item.strip()]

    evaluate_plate(
        image_path=args.image,
        menu_items=menu_list,
        output_dir=args.output_dir,
        debug=True,
    )


if __name__ == "__main__":
    main()
