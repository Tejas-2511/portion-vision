"""
FastAPI routes for portion estimation.
OCR is handled in the Node.js backend via Tesseract.js.
"""

import cv2
import logging
import numpy as np
from fastapi import APIRouter, File, UploadFile, Form
from fastapi.responses import JSONResponse

from estimation.mass_estimator import estimate_food_mass

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/estimate-portion")
async def estimate_portion(
    image: UploadFile = File(...),
    expected_items: str = Form(None),
    plate_profile: str = Form(None),
    debug: bool = Form(True),
):
    """
    Estimate food mass from a plate image.

    - **image**: JPEG/PNG of the mess plate
    - **expected_items**: comma-separated food names (optional, for labeling)
    - **plate_profile**: plate type key (optional, defaults to standard_mess_thali)
    - **debug**: when true, saves ALL intermediate pipeline outputs to
      `outputs/<run_id>/` and generates an HTML report

    Returns:
    ```json
    {
        "food_items": [
            {"name": "dal", "volume_ml": 120.5, "mass_g": 126.5},
            ...
        ],
        "confidence": 0.82,
        "_debug": { "run_id": "...", "run_dir": "...", "report": "..." }
    }
    ```
    """
    items_list = None
    if expected_items:
        items_list = [item.strip() for item in expected_items.split(",") if item.strip()]

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
            debug=debug,
        )
        # #7 — Quality gate failure is returned as a 422 with a user-friendly message
        if result.get("error_type") == "image_quality":
            return JSONResponse(
                status_code=422,
                content={
                    "error":   result["error"],
                    "type":    "image_quality",
                    "message": result["error"],
                },
            )
        return result

    except Exception as e:
        logger.exception("Portion estimation failed")
        return JSONResponse(status_code=500, content={"error": str(e)})
