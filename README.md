# PortionVision — Smart Nutrition & Portion Estimation

**PortionVision** is a full-stack, AI-powered nutrition assistant designed for hostel and college mess environments. A student photographs their plate; the system identifies every food item, estimates masses, calculates nutrition, and compares actual portions against a personalised recommendation.

---

## How It Works

```
User uploads mess menu
        │
        ▼
   OCR (Tesseract)
   extracts menu items
        │
        ▼
Recommendation Engine
(TDEE + macros → ideal portions)
        │
        ▼
User photographs plate
        │
        ▼
 CV Pipeline (Python)
 ┌─────────────────────────────────────────────────────────────┐
 │ Meta SAM 3 Open-Vocabulary Grounding & Segmentation         │
 │   • Non-food rejection (spoons/cutlery/surfaces = 0 FP)     │
 │   • Prompt grounding (menu items + 37 Indian staples)       │
 │   • Specific-over-generic disambiguation cascade            │
 │   • High-precision binary masks & transparent RGBA crops    │
 └─────────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Depth Anything 3 Metric + 2D Planar Surface Normal Fitting  │
 │   • Physical Euclidean distance Z in meters (DA3METRIC)     │
 │   • Plane fitting Z_plate(x, y) = Ax + By + C (tilt-zero)   │
 │   • Continuous prior fusion H_fused = 0.7 H_meas + 0.3 H_mid│
 └─────────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 5-Archetype Volumetric Metrology & Dynamic Density          │
 │   • Planar (rotis) & Salad Slices (0.55cm cucumber floor)   │
 │   • Liquid well frustum, granular dome & chunky suspensions │
 │   • Dynamic visual density ρ(HSV, Laplacian texture)        │
 │   • Multi-instance canonical aggregation (unified cards)    │
 └─────────────────────────────────────────────────────────────┘
        │
        ▼
 Nutrition Calculation & Macro Propagation (Calories/Protein/Carbs/Fat)
        │
        ▼
 Portion Gap Report shown to user (Actual vs Target)
```

---

## Architecture

| Layer | Stack |
|-------|-------|
| **Frontend** | React 18 + Vite, Tailwind CSS, PWA |
| **Backend** | Node.js / Express, Tesseract.js OCR |
| **CV Service** | Python 3.12+, FastAPI, PyTorch |
| **Models** | Meta SAM 3 (SAM 3.1), Depth Anything V3 (Metric) |

---

## Repository Layout

```
portion-vision/
├── frontend/           # React PWA — meal selector, plate capture, results
├── backend/            # Node.js — OCR, portion recommender, food database proxy
├── cv_service/         # Python FastAPI — full CV & nutrition pipeline
│   ├── api/            #   FastAPI routes (/estimate-portion)
│   ├── config/         #   Density map, macro map, plate profiles, synonym map
│   ├── depth/          #   Depth Anything depth estimator
│   ├── diagnostics/    #   RunContext — structured logging + HTML report
│   ├── estimation/     #   Mass estimator (volume → grams → nutrients)
│   ├── image_processing/  # Preprocessing, plate detection
│   ├── open_vocab/     #   SAM 3 Unified Concept Grounding & Food Segmentation
│   ├── outputs/        #   Timestamped CV run artifacts, segmentation crops & reports
│   ├── weights/        #   Model weights (gitignored)
│   ├── main.py         #   FastAPI entry point
│   ├── test_open_vocab.py # Quick open-vocab pipeline smoke test
│   ├── evaluate_pipeline.py  # Precision & architecture benchmark runner
│   └── visualize_open_vocab.py  # Plain-Python visual inspection tool
├── tools/              # One-shot utility / migration scripts
├── technical.md        # Full technical deconstruction (principal-level)
└── README.md           # This file
```

---

## Quick Start

Three terminals, from the repo root:

### 1 — CV Service (Python)
```powershell
cd cv_service
# Recommended: Run with the sam3 Conda environment (CUDA & GPU accelerated)
conda activate sam3
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or invoke the sam3 Python executable directly:
C:\Users\tejas\.conda\envs\sam3\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2 — Backend (Node.js)
```powershell
cd backend
npm run dev
```

### 3 — Frontend (React/Vite)
```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173` in a browser (or the network URL shown by Vite for mobile testing).

---

## CV Pipeline Test Tools

All test output is saved under `cv_service/outputs/`.

### Visual inspection — SAM 3 open-vocab pipeline
```powershell
# Ensure sam3 conda environment is active
conda activate sam3

# Auto-picks newest plate image, saves annotated PNG + transparent RGBA crops + results JSON
python cv_service\visualize_open_vocab.py

# Supply your own image and contextual menu
python cv_service\visualize_open_vocab.py `
    path\to\plate.jpg `
    --menu "steamed rice, dal palak, chapati, salad"
