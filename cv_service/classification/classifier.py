"""
Food classification using MobileNetV3-Small (ImageNet pre-trained).

Pipeline:  SAM mask → crop → 224×224 → MobileNetV3 → label + confidence

The ImageNet label space is bridged to Indian food categories via a curated
mapping.  If OCR-derived 'allowed_labels' are supplied, classifier output is
re-ranked so only OCR-confirmed items can win.

To swap in a fine-tuned checkpoint, place it at:
    cv_service/weights/food_classifier.pth
It must be a state-dict for MobileNetV3-Small with the same head (1000 classes).
If a fine-tuned head uses a different output size, extend _LABEL_TO_FOOD_MAP.

# TODO: fine-tune on Indian food dataset for production accuracy.
"""

from __future__ import annotations

import os
import logging
import time
import cv2
import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# ── Lazy-loaded global model ─────────────────────────────────────────────────
_model      = None
_transforms = None
_device     = None

# ── OCR boost multiplier: score of OCR-allowed labels is amplified by this ──
OCR_BOOST = 2.5

# ── ImageNet class index → canonical Indian food label ───────────────────────
# Keys are ImageNet class *names* (lowercase, partial substring match is used).
# Maps to the same canonical names used in density_map.py / macro_map.py.
_IMAGENET_TO_FOOD: dict[str, str] = {
    # Grains / breads
    "pretzel":          "roti",
    "bagel":            "roti",
    "french loaf":      "roti",
    "pizza":            "roti",
    "flatbread":        "roti",
    "pancake":          "roti",
    "pita":             "roti",
    "naan":             "naan",
    "waffle":           "paratha",
    # Rice-like
    "pilaf":            "rice",
    "risotto":          "rice",
    "congee":           "khichdi",
    "burrito":          "rice",
    # Lentils / soups
    "soup":             "dal",
    "consomme":         "dal",
    "chowder":          "sambar",
    "stew":             "dal",
    "gravy":            "dal",
    # Vegetables
    "broccoli":         "gobi",
    "cauliflower":      "gobi",
    "eggplant":         "baingan",
    "zucchini":         "sabzi",
    "spinach":          "dal palak",
    "okra":             "bhindi",
    "potato":           "aloo",
    "french fries":     "aloo",
    "hash brown":       "aloo",
    "mixed vegetables": "mixed veg",
    "cabbage":          "sabzi",
    "carrot":           "sabzi",
    "pea":              "sabzi",
    # Protein
    "chicken":          "chicken",
    "hen":              "chicken",
    "drumstick":        "chicken",
    "chicken wing":     "chicken",
    "fried chicken":    "chicken curry",
    "roast chicken":    "chicken",
    "fish":             "fish curry",
    "salmon":           "fish curry",
    "sushi":            "fish curry",
    "egg":              "egg",
    "omelette":         "egg curry",
    "deviled egg":      "egg",
    "meat loaf":        "mutton",
    "pork":             "mutton",
    "beef":             "mutton",
    "cheese":           "paneer",
    "cottage cheese":   "paneer",
    "tofu":             "paneer",
    # Accompaniments
    "dip":              "chutney",
    "guacamole":        "chutney",
    "hummus":           "chutney",
    "sauce":            "chutney",
    "yogurt":           "curd",
    "custard":          "raita",
    "pudding":          "kheer",
    "salad":            "salad",
    "coleslaw":         "salad",
    # Sweets
    "chocolate":        "halwa",
    "brownie":          "halwa",
    "doughnut":         "gulab jamun",
    "muffin":           "halwa",
    "ice cream":        "kheer",
    "cake":             "barfi",
    "cookie":           "laddu",
    "sweet":            "halwa",
}

# Ordered list of known food labels (canonical names from density_map)
ALL_FOOD_LABELS: list[str] = sorted(set(_IMAGENET_TO_FOOD.values()))


def _load_model() -> None:
    """Lazy-load MobileNetV3-Small. Checks for fine-tuned weights first."""
    global _model, _transforms, _device

    if _model is not None:
        return

    from torchvision import models, transforms
    from torchvision.models import MobileNet_V3_Small_Weights

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Check for fine-tuned checkpoint
    weights_path = os.path.join(
        os.path.dirname(__file__), "..", "weights", "food_classifier.pth"
    )
    if os.path.exists(weights_path):
        logger.info(f"Loading fine-tuned classifier from {weights_path}")
        _model = models.mobilenet_v3_small(weights=None)
        state = torch.load(weights_path, map_location=_device)
        _model.load_state_dict(state)
    else:
        logger.info("Loading ImageNet MobileNetV3-Small (no fine-tuned weights found)")
        _model = models.mobilenet_v3_small(
            weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1
        )

    _model.to(_device)
    _model.eval()

    # Standard ImageNet preprocessing
    _transforms = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    logger.info(f"Food classifier loaded on {_device}")


