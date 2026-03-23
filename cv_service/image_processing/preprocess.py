"""
Image preprocessing — resize, perspective warp to get a top-down plate view.
"""

import cv2
import numpy as np


def process_image(image: np.ndarray, target_long_edge: int = 1024) -> np.ndarray:
    """
    Preprocess the input image:
    1. Resize for consistency (longest edge → target_long_edge px)
    2. Detect the plate boundary
    3. Apply perspective transform to get a top-down view

    Returns the warped (or resized-only) image.
    """
    height, width = image.shape[:2]
    scale = target_long_edge / max(height, width)
    resized = cv2.resize(image, (int(width * scale), int(height * scale)))

    # Detect plate boundary via edge detection
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return resized

    largest = max(contours, key=cv2.contourArea)

    # Approximate to a polygon — if 4 corners found, warp to top-down view
    epsilon = 0.02 * cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, epsilon, True)

    if len(approx) == 4:
        return _four_point_transform(resized, approx.reshape(4, 2))

    return resized


# ── Internal helpers ─────────────────────────────────────────────────────

def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]   # top-right
    rect[3] = pts[np.argmax(d)]   # bottom-left
    return rect


def _four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Perspective-warp image so the 4-point region fills the output rectangle."""
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect

    w = int(max(
        np.linalg.norm(br - bl),
        np.linalg.norm(tr - tl),
    ))
    h = int(max(
        np.linalg.norm(tr - br),
        np.linalg.norm(tl - bl),
    ))

    dst = np.array([
        [0, 0],
        [w - 1, 0],
        [w - 1, h - 1],
        [0, h - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (w, h))