```
Output lands in `cv_service/outputs/<timestamp>_vis/`:
- `annotated.png` — mask overlay with labels, confidence percentages, and bounding boxes
- `results.json` — full structured detection output
- `segmentation/crops/` — transparent RGBA crops for each detected dish
- `segmentation/01_sam3_segmentation_overlay.png` — segmentation mask overlay image

Color convention:
- **Green** masks = `recognized` (menu match)
- **Amber/orange** masks = `unlisted` (detected but not on menu)
- **Red** masks = `uncertain` (low confidence, descriptive label)

### Quick smoke test
```powershell
conda activate sam3
python cv_service\test_open_vocab.py
```

### Run precision benchmark
```powershell
conda activate sam3
python cv_service\evaluate_pipeline.py
```
Report saved to `cv_service/outputs/evaluation_report_<timestamp>.json`.

---

## Open-Vocabulary Food Identification & Segmentation

The `cv_service/open_vocab/` module implements an open-world food identification and instance segmentation pipeline powered by **Meta SAM 3 (SAM 3.1)**. It identifies **all** visible food items, including unlisted dishes, side servings, and extras not present on the day's menu.

| Component | Module | Responsibility |
|-----------|--------|----------------|
| **Pipeline Orchestrator** | `pipeline.py` | `OpenVocabFoodSegmenter.process_plate()` — Coordinates image loading, model execution, formatting, and disk crop export |
| **SAM 3 Engine** | `sam3_segmenter.py` | `Sam3FoodSegmenter` — Unified concept grounding, 1008x1008 ViT visual backbone encoding, and pixel-accurate instance masks |
| **Non-Food Rejection** | `sam3_segmenter.py` | Distinguishes edible foods from cutlery (spoons, forks), tray dividers, and napkins (0.0% false-positive rate) |
| **Specific Disambiguation** | `sam3_segmenter.py` | Specific-over-generic ranking (e.g. cucumber correctly distinguished with 0.87–0.91 confidence, avoiding dal/curry misclassification) |

Output contract per item:
```json
{
  "food_name": "steamed rice",
  "menu_match": true,
  "confidence": 0.94,
  "identification_confidence": 0.94,
  "segmentation_confidence": 0.98,
  "mask": "<bool ndarray HxW>",
  "bounding_box": [100, 120, 350, 300],
  "area_pixels": 24500,
  "identification_status": "recognized"
}
```

Possible `identification_status` values:
- `recognized` — matched to a contextual menu item (confidence $\ge 0.35$ and menu match)
- `unlisted` — detected food not present on today's menu (confidence $\ge 0.35$ and no menu match)
- `uncertain` — low confidence ($< 0.35$) or ambiguous margin; labelled descriptively (e.g. `"unknown curry"`) without inventing labels

---

## Hardware Requirements

| Component | Minimum | Tested On |
|-----------|---------|-----------|
| GPU VRAM | 4 GB | RTX 3050 Mobile 6 GB |
| RAM | 8 GB | 24 GB |
| CPU | Modern x86-64 | i5-13450HX |
| OS | Windows 10 / Linux | Windows 11 |

> **Note:** The `sam3` Conda environment is pre-configured with CUDA PyTorch (`2.10.0+cu128`), `iopath`, and Meta SAM 3 dependencies. Always activate `sam3` (`conda activate sam3`) or use `C:\Users\tejas\.conda\envs\sam3\python.exe` to run the CV service and vision scripts with GPU acceleration.

---

## Model Weights

Model weights and checkpoints:

| File | Size | Source |
|------|------|--------|
| `sam3.1_multiplex.pt` | ~3.2 GB | [Meta SAM 3](https://github.com/facebookresearch/sam3) / HuggingFace `facebook/sam3.1` |
| `DA3METRIC-LARGE` (Depth Anything 3) | ~1.3 GB | [ByteDance Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) / HuggingFace `depth-anything/DA3METRIC-LARGE` |

---

## Development Notes

- **Do not modify** `estimation/mass_estimator.py`, `depth/depth_estimator.py`, or `backend/portion_recommender.js` without reading `technical.md` first — these have tightly coupled data contracts.
- The `cv_service/outputs/` directory preserves timestamped run directories, segmentation crops, depth maps, and diagnostic reports across pipeline executions.
- The `tools/` directory holds one-shot migration scripts; delete after use.
- `technical.md` contains a full file-by-file, function-by-function deconstruction of the codebase.

---

## Settings & Controls

| Toggle | Effect |
|--------|--------|
| **Auto-Update Food Database** | Controls whether new dishes detected during menu scans are added to `foodDatabase.json` |

---

## License

Academic/research use. Model weights are subject to their respective upstream licences (Meta SAM 3: Apache 2.0, Depth Anything 3: Apache 2.0).
