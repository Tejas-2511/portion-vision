"""
Portion Vision — Computer Vision Microservice

FastAPI application for food mass estimation from mess plate images.
Uses SAM for segmentation, MiDaS for depth, and per-pixel volume integration.
"""

import logging
from fastapi import FastAPI
from api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s",
)

app = FastAPI(
    title="Portion Vision CV Service",
    description="Estimates food mass from a sectioned mess plate image using computer vision.",
    version="2.0.0",
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
