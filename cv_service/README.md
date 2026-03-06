# Portion Vision CV Service

This is a Python microservice built with FastAPI that estimates food portion sizes from tray images using Computer Vision.

## Architecture
- **API**: FastAPI endpoints (`/estimate-portion`)
- **Image Processing**: OpenCV for Gaussian Blur, edge detection, and perspective transform.
- **Segmentation**: K-Means clustering (via scikit-learn) to separate food from the tray background.
- **Portion Estimation**: Bounding box cropping and fill-ratio calculation against max gram capacities.

## Installation & Setup

1. **Create a virtual environment (optional but recommended)**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server**:
   ```bash
   python main.py
   ```
   The service will start on `http://localhost:8000`.

## API Usage

**Endpoint**: `POST /estimate-portion`

**Input Format**: `multipart/form-data` with an `image` file.

**Example Request using cURL**:
```bash
curl -X POST "http://localhost:8000/estimate-portion" -H "accept: application/json" -H "Content-Type: multipart/form-data" -F "image=@/path/to/your/tray_image.jpg"
```

**Expected Output**:
```json
{
  "sections": {
    "rice": 210,
    "dal": 130,
    "sabzi": 95,
    "salad": 40
  },
  "confidence": 0.82
}
```
