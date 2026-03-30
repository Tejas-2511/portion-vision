# PortionVision — Technical Documentation

## Overview

PortionVision is a smart nutrition assistant that helps users balance their meals in a college/office mess setting. It:

1. **Digitizes mess menus** using OCR (Tesseract.js).
2. **Generates personalized plate recommendations** using a multi-phase nutrition engine.
3. **Estimates actual food mass** from a plate photo using computer vision (SAM + MiDaS depth).

---

## System Architecture

```
portion-vision/
├── backend/          Node.js + Express API (port 5000) - Handles OCR
├── frontend/         React 19 + Vite 7 PWA (port 5173)
├── cv_service/       Python FastAPI CV microservice (port 8000) - Analysis only
└── technical.md      ← You are here
```

### Frontend (React + Vite)

- **Core**: React 19, Vite 7, React Router v7.
- **Styling**: Tailwind CSS v3 (Emerald/Slate theme).
- **Security & Stability**: 
  - Overrides in `package.json` fix vulnerabilities in `serialize-javascript` and `@rollup/plugin-terser`.
  - `vite-plugin-pwa` pinned for compatibility with Vite 7.
- **State**: `AppContext` (Context API).
  - `userProfile` — persisted in **localStorage** (client-only, no server sync).
  - `todaysMenu` — synced from server on load, cached in localStorage.
- **PWA**: `vite-plugin-pwa` for offline capability and mobile install.
- **Proxy**: Dev server proxies `/api` and `/ocr` → backend port 5000.

### Backend (Node.js + Express)

- **API**: Express.js REST endpoints.
- **OCR Engine**: Native **Tesseract.js** integration.
  - Uses local `eng.traineddata` for offline/deterministic performance.
  - No longer proxies OCR requests to Python.
- **Storage**: JSON flat-files in `backend/data/`.
  - `menu.json` — current active menu (`{ date, items }` — single `items` array).
  - `foodDatabase.json` — knowledge base of food items with nutrition data.
- **Image Processing**: `multer` (uploads).
- **Recommendation**: `portion_recommender.js` — calorie-aware plate builder.
- **CV Proxy**: `/api/analyze-plate` (60s timeout) proxies images to the Python CV service via `FormData`.

### CV Service (Python + FastAPI)

- **Framework**: FastAPI + Uvicorn.
- **Segmentation**: MobileSAM (Segment Anything).
- **Depth**: MiDaS v2.1 Small (monocular depth estimation via torch.hub).
- **Detection**: OpenCV contour analysis for plate/compartment detection.
- **Volume**: Per-pixel integration (area × height).
- **Weight Management**: Weights are cached locally in `cv_service/weights/` and `~/.cache/torch/hub/`.

---

## Core Logic & Algorithms

### 1. Menu OCR Pipeline (`POST /ocr`)

1. **Input**: Image (camera or gallery) uploaded to Node.js backend.
2. **OCR Engine**: Tesseract.js (Node.js `backend/server.js`).
3. **Execution**:
   - Tesseract processes the image using `eng.traineddata`.
   - Raw text is passed to `parseMenuText`.
4. **Parsing** (`parseMenuText`):
   - Normalize: lowercase, remove non-alpha characters (except `,/&-`).
   - Split by `,`, `/`, `&`, `|`, `+`.
   - Filter noise using `OCR_BLACKLIST` (e.g., "breakfast", "mess", "timing").
   - Filter short tokens (< 3 chars).
   - Deduplicate and sort alphabetically.
5. **Storage**: Backend saves parsed items to `menu.json`.
6. **Database Enrichment**: New items not in `foodDatabase.json` are auto-added with fallback nutrition estimates from `getFallbackDetails()`.

### 2. Recommendation Engine (`portion_recommender.js`)

Generates specific quantity recommendations to build a balanced plate from available menu items.

#### A. Calorie & Macro Estimation

