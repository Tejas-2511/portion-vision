import cv2
import numpy as np
from fastapi import APIRouter, File, UploadFile, Form

router = APIRouter()

@router.post("/estimate-portion")
async def estimate_portion(
    image: UploadFile = File(...),
    expected_items: str = Form(None)
):
    # Parse expected items if provided
    items_list = None
    if expected_items:
        items_list = [item.strip() for item in expected_items.split(",") if item.strip()]

    # Read image from upload
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_cv is None:
        return JSONResponse(status_code=400, content={"error": "Invalid image file"})

    try:
        # Step 1: Preprocess and normalize tray
        top_down_tray = process_image(img_cv)

        # Step 2 & 3: Segment and Estimate fill dynamically
        result = estimate_portions(top_down_tray, expected_items=items_list)

        return {"sections": result["sections"], "confidence": result["confidence"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
