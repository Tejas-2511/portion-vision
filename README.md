# PortionVision — Smart Nutrition & Portion Estimation

**PortionVision** is an AI-powered nutrition assistant designed for hostel and college mess environments. A user photographs their meal plate; the system identifies every food item with open-set recognition, groups visual fragments, reconstructs metric 3D heights, calculates physical mass, and compares actual intake against personalized macro targets.

---

## System Architecture

```
User uploads mess menu
        │
        ▼
   OCR (Tesseract)
   extracts menu items (contextual hints)
        │
        ▼
Recommendation Engine
(TDEE + Mifflin-St Jeor → ideal portions)
        │
        ▼
User captures plate photo
        │
        ▼
 CV Pipeline (Python FastAPI)
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ 1. Meta SAM 3 Grounding & Open-Vocabulary Segmentation                  │
 │    • ViT visual backbone encoding (1008×1008 CUDA)                      │
 │    • Non-food rejection anchors (spoon, fork, cutlery and napkin) reduce │
 │      non-food detections; available small evaluation sample does not    │
 │      establish a general false-positive rate                            │
 │    • Open-set recognition (dishes absent from menu accurately detected) │
 │    • Explicit UNKNOWN abstention (no forced menu classification)        │
 └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ 2. Dish-Level Container-Component Binding & Fragment Grouping           │
 │    • Binds solid ingredients (e.g. paneer chunks) with container bowls  │
 │    • Subsumes components into unified dish mask (prevents double-count) │
 │    • Minimum contour distance clustering for fragmented blobs (rice)    │
 │    • Strict boundary isolation for distinct touching foods (rice / dal) │
 └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ 3. Depth Anything 3 Metric + Planar Surface Normal Fitting              │
 │    • Dense metric depth in meters: Z(x, y) (DA3METRIC-LARGE)            │
 │    • Robust plane fitting: Z_plate(x, y) = Ax + By + C                  │
 │    • Tilt-free relative height: H_rel = max(0, Z_plate - Z)             │
 │    • Prior fusion: H_fused = 0.70 H_meas + 0.30 H_mid (bounded)         │
 └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ 4. Five Principal Volumetric Archetypes, Separate Condiment Model       │
 │    & Dynamic Density Tuning                                             │
 │    • Planar (rotis), Salad Slices (cucumber), Liquid Well Frustum       │
 │    • Granular Dome (rice), Chunky Suspensions (sabzi / curry)           │
 │    • Dynamic density tuning ρ(HSV, Laplacian texture)                   │
 └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
 Nutritional Calculation & Macro Propagation (Calories / Protein / Carbs / Fat)
        │
        ▼
 Portion Gap Report shown to user (Actual vs Personalized Target)
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS, PWA (Service Worker) |
| **Backend** | Node.js, Express, Tesseract.js OCR, REST APIs |
| **CV Service** | Python 3.12+, FastAPI, PyTorch (CUDA / TensorFloat-32) |
| **AI Models** | Meta SAM 3 (SAM 3.1 Multiplex), Depth Anything 3 (`DA3METRIC-LARGE`) |

---

## Repository Structure

```
portion-vision/
├── frontend/                  # React PWA — plate capture, meal slot selector, results
├── backend/                   # Node.js Express — OCR, portion recommender, DB sync
├── cv_service/                # Python FastAPI — full CV & nutrition pipeline
│   ├── api/                   #   FastAPI endpoint routes (/estimate-portion)
│   ├── config/                #   Plate geometries, density map, macro map, synonyms
│   ├── depth/                 #   Depth Anything 3 metric depth & plane normal fitting
│   ├── diagnostics/           #   RunContext — structured JSON & visual HTML reports
│   ├── estimation/            #   Mass estimator (voxel archetypes → mass → macros)
│   ├── volume/                #   Physics-informed pixel-level volume integration (V = Σ H_i × A_i)
│   ├── image_processing/      #   Quality gate (blur/tilt check) & homography warp
│   ├── open_vocab/            #   SAM 3 segmentation, open-set, instance grouper
│   │   ├── sam3_segmenter.py   #     ViT backbone, non-food anchors, container binding
│   │   ├── instance_grouper.py #     Spatial contour clustering & boundary resolution
│   │   └── pipeline.py        #     High-level orchestrator & transparent crop export
│   ├── outputs/               #   Timestamped CV run logs, masks, crops & reports
│   └── main.py                #   FastAPI server entry point
├── evaluate_example.py        # Standalone CLI tool for plate evaluation & testing
├── plate/                     # Reference plate dataset for testing & verification
├── technical.md               # Full architecture & code-level deconstruction
└── README.md                  # Project overview & documentation
```

---

## Quick Start

Run the three services in separate terminals from the repository root:

### 1. CV Service (Python FastAPI)

```powershell
cd cv_service

# Run directly with the sam3 environment Python (recommended on Windows):
& "C:\Users\tejas\.conda\envs\sam3\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Alternatively, if conda is configured in your shell:
conda activate sam3
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Backend (Node.js)