| Step | Method | Details |
|------|--------|---------|
| **BMR** | Mifflin-St Jeor | `10×weight + 6.25×height - 5×age ± offset` (male +5, female -161) |
| **TDEE** | Activity multiplier | Sedentary 1.2 → Very Active 1.725 |
| **Goal adjustment** | Deficit/surplus | Lose: -400 kcal · Gain: +300 kcal |
| **Meal fraction** | Split by meal | Breakfast 25% · Lunch 35% · Dinner 30% · Snack 10% |
| **Protein target** | Per-kg factor | Maintain: 1.0 g/kg · Lose: 1.6 g/kg · Gain: 2.0 g/kg |

#### B. Food Lookup & Classification

- **Primary**: O(1) normalized index lookup on `foodDatabase.json`.
- **Fuzzy fallback**: Levenshtein distance ≤ 2 against the full database.
- **Ultimate fallback**: Keyword-based `getFallbackDetails()` covering 30+ food patterns (biryani, rice, dal, chicken, etc.) with estimated macros.

Categories: `carb_base`, `protein_main`, `side`, `condiment`, `dessert`, `beverage`.
Meal roles: `mixed` (complete one-pot meal) or `single` (individual component).

#### C. Diet Filtering

Supports 6 diet preferences with tag-based filtering:

| Diet | Excludes |
|------|----------|
| **Non-veg** | Nothing |
| **Vegetarian** | Meat |
| **Lacto-veg** | Meat, eggs |
| **Ovo-veg** | Meat, dairy |
| **Vegan** | All animal products |
| **Jain** | Meat, eggs, root vegetables (potato, onion, garlic, carrot, etc.) |

Plus custom `avoidTags` from user profile (allergies, etc.).

#### D. Plate Building Algorithm (Multi-Phase)

The engine uses meal-type-specific fast paths and a phased approach:

**Snack fast-path** (mealType = `snack`):
- Pick 1-2 items within budget, prioritize protein. Add salad if available.

**Mixed-meal fast-path** (mealType = `lunch`/`dinner`, biryani/khichdi on menu):
- Use the highest-protein mixed item as the plate. Optionally add a side.

**Breakfast fast-path** (mealType = `breakfast`):
- Prefer breakfast-specific carbs (poha, upma, idli, oats).
- Add protein if budget allows. Include beverages.

**Standard plate build** (lunch/dinner, no mixed meal):

| Phase | Action | Budget Allocation |
|-------|--------|-------------------|
| **Phase 1** | Reserve calories for a vegetable side (highest fiber) | Up to 150 kcal reserved |
| **Phase 2** | Select protein(s) — sorted by protein/calorie efficiency | ~40% of remaining budget |
| **Phase 3** | Select carbs — roti+rice split if budget > 300 kcal | Remaining budget |
| **Phase 4** | Place reserved vegetable side on plate | Reserved kcal |
| **Trim** | If > 12% over target → reduce carb by 1 unit | — |
| **Fill** | If < 80% of target → add second side or bump carb | — |

Salads are always added (low calorie, always beneficial).
Condiments, beverages, and desserts go to `optionalItems`.

#### E. Serving Calculation (`calcServings`)

- Discrete items (roti, paratha): integer quantities, capped at 3-4.
- Bowl-based items (rice, dal, sabzi): 0.5 increments, capped at 1.5-2.
- Constrained by both calorie budget AND per-item fat limit.

#### F. Output Shape

```json
{
  "mealType": "lunch",
  "dietPreference": "non-veg",
  "recommendedPlate": [
    {
      "item": "chicken curry",
      "dish_type": "curry",
      "role": "protein",
      "recommendedQuantity": 1,
      "unit": "bowl",
      "serving_size": 150,
      "totalGrams": 150,
      "estimatedCalories": 280,
      "protein": 25,
      "carbs": 5,
      "fat": 14,
      "fiber": 1,
      "reason": "Muscle repair & satiety",
      "icon": "💪"
    }
  ],
  "optionalItems": [
    { "item": "papad", "calories": 40, "note": "Condiment — small amount", "limit": "~10g" }
  ],
  "summary": {
    "dailyCalories": 2200,
    "targetMealCalories": 770,
    "totalPlateCalories": 745,
    "totalPlateProtein": 42,
    "totalPlateCarbs": 85,
    "totalPlateFat": 22,
    "targetProtein": 38,
    "plateLogic": "Balanced 770 kcal lunch targeting 38g protein.",
    "dietNote": "",
    "notes": "Portions are estimates based on standard serving sizes."
  }
}
```

