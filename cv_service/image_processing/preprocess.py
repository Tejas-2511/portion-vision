"""
Image preprocessing — resize, denoise, enhance, perspective warp.

Each intermediate result is saved when a RunContext is provided.
"""

import time
import cv2
import numpy as np


def process_image(
    image: np.ndarray,
    target_long_edge: int = 1024,
    ctx=None,
) -> np.ndarray:
    """
    Preprocess the input image:
    1. Resize for consistency (longest edge → target_long_edge px)
    2. Gaussian denoise
    3. Color normalization (LAB-based)
    4. Contrast enhancement (CLAHE on L channel)
    5. Detect the plate boundary
    6. Apply perspective transform to get a top-down view

    When ctx (RunContext) is provided AND ctx.debug is True,
    every intermediate image is saved to the preprocessing/ folder.

    Returns the warped (or enhanced) image.
    """
    debug = ctx is not None and ctx.debug

    # ── 1. Resize ────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    height, width = image.shape[:2]
    scale = target_long_edge / max(height, width)
    resized = cv2.resize(image, (int(width * scale), int(height * scale)))
    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("preprocessing")
        fname = f"{idx:02d}_resized.png"
        ctx.save_image("preprocessing", fname, resized)
        ctx.log("Preprocessing", "Resize applied",
                {"original": f"{width}x{height}", "target_long_edge": target_long_edge,
                 "scale": round(scale, 4)},
                elapsed=elapsed, output_file=fname)

    # ── 2. Gaussian denoise ──────────────────────────────────────────────
    t0 = time.perf_counter()
    denoised = cv2.GaussianBlur(resized, (5, 5), 0)
    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("preprocessing")
        fname = f"{idx:02d}_denoised.png"
        ctx.save_image("preprocessing", fname, denoised)
        ctx.log("Preprocessing", "Gaussian blur applied",
                {"kernel": 5}, elapsed=elapsed, output_file=fname)

    # ── 3. Color normalization (LAB mean-shift) ──────────────────────────
    t0 = time.perf_counter()
    lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_ch, a_ch, b_ch = cv2.split(lab)
    l_ch -= l_ch.mean(); l_ch += 128.0
    a_ch -= a_ch.mean(); a_ch += 128.0
    b_ch -= b_ch.mean(); b_ch += 128.0
    lab = cv2.merge([l_ch, a_ch, b_ch]).clip(0, 255).astype(np.uint8)
    color_normalized = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("preprocessing")
        fname = f"{idx:02d}_color_normalized.png"
        ctx.save_image("preprocessing", fname, color_normalized)
        ctx.log("Preprocessing", "LAB color normalization applied",
                elapsed=elapsed, output_file=fname)

    # ── 4. CLAHE contrast enhancement ────────────────────────────────────
    t0 = time.perf_counter()
    lab2 = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB)
    l2, a2, b2 = cv2.split(lab2)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l2)
    enhanced = cv2.cvtColor(cv2.merge([l2, a2, b2]), cv2.COLOR_LAB2BGR)
    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("preprocessing")
        fname = f"{idx:02d}_contrast_enhanced.png"
        ctx.save_image("preprocessing", fname, enhanced)
        ctx.log("Preprocessing", "CLAHE contrast enhancement applied",
                {"clip_limit": 2.0, "tile_grid": "8x8"},
                elapsed=elapsed, output_file=fname)

    # ── 5–6. Edge detection → perspective warp ───────────────────────────
    t0 = time.perf_counter()
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    output = resized  # default — no warp
    warped = False

    if contours:
        largest = max(contours, key=cv2.contourArea)
        epsilon = 0.02 * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)
        if len(approx) == 4:
            output = _four_point_transform(resized, approx.reshape(4, 2))
            warped = True

    elapsed = time.perf_counter() - t0

    if debug:
        # Save edge detection result
        idx = ctx.next_index("preprocessing")
        fname = f"{idx:02d}_edges.png"
        ctx.save_image("preprocessing", fname, edges)
        ctx.log("Preprocessing", "Canny edge detection",
                {"low": 50, "high": 150},
                elapsed=elapsed, output_file=fname)

        # Save final warped/output
        idx = ctx.next_index("preprocessing")
        fname = f"{idx:02d}_perspective_warp.png"
        ctx.save_image("preprocessing", fname, output)
        ctx.log("Preprocessing", "Perspective warp" if warped else "Warp skipped (no 4-pt contour)",
                {"warped": warped},
                output_file=fname)

    return output


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