def _imagenet_idx_to_food_label(idx: int, imagenet_classes: list[str]) -> str | None:
    """Map a single ImageNet class index to a food label (or None if no match)."""
    class_name = imagenet_classes[idx].lower()
    for keyword, food in _IMAGENET_TO_FOOD.items():
        if keyword in class_name:
            return food
    return None


def _get_imagenet_classes() -> list[str]:
    """Return the 1000 ImageNet class names from torchvision."""
    from torchvision.models import MobileNet_V3_Small_Weights
    return MobileNet_V3_Small_Weights.IMAGENET1K_V1.meta["categories"]


def classify_mask_region(
    image_bgr: np.ndarray,
    mask: np.ndarray,
    allowed_labels: list[str] | None = None,
    top_k: int = 3,
) -> dict:
    """
    Classify the food item inside a binary mask region.

    Args:
        image_bgr:      Full BGRimage (same shape as mask).
        mask:           Boolean mask (H, W) — True = food pixels.
        allowed_labels: If provided (from OCR), only these labels can win.
                        Other labels get their probability dampened.
        top_k:          Number of alternatives to return.

    Returns:
        {
            "label":      str,    # best food label
            "confidence": float,  # 0–1 confidence for that label
            "top_k":      [{"label": str, "confidence": float}, ...],
        }
    """
    t0 = time.perf_counter()
    _load_model()

    # ── Crop the bounding box of the mask ────────────────────────────────────
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return {"label": "unknown", "confidence": 0.0, "top_k": []}

    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    crop_bgr = image_bgr[r0:r1+1, c0:c1+1]

    # Blank-out non-mask pixels in the crop so the model focuses on the food
    crop_mask = mask[r0:r1+1, c0:c1+1]
    crop_bgr = crop_bgr.copy()
    crop_bgr[~crop_mask] = 127  # neutral grey background

    # BGR → RGB
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)

    # ── Inference ─────────────────────────────────────────────────────────────
    tensor = _transforms(crop_rgb).unsqueeze(0).to(_device)

    with torch.no_grad():
        logits = _model(tensor)          # (1, 1000)

    probs = F.softmax(logits[0], dim=0).cpu().numpy()  # (1000,)

    # ── Map ImageNet indices → food labels, aggregate probabilities ───────────
    imagenet_classes = _get_imagenet_classes()
    food_scores: dict[str, float] = {}

    for idx in range(len(probs)):
        food = _imagenet_idx_to_food_label(idx, imagenet_classes)
        if food:
            food_scores[food] = food_scores.get(food, 0.0) + float(probs[idx])

    # Normalise so scores sum to 1 across known food labels
    total = sum(food_scores.values())
    if total > 0:
        food_scores = {k: v / total for k, v in food_scores.items()}
    else:
        # Fall back — return unknown
        return {"label": "unknown", "confidence": 0.0, "top_k": []}

    # ── Apply OCR boost ───────────────────────────────────────────────────────
    if allowed_labels:
        allowed_set = {lbl.strip().lower() for lbl in allowed_labels}
        
        def is_allowed(food_str: str) -> bool:
            # Check if canonical food name is substring of any OCR label, or vice versa
            food_str = food_str.lower()
            for allowed in allowed_set:
                if food_str in allowed or allowed in food_str:
                    return True
            return False

        food_scores = {
            food: (score * OCR_BOOST if is_allowed(food) else score)
            for food, score in food_scores.items()
        }
        # Re-normalise after boost
        total = sum(food_scores.values())
        food_scores = {k: v / total for k, v in food_scores.items()}

    # ── Build sorted results ──────────────────────────────────────────────────
    ranked = sorted(food_scores.items(), key=lambda x: x[1], reverse=True)
    best_label, best_conf = ranked[0]

    top_k_results = [
        {"label": lbl, "confidence": round(conf, 4)}
        for lbl, conf in ranked[:top_k]
    ]

    elapsed = time.perf_counter() - t0
    logger.debug(
        f"classify_mask_region → {best_label} ({best_conf:.3f}) "
        f"[OCR boost={'yes' if allowed_labels else 'no'}] "
        f"in {elapsed:.3f}s"
    )

    return {
        "label":      best_label,
        "confidence": round(best_conf, 4),
        "top_k":      top_k_results,
    }