---

### 3. Computer Vision — Food Mass Estimation (`cv_service/`)

Estimates food mass from a single image of a non-circular, sectioned mess plate.

#### Architecture

```
cv_service/
├── main.py                          # FastAPI entry point (port 8000)
├── api/routes.py                    # POST /estimate-portion
├── config/
│   ├── plate_config.py              # Known plate dimensions (cm)
│   └── density_map.py               # Food density table (g/ml)
├── image_processing/
│   ├── preprocess.py                # Resize + perspective warp
│   └── detection.py                 # Compartment detection + scale calibration
├── segmentation/
│   └── sam_segmenter.py             # MobileSAM food segmentation
├── depth/
│   └── depth_estimator.py           # MiDaS monocular depth estimation
├── volume/
│   └── volume_calculator.py         # Per-pixel volume integration
├── estimation/
│   └── mass_estimator.py            # End-to-end orchestrator
└── weights/                         # Locally cached model weights
```

#### Pipeline Steps

| Step | Module | What it does |
|------|--------|-------------|
| 1. Preprocess | `preprocess.py` | Resize (longest edge → 1024px) + detect plate boundary + perspective warp to top-down view |
| 2. Detect compartments | `detection.py` | Combined adaptive-threshold + Canny edge detection → contour filtering (2-90% of plate area). Outputs bounding boxes sorted top-left → bottom-right |
| 3. Scale calibration | `detection.py` | Matches largest detected compartment to known real-world dimensions from `plate_config.py` → computes `cm_per_pixel` scale factor |
| 4. Depth estimation | `depth_estimator.py` | MiDaS Small (via `torch.hub`) generates relative depth map. Plate surface = baseline (median depth). Height = depth – baseline, clamped ≥ 0. Relative heights scaled to assumed max food height (default 3 cm) |
| 5. Segmentation | `sam_segmenter.py` | MobileSAM with grid-point prompts segments food within each compartment. Masks filtered by area (1-95% of compartment) and overlap (< 50%). Falls back to HSV color thresholding if SAM unavailable |
| 6. Volume integration | `volume_calculator.py` | For each food mask: `volume = Σ (pixel_area_cm² × height_cm)` over all mask pixels. Capped at compartment's physical max volume |
| 7. Mass estimation | `mass_estimator.py` | `mass_g = volume_ml × density` using density lookup from `density_map.py` (80+ Indian foods, substring-match fallback, default 1.0 g/ml) |

#### Plate Configuration

Known plate profiles defined in `plate_config.py`:

- **`standard_mess_thali`**: 37×27 cm, 5 compartments (3 small wells + 2 large sections).
- **`4_compartment_plate`**: 33×25 cm, 4 equal sections.

Each compartment has known `width_cm`, `height_cm`, `depth_cm`, and `max_volume_ml`.

Compartment matching uses aspect-ratio comparison (greedy, largest-first).

#### Food Density Table

`density_map.py` contains densities (g/ml) for 80+ foods:

| Category | Example | Density (g/ml) |
|----------|---------|----------------|
| Rice (cooked) | steam rice | 1.08 |
| Flatbread | chapati, roti | 0.85 |
| Dal / lentils | dal, sambar | 1.02–1.05 |
| Curries | chicken curry | 1.05 |
| Sabzi (veg) | mixed veg | 0.90 |
| Condiments | pickle | 1.10 |
| Sweets | gulab jamun | 1.15 |

