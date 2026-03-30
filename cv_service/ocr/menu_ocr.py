"""
Menu OCR Service using PaddleOCR.

Extracts text from mess menu images and parses individual food items.
PaddleOCR provides superior accuracy for structured text layouts like
printed menus, whiteboards, and handwritten lists compared to Tesseract.
"""

import logging
import re
from typing import List, Optional

import cv2
import numpy as np
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)

# Singleton — PaddleOCR loads models on first init (~2-3s), reuse after that
_ocr_instance: Optional[PaddleOCR] = None


def _get_ocr() -> PaddleOCR:
    """Lazy-initialise a PaddleOCR instance (English, angle classifier on)."""
    global _ocr_instance
    if _ocr_instance is None:
        logger.info("Initialising PaddleOCR engine …")
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,   # Handle rotated text
            lang="en",            # English for menu items
        )
        logger.info("PaddleOCR engine ready.")
    return _ocr_instance


# ── Text cleaning ────────────────────────────────────────────────────────

# Common header / noise words that should be removed from extracted items
_BLACKLIST = {
    "menu", "breakfast", "lunch", "dinner", "snack", "snacks",
    "today", "date", "day", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
    "mess", "hostel", "canteen", "cafeteria",
    "special", "note", "notes", "timings", "timing",
}


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip non-alpha noise at edges."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z\s/,&\-]", "", text)   # keep letters + separators
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_items(line: str) -> List[str]:
    """Split a single OCR line into individual food items."""
    # Split on common delimiters found in mess menus
    parts = re.split(r"[,/&|+]", line)
    return [p.strip() for p in parts if p.strip()]


def clean_menu_items(raw_lines: List[str]) -> List[str]:
    """
    Clean and deduplicate extracted OCR lines into a sorted list of
    individual food items, filtering out headers and noise.
    """
    items: List[str] = []

    for line in raw_lines:
        normalised = _normalise(line)
        if not normalised or len(normalised) < 3:
            continue

        for item in _split_items(normalised):
            if len(item) < 3:
                continue
            # skip if the entire token is a blacklisted word
            if item in _BLACKLIST:
                continue
            # skip if every word in the item is blacklisted
            words = item.split()
            if all(w in _BLACKLIST for w in words):
                continue
            items.append(item)

    # Deduplicate preserving first occurrence, then sort
    seen = set()
    unique: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    unique.sort()
    return unique


# ── Public API ───────────────────────────────────────────────────────────

def extract_menu_text(image_bgr: np.ndarray) -> dict:
    """
    Run PaddleOCR on an image and return structured menu data.

    Parameters
    ----------
    image_bgr : np.ndarray
        OpenCV BGR image (as read by cv2.imread or from upload bytes).

    Returns
    -------
    dict
        {
            "raw_text": str,        # full OCR dump for debugging
            "items": List[str],     # cleaned, deduplicated food items
        }
    """
    ocr = _get_ocr()

    # PaddleOCR expects RGB
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    # Run OCR — returns list of list of (bbox, (text, confidence))
    results = ocr.ocr(image_rgb)

    # Flatten all detected text lines
    raw_lines: List[str] = []
    if results and results[0]:
        for detection in results[0]:
            text = detection[1][0]       # extracted string
            confidence = detection[1][1]  # confidence score
            if confidence > 0.5:         # skip low-confidence noise
                raw_lines.append(text)

    raw_text = "\n".join(raw_lines)
    items = clean_menu_items(raw_lines)

    logger.info(
        "OCR extracted %d raw lines → %d cleaned items", len(raw_lines), len(items)
    )

    return {
        "raw_text": raw_text,
        "items": items,
    }
