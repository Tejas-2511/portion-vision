"""
PortionVision — Intelligent Food-Instance Grouper
Handles:
  1. Blob grouping for fragmented detections of the same food (e.g. scattered rice grains, cucumber slices).
  2. Spatial proximity & plate compartment-aware clustering.
  3. Non-merging guarantee for different food classes (touching rice and dal remain strictly separate).
  4. Mutual exclusivity enforcement: eliminates duplicate boundary pixels across distinct items.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _mask_min_distance(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Compute the minimum Euclidean pixel distance between two binary masks."""
    if np.logical_and(mask_a, mask_b).any():
        return 0.0

    # Fast 8-connected boundary contact check via 3x3 dilation
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated_a = cv2.dilate(mask_a.astype(np.uint8), kernel, iterations=1).astype(bool)
    if np.logical_and(dilated_a, mask_b).any():
        return 0.0

    # Extract contours/boundary points for exact distance
    contours_a, _ = cv2.findContours(mask_a.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours_b, _ = cv2.findContours(mask_b.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    if not contours_a or not contours_b:
        return float("inf")

    pts_a = np.vstack([c.reshape(-1, 2) for c in contours_a])
    pts_b = np.vstack([c.reshape(-1, 2) for c in contours_b])

    # Subsample boundary perimeter if large
    if len(pts_a) > 250:
        pts_a = pts_a[np.linspace(0, len(pts_a) - 1, 250, dtype=int)]
    if len(pts_b) > 250:
        pts_b = pts_b[np.linspace(0, len(pts_b) - 1, 250, dtype=int)]

    diff = pts_a[:, np.newaxis, :] - pts_b[np.newaxis, :, :]
    dist_sq = np.sum(diff ** 2, axis=-1)
    return float(np.sqrt(np.min(dist_sq)))


def group_food_fragments(
    detections: List[Dict[str, Any]],
    image_shape: Tuple[int, int],
    spatial_proximity_px: float = 75.0,
) -> List[Dict[str, Any]]:
    """
    Intelligently group fragmented masks belonging to the same food portion.

    Rules:
      1. ONLY detections of the exact same canonical food class can be grouped.
      2. Fragments must be within spatial proximity (default <= 75 px) or touching.
      3. Genuinely different food items (even if touching) are NEVER merged.
      4. Overlapping boundary pixels between DIFFERENT food items are resolved by
         confidence argmax to prevent duplicate mass calculations.
    """
    if not detections:
        return []

    H, W = image_shape[:2]

    # ── Group by Canonical Food Class ───────────────────────────────────────
    class_groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in detections:
        key = (d.get("name") or d.get("food_name") or d.get("query") or "unknown").strip().lower()
        class_groups.setdefault(key, []).append(d)

    grouped_detections: List[Dict[str, Any]] = []
    group_counter = 0

    for food_class, items in class_groups.items():
        if len(items) == 1:
            item = items[0].copy()
            item_area = int(item.get("area_pixels", item.get("area", item["mask"].sum())))
            item["area"] = item_area
            item["area_pixels"] = item_area
            item["grouped_instance_id"] = f"inst_{group_counter}"
            item["fragment_count"] = 1
            item["decision_reason"] = item.get("decision_reason") or "SINGLE_INSTANCE"
            grouped_detections.append(item)
            group_counter += 1
            continue

        # Multiple fragments of the same food class.
        # Use connected component / proximity graph clustering.
        n = len(items)
        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            root_i, root_j = find(i), find(j)
            if root_i != root_j:
                parent[root_i] = root_j

        for i in range(n):
            mask_i = items[i]["mask"]
            for j in range(i + 1, n):
                mask_j = items[j]["mask"]
                dist = _mask_min_distance(mask_i, mask_j)

                # Salads & rice fragments cluster easily within a serving zone
                is_salad = "salad" in food_class or "cucumber" in food_class
                threshold = spatial_proximity_px * 1.5 if is_salad else spatial_proximity_px

                if dist <= threshold:
                    union(i, j)

        # Build clusters
        clusters: Dict[int, List[int]] = {}
        for idx in range(n):
            root = find(idx)
            clusters.setdefault(root, []).append(idx)

        for root, member_indices in clusters.items():
            if len(member_indices) == 1:
                single_item = items[member_indices[0]].copy()
                single_item["grouped_instance_id"] = f"inst_{group_counter}"
                single_item["fragment_count"] = 1
                single_item["decision_reason"] = single_item.get("decision_reason") or "SINGLE_INSTANCE"
                grouped_detections.append(single_item)
                group_counter += 1
            else:
                # Merge multiple fragments into one logical food instance
                member_items = [items[idx] for idx in member_indices]
                merged_mask = np.zeros((H, W), dtype=bool)
                total_weighted_conf = 0.0
                total_area = 0
                all_boxes = []

                for m_it in member_items:
                    m_mask = m_it["mask"]
                    merged_mask = np.logical_or(merged_mask, m_mask)
                    m_area = int(m_mask.sum())
                    m_conf = float(m_it.get("confidence", 0.70))
                    total_area += m_area
                    total_weighted_conf += m_conf * m_area
                    if "bounding_box" in m_it:
                        all_boxes.append(m_it["bounding_box"])

                merged_conf = total_weighted_conf / max(total_area, 1)

                # Compute unified bounding box [x, y, w, h]
                y_idx, x_idx = np.where(merged_mask)
                if len(x_idx) > 0:
                    bx = int(x_idx.min())
                    by = int(y_idx.min())
                    bw = int(x_idx.max() - bx + 1)
                    bh = int(y_idx.max() - by + 1)
                    unified_box = [bx, by, bw, bh]
                else:
                    unified_box = [0, 0, 0, 0]

                rep = member_items[0].copy()
                rep["mask"] = merged_mask
                rep["area"] = int(merged_mask.sum())
                rep["area_pixels"] = int(merged_mask.sum())
                rep["bounding_box"] = unified_box
                rep["confidence"] = round(float(merged_conf), 4)
                rep["identification_confidence"] = round(float(merged_conf), 4)
                rep["segmentation_confidence"] = round(float(merged_conf), 4)
                rep["fragment_count"] = len(member_indices)
                rep["grouped_instance_id"] = f"inst_{group_counter}"
                rep["decision_reason"] = f"FRAGMENT_GROUPED_{len(member_indices)}_PIECES"
                rep["is_small_item"] = int(merged_mask.sum()) < (H * W * 0.015)

                logger.info(
                    "[Instance Grouper] Grouped %d fragments of '%s' into unified instance (area=%d px, conf=%.2f)",
                    len(member_indices), food_class, int(merged_mask.sum()), merged_conf,
                )
                grouped_detections.append(rep)
                group_counter += 1

    # ── Final Mutual Exclusivity Pass (No Duplicate Mass Calculation) ───────
    # If two DIFFERENT foods have overlapping boundary pixels, assign each contested
    # pixel to the food instance with higher confidence.
    occupied_mask = np.zeros((H, W), dtype=np.int32) - 1

    # Sort items by confidence descending
    grouped_detections.sort(key=lambda d: float(d.get("confidence", 0.5)), reverse=True)

    for inst_idx, item in enumerate(grouped_detections):
        raw_mask = item["mask"]
        # Pixels that were already claimed by a higher-confidence distinct food
        already_claimed = (occupied_mask >= 0) & (occupied_mask != inst_idx)
        contested_pixels = raw_mask & already_claimed

        if contested_pixels.any():
            # Remove contested pixels from this lower-confidence item
            cleaned_mask = raw_mask & (~already_claimed)
            item["mask"] = cleaned_mask
            item["area"] = int(cleaned_mask.sum())
            item["area_pixels"] = int(cleaned_mask.sum())

        occupied_mask[item["mask"]] = inst_idx

    # Discard any items that were completely starved by mutual exclusivity
    valid_final = [d for d in grouped_detections if d.get("area_pixels", 0) > 50]
    return valid_final
