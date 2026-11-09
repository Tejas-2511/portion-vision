"""
PortionVision — Streamlined Vision Pipeline Orchestrator.

Architecture:
  Plate Image (Top-Down BGR)
       ↓
  SAM 3 Unified Concept Grounding & Instance Segmentation
       ↓
  Lightweight Food-Aware Validation & Cutlery Rejection
       ↓
  Individual Food Region Masks + RGBA Crops
       ↓
  Depth Anything & Geometric Mass Estimation (Downstream)
"""

from __future__ import annotations

import logging
import time
import os
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Optional

from .sam3_segmenter import Sam3FoodSegmenter, get_sam3_segmenter, is_sam3_available

logger = logging.getLogger(__name__)


def get_vram_usage_mb() -> float:
    """Returns allocated GPU VRAM in megabytes, or 0.0 if CUDA is unavailable."""
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.memory_allocated() / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0


class OpenVocabFoodSegmenter:
    """
    Streamlined Food Identification & Instance Segmentation Pipeline.
    Backed solely by Meta SAM 3.1 with food-aware validation and non-food rejection.
    """

    def __init__(
        self,
        weights_dir: Optional[str] = None,
        device: Optional[str] = None,
        confidence_threshold: float = 0.35,
        **kwargs,
    ):
        self.device = device or "cuda"
        self.confidence_threshold = confidence_threshold

        logger.info(
            "[Pipeline] Initializing SAM 3.1 Food Segmentation Engine (device=%s, conf=%.2f)",
            self.device,
            self.confidence_threshold,
        )
        self.segmenter = get_sam3_segmenter(confidence_threshold=self.confidence_threshold)

    def process_plate(
        self,
        image_bgr: np.ndarray,
        menu_items: Optional[List[str]] = None,
        compartments: Optional[List[Dict[str, Any]]] = None,
        meal_type: str = "lunch",
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes unified SAM 3 food identification and segmentation.

        Args:
            image_bgr:    Top-down plate image (numpy HxWx3 BGR).
            menu_items:   Optional list of dishes from OCR menu.
            compartments: Optional tray compartment bounding boxes.
            meal_type:    Meal slot ('breakfast', 'lunch', 'snacks', 'dinner').
            output_dir:   Optional directory for saving segmentation crops and overlay.

        Returns:
            Structured dictionary compliant with PortionVision output contract.
        """
        t0 = time.perf_counter()
        h, w = image_bgr.shape[:2]
        vram_start = get_vram_usage_mb()

        logger.info(
            "[Pipeline] Processing %dx%d plate image (meal=%s, %d menu items)...",
            w, h, meal_type, len(menu_items or []),
        )

        # Convert BGR to PIL Image RGB for SAM 3
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(image_rgb)

        # Single-pass unified concept grounding + segmentation
        food_items = self.segmenter.segment_plate(
            image_path_or_pil=image_pil,
            menu_items=menu_items,
            generic_discovery=True,
            meal_type=meal_type,
            save_crops=True,
            output_dir=output_dir,
        )

        elapsed = time.perf_counter() - t0

        recognized = sum(1 for it in food_items if it["identification_status"] == "recognized")
        unlisted   = sum(1 for it in food_items if it["identification_status"] == "unlisted")
        uncertain  = sum(1 for it in food_items if it["identification_status"] == "uncertain")

        logger.info(
            "[Pipeline] Detected %d food items (%d recognized, %d unlisted, %d uncertain) in %.2fs",
            len(food_items), recognized, unlisted, uncertain, elapsed,
        )

        return {
            "food_items": food_items,
            "image_dimensions": [w, h],
            "total_items": len(food_items),
            "recognized_count": recognized,
            "unlisted_count": unlisted,
            "uncertain_count": uncertain,
            "elapsed_seconds": round(elapsed, 3),
            "diagnostics": {
                "pipeline": "sam3_streamlined",
                "timings": {"total_pipeline_s": round(elapsed, 3)},
                "vram_mb": {
                    "start": vram_start,
                    "end": get_vram_usage_mb(),
                },
                "device": self.device,
            },
        }
