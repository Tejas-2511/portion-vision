"""
PortionVision — SAM 3 Food Segmentation & Identification Engine.

Sole primary engine for:
  - Text-prompted food concept detection & instance segmentation
  - Open-world food discovery with contextual menu guidance
  - Non-food rejection (spoons, cutlery, napkins, empty surfaces)
  - Food-aware mask refinement and deduplication
  - Transparent RGBA crop export for downstream depth/mass estimation
"""

from __future__ import annotations

import gc
import logging
import os
import sys
import time
import json
import uuid
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SAM 3 codebase on sys.path
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent          # cv_service/open_vocab/
_CV_SERVICE_DIR = _THIS_DIR.parent                    # cv_service/
_REPO_ROOT = _CV_SERVICE_DIR.parent                   # portion-vision/
_SAM3_REPO = str(_REPO_ROOT.parent / "SAM3" / "sam3") # ../SAM3/sam3

if _SAM3_REPO not in sys.path:
    sys.path.insert(0, _SAM3_REPO)
if str(_CV_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_CV_SERVICE_DIR))

from config.synonym_map import get_visual_prompt_aliases, find_menu_match

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SAM3_CHECKPOINT = (
    r"C:\Users\tejas\.cache\huggingface\hub"
    r"\models--facebook--sam3.1\snapshots"
    r"\daa63191845a41281374e725f4c9e51c7a824460"
    r"\sam3.1_multiplex.pt"
)

# ---------------------------------------------------------------------------
# Query Taxonomies
# ---------------------------------------------------------------------------

# Common Indian staple and side dishes queried for open-world discovery
COMMON_INDIAN_STAPLES: List[str] = [
    "rice",
    "dal",
    "curry",
    "sabzi",
    "chapati",
    "roti",
    "paratha",
    "poori",
    "papad",
    "salad",
    "cucumber",
    "tomato",
    "onion",
    "pickle",
    "chutney",
    "curd",
    "raita",
    "paneer",
    "chicken",
    "egg",
    "biryani",
    "pulao",
    "sambar",
    "chole",
    "rajma",
    "idli",
    "dosa",
    "vada",
    "poha",
    "upma",
    "samosa",
    "pakoda",
    "halwa",
    "gulab jamun",
    "sweet",
    "cake",
    "fruit",
]

# Non-food anchors used strictly for rejection
NON_FOOD_ANCHORS: List[str] = [
    "spoon",
    "fork",
    "cutlery",
    "napkin",
]

# Generic fallback query (only assigned if no specific query claimed the region)
GENERIC_FALLBACK_QUERY = "food"

# Deduplication and rejection thresholds
_DEDUP_IOU_THRESH = 0.55
_NON_FOOD_IOU_THRESH = 0.35
_NON_FOOD_CONTAINMENT_THRESH = 0.50
_MIN_MASK_AREA_RATIO = 0.001       # 0.1% of image area
_MAX_MASK_AREA_RATIO = 0.92        # 92% of image area (reject background canvas)


# ---------------------------------------------------------------------------
# Geometric & Mask Utility Functions
# ---------------------------------------------------------------------------

