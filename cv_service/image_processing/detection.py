"""
Plate & compartment detection + pixel-to-cm scale calibration.

Detects individual compartments inside a non-circular sectioned mess plate
and computes a scale factor (cm per pixel) using known plate dimensions.
"""

import cv2
import numpy as np
from config.plate_config import get_plate_profile, PLATE_PROFILES


def find_compartments(image: np.ndarray) -> list[dict]:
    """
    Detect compartments in the plate image using contour analysis.

    Returns a list of dicts:
        {
            "bbox": (x, y, w, h),
            "contour": np.ndarray,
            "area_px": int,
        }
    sorted top-left → bottom-right.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive threshold to capture compartment dividers
    thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15, C=5,
    )

    # Morphological close to merge nearby edges into solid dividers
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Also try Canny-based detection and merge
    edges = cv2.Canny(blurred, 30, 100)
    dilated = cv2.dilate(edges, kernel, iterations=2)
    combined = cv2.bitwise_or(closed, dilated)

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = image.shape[:2]
    img_area = img_h * img_w
    min_area = img_area * 0.02   # compartment must be ≥ 2% of plate
    max_area = img_area * 0.90   # must not be the whole plate

    compartments = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(cnt)
            # Reject if it's basically the full image border
            if w < img_w * 0.95 and h < img_h * 0.95:
                compartments.append({
                    "bbox": (x, y, w, h),
                    "contour": cnt,
                    "area_px": int(area),
                })

    # Sort: top row first (by y), then left→right (by x)
    compartments.sort(key=lambda c: c["bbox"][1] * img_w + c["bbox"][0])

    return compartments


def pick_best_plate_profile(compartments: list[dict]) -> str:
    """
    Look at detected compartments and pick the best matching profile
    from plate_config automatically based on aspect ratios and count.
    """
    if not compartments:
        return "standard_mess_thali"

    best_profile_name = "standard_mess_thali"
    best_total_diff = float("inf")
    
    det_ratios = sorted([c["bbox"][2] / max(c["bbox"][3], 1) for c in compartments], reverse=True)

    for name, p in PLATE_PROFILES.items():
        prof_ratios = sorted([c["width_cm"] / max(c["height_cm"], 1) for c in p["compartments"]], reverse=True)
        
        # Penalty for count mismatch
        diff = abs(len(det_ratios) - len(prof_ratios)) * 1.5
        
        # Add up differences in sorted ratios
        for i in range(min(len(det_ratios), len(prof_ratios))):
            diff += abs(det_ratios[i] - prof_ratios[i])
        
        # Penalize extra/missing detected items
        diff += abs(len(det_ratios) - len(prof_ratios)) * 0.5

        if diff < best_total_diff:
            best_total_diff = diff
            best_profile_name = name

    return best_profile_name


def compute_scale(
    compartments: list[dict],
    image_shape: tuple,
    plate_profile_name: str = None,
) -> float:
    """
    Compute pixels-per-cm scale factor by matching detected compartments
    to known real-world dimensions. Handles auto-detection if profile not provided.
    """
    if plate_profile_name is None:
        plate_profile_name = pick_best_plate_profile(compartments)

    profile = get_plate_profile(plate_profile_name)
    img_h, img_w = image_shape[:2]

    if not compartments:
        # Fall back to outer plate dimensions
        px_per_cm_w = img_w / profile["outer_width_cm"]
        px_per_cm_h = img_h / profile["outer_height_cm"]
        px_per_cm = (px_per_cm_w + px_per_cm_h) / 2.0
        return 1.0 / px_per_cm  # cm per pixel

    # Sort detected compartments by pixel area (largest first)
    sorted_det = sorted(compartments, key=lambda c: c["area_px"], reverse=True)

    # Sort profile compartments by real area (largest first)
    profile_comps = sorted(
        profile["compartments"],
        key=lambda c: c["width_cm"] * c["height_cm"],
        reverse=True,
    )

    # Match largest detected to largest known
    largest_det = sorted_det[0]
    _, _, det_w, det_h = largest_det["bbox"]
    largest_known = profile_comps[0]

    px_per_cm_w = det_w / largest_known["width_cm"]
    px_per_cm_h = det_h / largest_known["height_cm"]
    px_per_cm = (px_per_cm_w + px_per_cm_h) / 2.0

    return 1.0 / max(px_per_cm, 1e-6)  # cm per pixel


def match_compartments_to_profile(
    compartments: list[dict],
    plate_profile_name: str = None,
) -> list[dict]:
    """
    Mapping of detected compartments to labels using auto-detected plate profile.
    """
    if plate_profile_name is None:
        plate_profile_name = pick_best_plate_profile(compartments)

    profile = get_plate_profile(plate_profile_name)
    profile_comps = profile["compartments"]

    # Sort both by area (largest→smallest) for greedy matching
    det_sorted = sorted(compartments, key=lambda c: c["area_px"], reverse=True)
    prof_sorted = sorted(
        profile_comps,
        key=lambda c: c["width_cm"] * c["height_cm"],
        reverse=True,
    )

    enriched = []
    used_profile_indices = set()

    for det in det_sorted:
        best_idx = None
        best_diff = float("inf")
        det_ratio = det["bbox"][2] / max(det["bbox"][3], 1)  # w/h aspect ratio

        for i, pc in enumerate(prof_sorted):
            if i in used_profile_indices:
                continue
            pc_ratio = pc["width_cm"] / max(pc["height_cm"], 1)
            diff = abs(det_ratio - pc_ratio)
            if diff < best_diff:
                best_diff = diff
                best_idx = i

        if best_idx is not None and best_diff < 2.0:
            matched = prof_sorted[best_idx]
            used_profile_indices.add(best_idx)
            enriched.append({
                **det,
                "label": matched["label"],
                "depth_cm": matched["depth_cm"],
                "max_volume_ml": matched["max_volume_ml"],
            })
        else:
            # Unmatched — use defaults
            enriched.append({
                **det,
                "label": f"section_{len(enriched) + 1}",
                "depth_cm": 2.0,
                "max_volume_ml": 200,
            })

    return enriched
