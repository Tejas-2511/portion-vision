"""
PortionVision — Standalone Plate Evaluation & Metrology CLI Tool
================================================================

Run PortionVision's full Computer Vision pipeline on any plate photo:
  1. Meta SAM 3 open-vocabulary segmentation & grounding.
  2. Depth Anything 3 metric depth estimation & 3D topographic relief mapping.
  3. 5-Archetype volumetric voxel integration (mound, liquid, salad, planar, chunk).
  4. Dynamic visual density & macronutrient calculation (Calories, Protein, Carbs, Fat).
  5. HTML inspection report & high-resolution diagnostic artifact generation.

Quick Start:
  # 1. Run on default example plate with standard menu:
  python evaluate_example.py

  # 2. Run on a specific plate image with contextual mess menu:
  python evaluate_example.py --image "plate/use/IMG20260408201758.jpg" --menu "palak paneer, dal, steamed rice, green salad"

  # 3. Run in open-world discovery mode (no menu provided):
  python evaluate_example.py --image "plate/use/IMG20260402200840.jpg" --open-world
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import cv2

# Ensure cv_service is on sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CV_SERVICE_DIR = os.path.join(ROOT_DIR, "cv_service")
if CV_SERVICE_DIR not in sys.path:
    sys.path.insert(0, CV_SERVICE_DIR)

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
    if not os.path.isabs(image_path):
        # Check relative to current working dir, then relative to repository root
        if not os.path.exists(image_path):
            candidate = os.path.join(ROOT_DIR, image_path)
            if os.path.exists(candidate):
                image_path = candidate

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Plate image not found: {image_path}")

    print("=" * 78)
    print("  PORTIONVISION — COMPUTER VISION PORTION EVALUATION")
    print("=" * 78)
    print(f" Image Target : {os.path.abspath(image_path)}")
    print(f" Context Menu : {menu_items if menu_items else '(Open-world discovery mode)'}")
    print("-" * 78)

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

    print("\n" + "=" * 78)
    print(f"  DETECTION & MACRONUTRIENT SUMMARY ({len(food_items)} dishes identified, {total_time:.2f}s)")
    print("=" * 78)
    print(f"  {'Food Item':<22} | {'Mass (g)':<9} | {'Vol (ml)':<9} | {'Conf':<6} | {'Calories':<9} | {'Macros (P/C/F)'}")
    print("  " + "-" * 74)

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

    print("  " + "-" * 74)
    print(f"  {'TOTAL MEAL':<22} | {total_mass:>7.1f}g | {'':<9} | {'':<6} | {total_cal:>6.0f} kcal | {total_p:>4.1f}g / {total_c:>4.1f}g / {total_f:>4.1f}g")
    print("=" * 78)

    debug_info = res.get("_debug", {})
    run_dir = debug_info.get("run_dir")
    report_path = debug_info.get("report")

    print("\n[RUN OUTPUT ARTIFACTS]")
    if run_dir and os.path.exists(run_dir):
        print(f"  • Run Directory : {run_dir}")
        if report_path and os.path.exists(report_path):
            print(f"  • Visual Report : {report_path}")
        
        # List stage subfolders
        for root, dirs, files in os.walk(run_dir):
            for file in files:
                if file.endswith((".png", ".jpg", ".json", ".html")) and not file.endswith("pipeline.log"):
                    rel = os.path.relpath(os.path.join(root, file), run_dir)
                    print(f"    - {rel}")
    print()

    return res


def main():
    parser = argparse.ArgumentParser(
        description="PortionVision Plate Evaluation & Metrology CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evaluate_example.py
  python evaluate_example.py --image "plate/use/IMG20260408201758.jpg" --menu "palak paneer, dal, steamed rice, green salad"
  python evaluate_example.py --image "plate/use/IMG20260402200840.jpg" --open-world
        """
    )
    default_img = os.path.join("plate", "use", "IMG-20260402-WA0047.jpg")
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

    args = parser.parse_args()

    menu_list = None
    if not args.open_world and args.menu:
        menu_list = [item.strip() for item in args.menu.split(",") if item.strip()]

    evaluate_plate(
        image_path=args.image,
        menu_items=menu_list,
        debug=True,
    )


if __name__ == "__main__":
    main()