Lookup: exact match → substring match → default (1.0).

#### API: `POST /estimate-portion`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | File | Yes | JPEG/PNG plate image |
| `expected_items` | string | No | Comma-separated food names for labeling |
| `plate_profile` | string | No | Plate type (default: `standard_mess_thali`) |

**Response:**
```json
{
  "food_items": [
    { "name": "dal", "volume_ml": 120.5, "mass_g": 126.5 },
    { "name": "rice", "volume_ml": 210.0, "mass_g": 231.0 }
  ],
  "confidence": 0.82
}
```

#### Model Loading

- MobileSAM and MiDaS weights are **lazy-loaded** on first request.
- Subsequent calls reuse loaded models in memory.
- GPU (CUDA) used if available, otherwise CPU.

---

## API Reference

| Method | Endpoint | Service | Description |
|--------|----------|---------|-------------|
| `GET` | `/health` | Backend | Health check |
| `GET` | `/api/menu` | Backend | Get current digitized menu |
| `POST` | `/ocr` | Backend | Upload image for menu OCR (Native Tesseract.js) |
| `POST` | `/api/recommend` | Backend | Get plate recommendations. Body: `{ userProfile, mealType, menuItems }` |
| `GET` | `/api/foods` | Backend | Get all foods in the database |
| `GET` | `/api/foods/search?q=` | Backend | Search foods by name (substring + fuzzy) |
| `POST` | `/api/analyze-plate` | Backend → CV | Upload plate photo for mass estimation (proxied to CV service) |
| `POST` | `/estimate-portion` | CV Service | Direct CV endpoint (internal, port 8000) |
| `GET` | `/health` | CV Service | CV service health check |

---

## Setup

### 1. Backend (Node.js)
```bash
cd backend
npm install
npm run dev
```
Runs on `http://localhost:5000`. Requires `eng.traineddata` in root for OCR.

### 2. Frontend (React)
```bash
cd frontend
npm install
npm run dev
```
Runs on `http://localhost:5173`. Access via network IP for mobile testing.

### 3. CV Service (Python)
```bash
cd cv_service
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
Runs on `http://localhost:8000`. Weights download automatically on first request.

---

## Folder Structure

```
portion-vision/
├── backend/
│   ├── data/                       # JSON database (menu.json, foodDatabase.json)
│   ├── utils/                      # Shared utilities (normalize.js, fuzzyMatch.js)
│   ├── uploads/                    # Temp image storage (auto-cleaned)
│   ├── eng.traineddata             # Tesseract OCR language data
│   ├── server.js                   # Express API + Tesseract OCR + CV proxy
│   └── portion_recommender.js      # Recommendation engine
├── frontend/
│   ├── src/
│   │   ├── components/             # RecommendationCard, Button, ErrorMessage
│   │   ├── contexts/               # AppContext (global state)
│   │   ├── hooks/                  # useApp, useErrorHandler
│   │   ├── pages/                  # Home, MenuUpload, Preferences, Analysis
│   │   ├── services/               # api.js (centralized HTTP client)
│   │   └── utils/                  # validation.js
│   ├── package.json                # PWA + Dependency overrides
│   ├── vite.config.js              # PWA + proxy config
│   └── tailwind.config.js          # Theme config
├── cv_service/
│   ├── config/                     # plate_config.py, density_map.py
│   ├── image_processing/           # preprocess.py, detection.py
│   ├── segmentation/               # sam_segmenter.py (MobileSAM)
│   ├── depth/                      # depth_estimator.py (MiDaS)
│   ├── volume/                     # volume_calculator.py
│   ├── estimation/                 # mass_estimator.py (pipeline orchestrator)
│   ├── api/                        # routes.py (FastAPI endpoint)
│   ├── weights/                    # Locally cached model weights (mobile_sam.pt)
│   └── main.py                     # FastAPI entry point
└── technical.md                    # Documentation
```
