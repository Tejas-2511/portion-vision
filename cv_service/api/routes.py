"""
FastAPI routes for portion estimation and menu OCR.
"""

import cv2
import logging
import numpy as np
from datetime import datetime, timezone
from fastapi import APIRouter, File, UploadFile, Form
from fastapi.responses import JSONResponse

from estimation.mass_estimator import estimate_food_mass
from ocr.menu_ocr import extract_menu_text

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/estimate-portion")
async def estimate_portion(
    image: UploadFile = File(...),
    expected_items: str = Form(None),
    plate_profile: str = Form(None),
):
    """
    Estimate food mass from a plate image.

    - **image**: JPEG/PNG of the mess plate
    - **expected_items**: comma-separated food names (optional, for labeling)
    - **plate_profile**: plate type key (optional, defaults to standard_mess_thali)

    Returns:
    ```json
    {
        "food_items": [
            {"name": "dal", "volume_ml": 120.5, "mass_g": 126.5},
            ...
        ],
        "confidence": 0.82
    }
    ```
    """
    # Parse expected items
    items_list = None
    if expected_items:
        items_list = [item.strip() for item in expected_items.split(",") if item.strip()]

    # Read image bytes → OpenCV BGR
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return JSONResponse(status_code=400, content={"error": "Invalid image file"})

    try:
        result = estimate_food_mass(
            image_bgr=img_bgr,
            expected_items=items_list,
            plate_profile=plate_profile,
        )
        return result

    except Exception as e:
        logger.exception("Portion estimation failed")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/ocr")
async def ocr_menu(
    image: UploadFile = File(...),
):
    """
    Extract menu items from an uploaded image using PaddleOCR.

    - **image**: JPEG/PNG of a mess menu (whiteboard, printout, etc.)

    Returns:
    ```json
    {
        "items": ["chapati", "dal fry", "rice", ...],
        "date": "2026-03-30T19:25:00Z"
    }
    ```
    """
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return JSONResponse(status_code=400, content={"error": "Invalid image file"})

    try:
        result = extract_menu_text(img_bgr)
        return {
            "items": result["items"],
            "date": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("Menu OCR failed")
        return JSONResponse(status_code=500, content={"error": str(e)})