```powershell
cd backend
npm run dev
```
Backend runs on `http://localhost:5000`.

### 3. Frontend (React / Vite)

```powershell
cd frontend
npm run dev
```
Frontend runs on `http://localhost:5173`. Open in a browser or scan the network URL on mobile.

---

## Key Computer Vision Features

### 1. Grounded Open-Set Recognition & Unknown Abstention
- The mess menu acts as **contextual guidance**, never as a mandatory classification list.
- Identifies dishes absent from the menu (`identification_status: "open_set"`, `menu_match: false`).
- Ambiguous regions with confidence $< 0.45$ receive an explicit `identification_status: "unknown"` abstention rather than being forced into an incorrect menu label.

### 2. Dish-Level Container-Component Binding
- Prepared composite dishes (e.g. Palak Paneer) are recognized as complete items.
- Solid ingredients (paneer cubes, chicken) contained within a bowl ($\ge 70\%$ inclusion) bind to the host dish's identity, preventing the green spinach gravy from being misclassified as Dal Tadka.
- Contained solids are unified into the host dish mask, preventing mass double-counting.

### 3. Spatial Instance Grouper
- Groups fragmented masks (e.g. multiple cucumber slices in a salad or scattered rice clusters) using minimum Euclidean contour distance ($75\,\text{px}$ for rice, $112.5\,\text{px}$ for salads).
- Disparate touching foods (e.g. rice and dal) are strictly preserved as separate items.
- Overlapping boundary pixels are assigned via argmax confidence to prevent duplicate voxel calculations.

### 4. Physics-Informed Pixel-Level Voxel Integration ($V = \sum H_i \times A_i$)
- Replaced scalar heuristic approximations with true pixel-level volume integration:
  $$V = \sum_{i \in \mathcal{M}_{\text{valid}}} \left( H_i^{\text{eff}} \times A_i \right) \quad [\text{cm}^3 \equiv \text{ml}]$$
- Grounds elevations to the local support base ($\Delta H_i = \max(0.0, H_i - p_5)$), eliminating baseline drift and perspective tilt artifacts.
- Preserves the 5 physical archetypes: Planar Laminate (`chapati`), Sliced Salad (`cucumber`), Liquid Frustum (`dal`), Mounded Grain (`rice`), Chunky Suspension (`paneer`/`sabzi`), plus Condiment Dollops (`pickle`).
- Strict inlier masking ($\mathcal{M}_{\text{valid}}$) rejects NaNs, non-finite values, and specular glare spikes.

---

## CV Inspection & Verification Tools

### 1. Standalone Plate Evaluation CLI
Run PortionVision's full pipeline on any custom plate image:

```powershell
conda activate sam3

# Default plate with standard mess menu:
python evaluate_example.py

# Custom plate image with specific menu items:
python evaluate_example.py --image "plate/use/IMG20260408201758.jpg" --menu "palak paneer, dal, steamed rice, green salad"

# Open-world discovery mode (no menu provided):
python evaluate_example.py --image "plate/use/IMG20260402200840.jpg" --open-world
```

### 2. Presentation & Benchmark Outputs
Curated presentation artifacts for all 7 reference plates are available in:
- `cv_service/outputs/temp/` (and root `outputs/temp/`, `output/temp/`)

Each plate directory includes:
- `01_original_photo.png` — raw top-down tray capture
- `02_sam3_segmentation_overlay.png` — Meta SAM 3 open-vocabulary masks
- `03_metric_depth_colored.png` — Depth Anything 3 metric depth map
- `04_height_relative_colored.png` — tray-normalized relative elevation
- `05_3D_topographic_relief_map.png` — 3D relief surface rendering
- `06_voxel_volume_integration_regions.png` — calibrated pixel-level voxel integration
- `07_final_annotated_portions.png` — portion labels, masses (g), and confidence scores
- `report.html` & `results.json` — complete metrology metrics and macronutrient breakdown

---

## Configuration & Settings

| Variable / Setting | Default | Description |
|---|---|---|
| `ALLOW_OCR_DB_UPDATE` | `false` | Controls whether scanned menu items automatically add new stub entries to `foodDatabase.json`. Can be configured via environment variable or backend config. |
| `QUALITY_BLUR_THRESHOLD` | `80` | Laplacian variance threshold for motion blur detection. |
| `QUALITY_TILT_THRESHOLD` | `30°` | Maximum allowable plate tilt before triggering retake prompt. |

---

## Hardware Requirements

| Component | Minimum | Recommended / Tested |
|---|---|---|
| **GPU** | Depends on model configuration and inference settings | Tested on NVIDIA RTX 3050 Laptop GPU (6 GB VRAM) |
| **System RAM** | 8 GB | 16 GB+ |
| **Storage** | 10 GB free space (model weights) | NVMe SSD |
| **OS** | Windows 10/11 or Ubuntu 22.04+ | Windows 11 |

---

## Documentation

For an in-depth, function-by-function architectural deconstruction, mathematical formulations, and validation metrics, refer to [`technical.md`](technical.md).