def _mask_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Compute IoU between two boolean masks of the same shape."""
    inter = np.logical_and(mask_a, mask_b).sum()
    if inter == 0:
        return 0.0
    union = np.logical_or(mask_a, mask_b).sum()
    return float(inter) / float(union) if union > 0 else 0.0


def _mask_overlap_ratio(mask_subject: np.ndarray, mask_reference: np.ndarray) -> float:
    """Fraction of mask_subject that falls inside mask_reference."""
    subj_area = mask_subject.sum()
    if subj_area == 0:
        return 0.0
    inter = np.logical_and(mask_subject, mask_reference).sum()
    return float(inter) / float(subj_area)


def _mask_to_xywh(mask: np.ndarray) -> List[int]:
    """Return [x, y, w, h] bounding box from a boolean mask."""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return [0, 0, 0, 0]
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return [x0, y0, max(1, x1 - x0), max(1, y1 - y0)]


def _save_rgba_crop(
    image_pil: Image.Image,
    mask: np.ndarray,
    crop_path: str,
) -> None:
    """
    Save an RGBA PNG crop of the detected food region.
    Non-masked pixels are set to transparent (alpha=0).
    """
    img_rgba = image_pil.convert("RGBA")
    img_arr = np.array(img_rgba)

    alpha = (mask.astype(np.uint8) * 255)
    img_arr[:, :, 3] = alpha

    ys, xs = np.where(mask)
    if len(xs) == 0:
        return
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    crop_arr = img_arr[y0 : y1 + 1, x0 : x1 + 1]

    os.makedirs(os.path.dirname(crop_path), exist_ok=True)
    Image.fromarray(crop_arr, "RGBA").save(crop_path)


# ---------------------------------------------------------------------------
# Sam3FoodSegmenter Class
# ---------------------------------------------------------------------------

class Sam3FoodSegmenter:
    """
    PortionVision — Central SAM 3 Food Identification & Segmentation Engine.

    Handles:
      1. Single visual backbone encoding per plate image
      2. Multi-concept text grounding:
         - Menu-guided dish items (e.g., 'dal palak', 'steamed rice')
         - Common Indian staples (e.g., 'cucumber', 'roti', 'pickle')
         - Non-food anchors ('spoon', 'fork', 'napkin')
      3. Non-food rejection (spoons/cutlery discarded before downstream mass estimation)
      4. Specific-over-generic resolution (e.g., 'cucumber' preferred over generic 'food')
      5. Pixel-accurate RGBA crop generation
    """

    def __init__(
        self,
        checkpoint_path: str = SAM3_CHECKPOINT,
        confidence_threshold: float = 0.35,
        device: Optional[str] = None,
    ):
        import torch

        self.checkpoint_path = checkpoint_path
        self.confidence_threshold = confidence_threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._processor = None
        self._loaded = False
        logger.info(
            "[SAM3] Initialized Sam3FoodSegmenter (device=%s, conf_thresh=%.2f)",
            self.device,
            self.confidence_threshold,
        )

    def _load(self) -> None:
        """Lazy-loads SAM 3.1 weights into GPU memory."""
        if self._loaded:
            return

        import torch
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor

        t0 = time.perf_counter()
        logger.info("[SAM3] Loading SAM 3.1 checkpoint: %s", self.checkpoint_path)

        if not os.path.isfile(self.checkpoint_path):
            raise FileNotFoundError(
                f"[SAM3] Checkpoint not found at: {self.checkpoint_path}"
            )

        if self.device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        self._model = build_sam3_image_model(
            checkpoint_path=self.checkpoint_path,
            device=self.device,
            eval_mode=True,
            load_from_HF=False,
            enable_segmentation=True,
            enable_inst_interactivity=False,
        )
        self._model.eval()

        self._processor = Sam3Processor(
            model=self._model,
            resolution=1008,
            device=self.device,
            confidence_threshold=self.confidence_threshold,
        )

        elapsed = time.perf_counter() - t0
        logger.info(
            "[SAM3] SAM 3.1 loaded in %.1fs | VRAM: %.0f MB",
            elapsed,
            self.get_vram_mb(),
        )
        self._loaded = True

    def unload(self) -> None:
        """Explicitly unloads model to release GPU VRAM if needed."""
        if not self._loaded:
            return
        import torch

        logger.info("[SAM3] Unloading SAM 3.1 from VRAM...")
        del self._processor
        del self._model
        self._processor = None
        self._model = None
        self._loaded = False
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()
        logger.info("[SAM3] Unloaded. VRAM remaining: %.0f MB", self.get_vram_mb())

    @staticmethod
    def get_vram_mb() -> float:
        """Return current allocated CUDA VRAM in MB."""
        try:
            import torch
            if torch.cuda.is_available():
                return round(torch.cuda.memory_allocated() / (1024 * 1024), 1)
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------
    # Query Execution
    # ------------------------------------------------------------------

    def _run_query(
        self,
        state: Dict[str, Any],
        query: str,
        image_pil: Image.Image,
        query_type: str = "food",
        parent_menu_item: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run text grounding for a single query prompt."""
        import torch

        try:
            result_state = self._processor.set_text_prompt(
                prompt=query,
                state=state,
            )
        except Exception as exc:
            logger.warning("[SAM3] Query %r failed: %s", query, exc)
            return []

        masks_t: torch.Tensor = result_state.get("masks")
        boxes_t: torch.Tensor = result_state.get("boxes")
        scores_t: torch.Tensor = result_state.get("scores")

        if masks_t is None or masks_t.shape[0] == 0:
            return []

        detections = []
        img_w, img_h = image_pil.size
        total_px = img_w * img_h

        for i in range(masks_t.shape[0]):
            mask_np = masks_t[i, 0].cpu().numpy().astype(bool)
            score = float(scores_t[i].cpu().float())
            box = boxes_t[i].cpu().float().tolist()

            area = int(mask_np.sum())
            ratio = area / total_px

            # Micro-noise and full-canvas filters
            if ratio < _MIN_MASK_AREA_RATIO or ratio > _MAX_MASK_AREA_RATIO:
                continue

            detections.append(
                {
                    "query": query,
                    "query_type": query_type,
                    "parent_menu_item": parent_menu_item,
                    "mask": mask_np,
                    "box_xyxy": box,
                    "score": score,
                    "area": area,
                }
            )

        return detections

    # ------------------------------------------------------------------
    # Food-Aware Post-Processing & Validation
    # ------------------------------------------------------------------

    def _filter_and_disambiguate(
        self,
        food_detections: List[Dict[str, Any]],
        non_food_detections: List[Dict[str, Any]],
        menu_items: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Refines raw SAM 3 detections:
          1. Rejects any detection overlapping significantly with non-food anchors (spoons/cutlery).
          2. Resolves overlapping food hypotheses:
             - Parent menu items & visual aliases > Synonym-matched staples > Generic staples > 'food'.
          3. Deduplicates redundant detections of the same physical item with menu coverage balancing.
        """
        # Step 1: Reject low-confidence hallucinations and tableware/cutlery overlap
        valid_food: List[Dict[str, Any]] = []
        for f_det in food_detections:
            f_mask = f_det["mask"]
            q = f_det["query"].lower()
            score = f_det["score"]

            # Filter 1a: Confidence cutoff
            # Generic fallback 'food' needs higher confidence (>= 0.48) to avoid capturing empty trays/tables.
            # Specific food items require >= 0.42 to reject spurious reflections on bare plate rims.
            min_score = 0.48 if q == GENERIC_FALLBACK_QUERY else 0.42
            if score < min_score:
                logger.info(
                    "[SAM3 Filter] Rejected '%s' (conf=%.2f < min=%.2f) — below confidence threshold",
                    f_det["query"], score, min_score,
                )
                continue

            # Filter 1b: Overlap with non-food anchors (spoons, cutlery)
            is_non_food = False
            for nf_det in non_food_detections:
                nf_mask = nf_det["mask"]
                iou = _mask_iou(f_mask, nf_mask)
                overlap_f_in_nf = _mask_overlap_ratio(f_mask, nf_mask)
                overlap_nf_in_f = _mask_overlap_ratio(nf_mask, f_mask)

                if (iou >= _NON_FOOD_IOU_THRESH or 
                    overlap_f_in_nf >= _NON_FOOD_CONTAINMENT_THRESH or 
                    (overlap_nf_in_f >= 0.60 and q == GENERIC_FALLBACK_QUERY)):
                    logger.info(
                        "[SAM3 Filter] Rejected '%s' (conf=%.2f) — overlaps non-food '%s' (IoU=%.2f, f_in_nf=%.2f, nf_in_f=%.2f)",
                        f_det["query"], f_det["score"], nf_det["query"], iou, overlap_f_in_nf, overlap_nf_in_f,
                    )
                    is_non_food = True
                    break

            if not is_non_food:
                valid_food.append(f_det)

        # Step 2: Specificity score ranking
        # Priority:
        #   4 = Direct menu item or menu item's visual prompt alias
        #   3 = Exact menu string match or synonym cluster match (e.g. cucumber -> salad)
        #   2 = Specific Indian staple (unlisted)
        #   1 = Generic umbrella term ('food')
        menu_set = {m.strip().lower() for m in (menu_items or [])}

        # Step 2b: Ingredient-to-dish container binding (e.g., paneer cubes inside a curry bowl)
        # If a bowl/container is claimed by generic dal/curry, but physically contains specific ingredients
        # (e.g. paneer cubes whose parent menu item is 'palak paneer' or 'paneer butter masala'),
        # rebind the container to that specific dish so the curry is not mislabeled as dal.
        for cand in valid_food:
            cand_area = cand.get("area", 0)
            if cand_area < 10000:
                continue
            cand_mask = cand["mask"]
            cand_parent = (cand.get("parent_menu_item") or find_menu_match(cand["query"], menu_items) or "").lower()

            contained_dish_counts: Dict[str, int] = {}
            for other in valid_food:
                other_area = other.get("area", 0)
                if other is cand or other_area >= cand_area * 0.40:
                    continue
                if _mask_overlap_ratio(other["mask"], cand_mask) >= 0.70:
                    other_parent = other.get("parent_menu_item") or find_menu_match(other["query"], menu_items)
                    if other_parent:
                        op_clean = other_parent.strip().lower()
                        # If child is paneer/chicken/kofta ingredient matching a menu dish
                        if any(k in op_clean for k in ["paneer", "chicken", "kofta", "egg", "chana", "rajma"]):
                            contained_dish_counts[op_clean] = contained_dish_counts.get(op_clean, 0) + 1

            if contained_dish_counts:
                best_dish = max(contained_dish_counts, key=contained_dish_counts.get)
                if best_dish != cand_parent and ("dal" in cand_parent or "curry" in cand["query"].lower()):
                    logger.info(
                        "[SAM3 Binding] Container '%s' contains %d ingredient(s) of '%s' — rebinding bowl from '%s' to '%s'",
                        cand["query"], contained_dish_counts[best_dish], best_dish, cand_parent or cand["query"], best_dish,
                    )
                    cand["parent_menu_item"] = best_dish
                    cand["query"] = best_dish

        def get_priority(det: Dict[str, Any]) -> int:
            if det.get("parent_menu_item") is not None:
                return 4
            q = det["query"].lower()
            if q in menu_set:
                return 3
            if find_menu_match(q, menu_items) is not None:
                return 3
            if q != GENERIC_FALLBACK_QUERY:
                return 2
            return 1

        # Sort primarily by specificity priority descending, secondarily by score descending
        valid_food.sort(key=lambda d: (get_priority(d), d["score"]), reverse=True)

        # Step 3: Deduplication across overlapping masks with menu coverage awareness
        kept: List[Dict[str, Any]] = []
        assigned_menu_items: set[str] = set()

        for cand in valid_food:
            cand_mask = cand["mask"]
            parent = cand.get("parent_menu_item") or find_menu_match(cand["query"], menu_items)
            parent_key = parent.lower() if parent else None
            is_large = cand.get("area", 0) > 20000

            # If this menu item already claimed a primary bowl/compartment,
            # and another candidate for this exact mask belongs to an unassigned menu item,
            # allow the unassigned menu item to take it.
            if parent_key and is_large and parent_key in assigned_menu_items:
                has_alternative_menu_cand = False
                for alt in valid_food:
                    if alt is cand:
                        continue
                    alt_parent = alt.get("parent_menu_item") or find_menu_match(alt["query"], menu_items)
                    alt_key = alt_parent.lower() if alt_parent else None
                    if alt_key and alt_key not in assigned_menu_items and _mask_iou(cand_mask, alt["mask"]) >= _DEDUP_IOU_THRESH:
                        has_alternative_menu_cand = True
                        break
                if has_alternative_menu_cand:
                    continue

            duplicate = False
            for existing in kept:
                exist_mask = existing["mask"]
                iou = _mask_iou(cand_mask, exist_mask)

                if iou >= _DEDUP_IOU_THRESH:
                    duplicate = True
                    break

                # Subsumption: If cand is a small internal ingredient (e.g. paneer cube, chicken chunk)
                # sitting entirely inside an already-kept container bowl of the same parent dish,
                # subsume it into the container dish so the bowl is measured as one unified portion.
                if cand.get("area", 0) < existing.get("area", 0) * 0.40:
                    cand_in_exist = _mask_overlap_ratio(cand_mask, exist_mask)
                    if cand_in_exist >= 0.75:
                        exist_parent = existing.get("parent_menu_item") or find_menu_match(existing["query"], menu_items)
                        exist_key = exist_parent.lower() if exist_parent else None
                        if (exist_key and parent_key and exist_key == parent_key) or existing["query"] == cand["query"]:
                            logger.info(
                                "[SAM3 Subsumption] Subsuming internal ingredient '%s' (area=%d) into container dish '%s'",
                                cand["query"], cand.get("area", 0), existing["query"],
                            )
                            duplicate = True
                            break

            if not duplicate:
                kept.append(cand)
                if parent_key and is_large:
                    assigned_menu_items.add(parent_key)

        return kept

    # ------------------------------------------------------------------
    # Public Segmentation Pipeline
    # ------------------------------------------------------------------

    def segment_plate(
        self,
        image_path_or_pil: Union[str, Image.Image, np.ndarray],
        menu_items: Optional[List[str]] = None,
        generic_discovery: bool = True,
        meal_type: str = "lunch",
        save_crops: bool = True,
        output_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes SAM 3.1 food identification and concept segmentation.

        Args:
            image_path_or_pil: File path, PIL Image, or BGR numpy array.
            menu_items: Optional list of expected dishes from menu OCR.
            generic_discovery: Whether to discover unlisted food items.
            meal_type: Meal slot ('breakfast', 'lunch', etc.).
            save_crops: If True, saves transparent RGBA crops to disk.
            output_dir: Optional path to save segmentation crops and diagnostics.
                        Defaults to cv_service/outputs/<timestamp>_<uid>/segmentation/.

        Returns:
            List of structured PortionVision food item dictionaries.
        """
        self._load()

        # ── Format Image ──────────────────────────────────────────────────
        if isinstance(image_path_or_pil, str):
            image_pil = Image.open(image_path_or_pil).convert("RGB")
        elif isinstance(image_path_or_pil, np.ndarray):
            # Assumed BGR numpy array from cv2
            rgb = cv2.cvtColor(image_path_or_pil, cv2.COLOR_BGR2RGB)
            image_pil = Image.fromarray(rgb)
        else:
            image_pil = image_path_or_pil.convert("RGB")

        img_w, img_h = image_pil.size
        total_pixels = img_w * img_h
        t_start = time.perf_counter()

        logger.info(
            "[SAM3] segment_plate: %dx%d image | Menu items: %d | Generic discovery: %s",
            img_w, img_h, len(menu_items or []), generic_discovery,
        )

        # ── Encode Visual Backbone (Single Pass) ─────────────────────────
        state = self._processor.set_image(image_pil)

        # ── Build Query Batches ──────────────────────────────────────────
        food_queries: List[Tuple[str, str, Optional[str]]] = []  # (query, type, parent_menu_item)

        # 1. Menu queries (with visual prompt expansion for SAM 3 text grounding)
        if menu_items:
            for m in menu_items:
                m_clean = m.strip()
                if not m_clean:
                    continue
                aliases = get_visual_prompt_aliases(m_clean)
                for alias in aliases:
                    food_queries.append((alias, "menu", m_clean))

        # 2. Common Indian food staples
        if generic_discovery:
            for staple in COMMON_INDIAN_STAPLES:
                if not any(staple.lower() == q.lower() for q, _, _ in food_queries):
                    food_queries.append((staple, "staple", None))

            # 3. Generic fallback
            food_queries.append((GENERIC_FALLBACK_QUERY, "generic", None))

        # 4. Non-food rejection anchors
        non_food_queries = [(nf, "non_food", None) for nf in NON_FOOD_ANCHORS]

        # ── Run Non-Food Queries First ───────────────────────────────────
        raw_non_food: List[Dict[str, Any]] = []
        for q, q_type, parent_m in non_food_queries:
            dets = self._run_query(state, q, image_pil, query_type=q_type, parent_menu_item=parent_m)
            if dets:
                logger.info("[SAM3 Non-Food] Query '%s' found %d instances", q, len(dets))
                raw_non_food.extend(dets)

        # ── Run Food Queries ─────────────────────────────────────────────
        raw_food: List[Dict[str, Any]] = []
        for q, q_type, parent_m in food_queries:
            dets = self._run_query(state, q, image_pil, query_type=q_type, parent_menu_item=parent_m)
            if dets:
                logger.debug("[SAM3 Food] Query '%s' (parent=%s) found %d instances", q, parent_m, len(dets))
                raw_food.extend(dets)

        logger.info(
            "[SAM3] Raw candidates: %d food, %d non-food",
            len(raw_food), len(raw_non_food),
        )

        # ── Food-Aware Disambiguation & Rejection ─────────────────────────
        final_detections = self._filter_and_disambiguate(
            food_detections=raw_food,
            non_food_detections=raw_non_food,
            menu_items=menu_items,
        )

        # ── Intelligent Food-Instance Grouping (Fragments & Disconnected Blobs) ──
        # Combines multiple fragments of the same food portion (e.g. cucumber slices in salad,
        # scattered rice grains) while guaranteeing that genuinely different touching foods
        # (rice vs dal) remain strictly separated without duplicate boundary mass.
        from open_vocab.instance_grouper import group_food_fragments
        final_detections = group_food_fragments(
            detections=final_detections,
            image_shape=(img_h, img_w),
            spatial_proximity_px=75.0,
        )

        # ── Resolve Output Directory (Universal Timestamped Output Folder) ──
        if output_dir:
            norm_path = os.path.normpath(output_dir)
            if os.path.basename(norm_path) == "segmentation":
                seg_dir = norm_path
            else:
                seg_dir = os.path.join(norm_path, "segmentation")
        else:
            # Default to a universal timestamped run folder under cv_service/outputs/
            ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            uid_str = uuid.uuid4().hex[:8]
            seg_dir = str(_CV_SERVICE_DIR / "outputs" / f"{ts_str}_{uid_str}" / "segmentation")

        os.makedirs(seg_dir, exist_ok=True)
        crops_dir = os.path.join(seg_dir, "crops") if save_crops else None
        if crops_dir:
            os.makedirs(crops_dir, exist_ok=True)

        output_items: List[Dict[str, Any]] = []

        for idx, det in enumerate(final_detections):
            mask: np.ndarray = det["mask"]
            score: float = det["score"]
            raw_label: str = det["query"]
            parent_menu: Optional[str] = det.get("parent_menu_item")
            box_xywh = _mask_to_xywh(mask)
            area_px = int(det.get("area_pixels", det.get("area", 0)))
            is_small = area_px < (total_pixels * 0.015)

            # ── Strictly Evidence-Based Menu Matching & Open-Set Classification ──
            # The menu acts as contextual guidance, NEVER a forced classification mandate.
            matched_menu_str = parent_menu or find_menu_match(raw_label, menu_items, min_confidence=0.50)
            is_menu_match = matched_menu_str is not None

            if is_menu_match and score >= 0.45:
                display_label = matched_menu_str
                id_status = "recognized"
                decision_reason = det.get("decision_reason") or "MENU_EVIDENCE_MATCH"
            elif raw_label in {"food", GENERIC_FALLBACK_QUERY, "unlisted food"} or score < 0.45:
                # Explicit UNKNOWN / UNRECOGNIZED category — abstain rather than force-classify!
                display_label = "UNKNOWN"
                id_status = "unknown"
                matched_menu_str = None
                is_menu_match = False
                decision_reason = "ABSTAINED_INSUFFICIENT_EVIDENCE"
            elif score >= 0.52:
                # Strong open-set recognition: dish absent from menu, but visual evidence supports it!
                display_label = raw_label
                id_status = "open_set"
                matched_menu_str = None
                is_menu_match = False
                decision_reason = "OPEN_SET_VISUAL_RECOGNITION"
            else:
                display_label = "UNKNOWN"
                id_status = "unknown"
                matched_menu_str = None
                is_menu_match = False
                decision_reason = "ABSTAINED_LOW_CONFIDENCE"

            crop_path = None
            if save_crops and crops_dir:
                safe_name = display_label.replace(" ", "_").replace("/", "-")
                crop_path = os.path.join(crops_dir, f"{idx:02d}_{safe_name}_{score:.2f}.png")
                try:
                    _save_rgba_crop(image_pil, mask, crop_path)
                except Exception as exc:
                    logger.warning("[SAM3] Failed to write crop: %s", exc)
                    crop_path = None

            # Diagnostics for development tracing and explainability
            composite_conf = round(score, 4)
            diagnostics = {
                "original_sam3_query":  raw_label,
                "candidate_labels":     [raw_label],
                "menu_matching_result": matched_menu_str,
                "final_food_label":     display_label,
                "confidence":           composite_conf,
                "uncertainty":          round(1.0 - composite_conf, 4),
                "original_mask_id":     f"mask_{idx:02d}",
                "grouped_instance_id":  det.get("grouped_instance_id", f"inst_{idx:02d}"),
                "fragment_count":       det.get("fragment_count", 1),
                "decision_reason":      decision_reason,
            }

            item_entry = {
                "name":                      display_label,
                "food_name":                 display_label,
                "menu_match":                is_menu_match,
                "matched_menu_item":         matched_menu_str,
                "confidence":                composite_conf,
                "identification_confidence": composite_conf,
                "segmentation_confidence":   round(score, 4),
                "association_confidence":    1.0,  # Native unified grounding
                "menu_match_confidence":     1.0 if is_menu_match else 0.0,
                "mask":                      mask,
                "bounding_box":              box_xywh,
                "area_pixels":               area_px,
                "identification_status":     id_status,
                "top_k": [
                    {
                        "label": display_label,
                        "confidence": composite_conf,
                        "raw_similarity": composite_conf,
                    }
                ],
                "is_small_item":             is_small,
                "crop_path":                 crop_path,
                "sam3_raw_query":            raw_label,
                "diagnostics":               diagnostics,
            }
            output_items.append(item_entry)

        elapsed = time.perf_counter() - t_start
        logger.info(
            "[SAM3] Detection complete: %d food items in %.2fs (VRAM: %.0f MB)",
            len(output_items), elapsed, self.get_vram_mb(),
        )

        # ── Save Segmentation Visual Overlay & Structured JSON ───────────
        if seg_dir and output_items:
            try:
                overlay_bgr = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
                overlay = overlay_bgr.copy()
                mask_layer = overlay_bgr.copy()

                palette = [
                    (50, 205, 50),   # lime green
                    (255, 140, 0),   # deep orange
                    (238, 130, 238), # violet
                    (0, 215, 255),   # gold
                    (255, 105, 180), # hot pink
                    (30, 144, 255),  # dodger blue
                    (147, 112, 219), # medium purple
                    (0, 250, 154),   # spring green
                ]
                status_colors = {
                    "recognized": (46, 139, 87),   # sea green
                    "unlisted":   (0, 140, 255),   # orange
                    "uncertain":  (60, 60, 220),   # red
                }

                for idx, itm in enumerate(output_items):
                    m = itm.get("mask")
                    if m is not None and isinstance(m, np.ndarray):
                        mask_layer[m.astype(bool)] = palette[idx % len(palette)]

                cv2.addWeighted(mask_layer, 0.45, overlay, 0.55, 0, overlay)

                for idx, itm in enumerate(output_items, 1):
                    st = itm.get("identification_status", "uncertain")
                    color = status_colors.get(st, (0, 140, 255))
                    m = itm.get("mask")
                    if m is not None and isinstance(m, np.ndarray):
                        cnts, _ = cv2.findContours((m.astype(np.uint8) * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        cv2.drawContours(overlay, cnts, -1, color, 2)

                    bx, by, bw, bh = itm.get("bounding_box", [0, 0, 0, 0])
                    cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), color, 2)

                    lbl = f"{idx}. {itm['food_name']} ({int(itm['confidence'] * 100)}%)"
                    cv2.putText(overlay, lbl, (bx, max(20, by - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

                overlay_path = os.path.join(seg_dir, "01_sam3_segmentation_overlay.png")
                cv2.imwrite(overlay_path, overlay)

                # Save detections JSON without large ndarray
                json_items = []
                for itm in output_items:
                    c = dict(itm)
                    if isinstance(c.get("mask"), np.ndarray):
                        c["mask_shape"] = list(c["mask"].shape)
                    c["mask"] = None
                    json_items.append(c)

                json_path = os.path.join(seg_dir, "sam3_detections.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "total_items": len(output_items),
                        "food_items": json_items,
                        "elapsed_seconds": round(elapsed, 3),
                        "timestamp": datetime.datetime.now().isoformat(),
                    }, f, indent=2)
            except Exception as exc:
                logger.warning("[SAM3] Could not write segmentation diagnostics: %s", exc)

        return output_items


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------
_GLOBAL_SAM3_SEGMENTER: Optional[Sam3FoodSegmenter] = None


def get_sam3_segmenter(
    confidence_threshold: float = 0.35,
) -> Sam3FoodSegmenter:
    """Return and cache the application-wide Sam3FoodSegmenter singleton."""
    global _GLOBAL_SAM3_SEGMENTER
    if _GLOBAL_SAM3_SEGMENTER is None:
        _GLOBAL_SAM3_SEGMENTER = Sam3FoodSegmenter(
            confidence_threshold=confidence_threshold
        )
    return _GLOBAL_SAM3_SEGMENTER


def is_sam3_available() -> bool:
    """Check if SAM 3.1 checkpoint and CUDA environment are available."""
    import torch
    if not torch.cuda.is_available():
        return False
    if not os.path.isfile(SAM3_CHECKPOINT):
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("sam3") is not None
    except Exception:
        return False
