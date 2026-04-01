# PortionVision — Full Technical Documentation (System Encyclopedia)

## 🌐 1. System Overview & Architecture

PortionVision is an end-to-end nutritional assistant designed for college/office mess environments. It solves the "hidden nutrition" problem by digitizing mess menus and estimating actual plate portions using 3D spatial analysis.

### The Three-Tier Stack:
| Tier | Technology | Responsibility |
|------|------------|----------------|
| **Frontend** | React 19 + Vite 7 + Tailwind | UX, PWA, Camera Capture, Results Visualization |
| **Backend** | Node.js + Express + Tesseract.js | Logic, OCR, Recommendations, JSON database |
| **CV Service** | Python + FastAPI + MobileSAM + MiDaS | 3D Reconstruction, Segmentation, Mass Estimation |

---

## 📱 2. Frontend: Mobile-First PWA

The frontend is a Progressive Web App optimized for low-latency interactions on mobile devices.

### Directory Structure & Responsibilities:
*   `src/pages/`:
    *   `Home.jsx`: Entry point with user summary and quick actions.
    *   `MenuUpload.jsx`: Interface for capturing and uploading mess menus.
    *   `PlateCapture.jsx`: Camera interface with guide overlays for thali alignment.
    *   `Analysis.jsx`: Complex results page with macro breakdown of detected portions.
    *   `Preferences.jsx`: LocalStorage-persisted user profile settings.
*   `src/components/`:
    *   `RecommendationCard.jsx`: Displays a balanced plate with progress bars for Calories, Protein, Carbs, and Fat.
    *   `MacroBar.jsx`: Reusable sub-component for nutritional progress visualization.
    *   `ErrorMessage.jsx`: standardized error reporting.
*   `src/contexts/AppContext.jsx`: Central state managing `userProfile`, `todayMenu`, and `imagePreview`.

### PWA Configuration:
*   Uses `vite-plugin-pwa` for service worker generation.
*   `registerType: 'autoUpdate'` ensures users always have the latest food density maps.
*   Offline capability allows users to view their recommendation even with poor mess-hall reception.

---

## ⚙️ 3. Backend: Logic, OCR & Recommendations

The backend serves as the "Knowledge Hub" and "Nutritionist" of the system.

### A. The OCR Pipeline (`server.js`)
*   **Engine**: Tesseract.js running native in Node.js.
*   **Data**: Uses local `eng.traineddata`.
*   **Logic**:
    1.  Image upload via `multer`.
    2.  `Tesseract.recognize` extracts raw text.
    3.  `parseMenuText` normalization:
        *   Regex `/[^a-z\s/,&\-]/g` strips punctuation.
        *   `OCR_BLACKLIST` removes non-food noise (Breakfast, Lunch, Dinner, Monday, Mess, Price, rs, etc.).
    4.  Items are checked against `foodDatabase.json`. New items are added with `_enrichedByFallback: true`.

### B. Dietary Preference Logic
The recommendation engine strictly filters menu items based on these tags:

| Diet | Excludes Items with Tags |
|------|-------------------------|
| **Non-veg** | (No exclusions) |
| **Vegetarian** | "meat" |
| **Lacto-veg** | "meat", "eggs" |
| **Ovo-veg** | "meat", "dairy" |
| **Vegan** | "meat", "eggs", "dairy", "honey" |
| **Jain** | "meat", "eggs", "root_veg" (potato, onion, garlic) |

### C. Recommendation Algorithm (`portion_recommender.js`)
1.  **BMR (Mifflin-St Jeor)**: `(10 * wt) + (6.25 * ht) - (5 * age) + s` (Male: +5, Female: -161).
2.  **Activity Adjustment**: Sedentary (1.2), Moderate (1.55), Very Active (1.725).
3.  **Meal Calorie Targets**:
    *   **Breakfast**: 25% of daily budget.
    *   **Lunch**: 35% of daily budget.
    *   **Dinner**: 30% of daily budget.
    *   **Snacks**: 10% of daily budget.
4.  **Plate Building Phases**:
    *   **Phase 1**: Reserve 150 kcal for a "veg side" (fiber/vitamins).
    *   **Phase 2**: Select a "protein_main". If multiple, pick the one with highest protein-to-calorie density.
    *   **Phase 3**: Allocate remaining calories to "carb_base".
    *   **Failsafe**: If diet excludes all items, a "No compatible items" warning is returned.

---

## 🤖 4. CV Service: Computer Vision & 3D Estimation

The Python service performs the "heavy lifting" of spatial estimation.

### A. The Image Pipeline
1.  **`preprocess.py`**:
    *   Resizes image to 1024px.
    *   Applies a Bilateral Filter to preserve edges while reducing sensor noise.
    *   warps perspective to a 1024x1024 square representation of the plate.
2.  **`detection.py` (Autonomous Calibration)**:
    *   Detects internal compartment contours.
    *   Calculates a "Geometric Fingerprint" for the plate.
    *   **Auto-detects Profile**: Compares the fingerprint to known profiles.
3.  **`depth_estimator.py` (MiDaS v2.1 Small)**:
    *   Generates a relative depth map.
    *   **Physics Check**: Calculates metric height $H = \frac{(Depth_{base} - Depth_{pixel}) \times Z_{dist}}{Focal_{len}}$.
    *   Baseline is established using the detected rim of the plate.
4.  **`sam_segmenter.py` (MobileSAM)**:
    *   Performs a global scan with a 225-point grid.
    *   **Heuristic Foodness Check**:
        *   **Texture**: Laplacian variance must be $> 25$ (Smooth steel has low variance).
        *   **Color**: HSV Saturation must be $> 12$ (Metallic surfaces have low saturation).
5.  **`volume_calculator.py`**:
    *   Total height $H_{total} = H_{relative\_to\_rim} + Depth_{physical\_well}$.
    *   $Volume = \sum (H_{total} \times PixelArea_{cm^2})$.

---

## 📊 5. Data Constants & Schemas (Dead-Accurate)

### A. Known Plate Profiles (`plate_config.py`)
| Profile Name | Outer Dim (cm) | Context |
|--------------|----------------|---------|
| **standard_mess_thali** | 37.0 x 27.0 | Standard 6-compartment tray. Wells = 2.5cm deep. |
| **4_compartment_plate** | 33.0 x 25.0 | 4-section square tray. Wells = 2.5cm deep. |

### B. Core Density Library (`density_map.py`)
*Used for: Mass (g) = Volume (ml) × Density*
| Food Item | Density (g/ml) |
|-----------|----------------|
| **Steam Rice** | 1.08 |
| **Dal Fry** | 1.05 |
| **Mixed Veg** | 0.90 |
| **Chapati/Roti** | 0.85 |
| **Paneer** | 1.03 |
| **Salad** | 0.60 |

### C. Nutritional Macro Map (`macro_map.py`)
*Units are per **1.0 gram** of food.*
| Category | Cal/g | Prot/g | Carb/g | Fat/g |
|----------|-------|--------|--------|-------|
| **Rice (Steam)** | 1.30 | 0.027 | 0.280 | 0.003 |
| **Roti (Chapati)** | 2.60 | 0.080 | 0.500 | 0.030 |
| **Dal (Yellow)** | 0.85 | 0.055 | 0.120 | 0.020 |
| **Aloo Gobi** | 0.95 | 0.030 | 0.120 | 0.050 |
| **Chicken Curry** | 1.40 | 0.150 | 0.040 | 0.080 |

### D. Dietary Preference Logic
The recommendation engine strictly filters using `MEAT_TAGS`, `isEgg()`, and `isDairy()` logic:

| Diet | Exclusions |
|------|------------|
| **Jain** | `MEAT_TAGS` + `Egg` + `Root_Veg` (potato, onion, garlic, carrot, etc.) |
| **Vegan** | `MEAT_TAGS` + `Egg` + `Dairy` (milk, ghee, butter, paneer) |
| **Lacto-Veg** | `MEAT_TAGS` + `Egg` |
| **Ovo-Veg** | `MEAT_TAGS` + `Dairy` |

---

## 🛠️ 6. Developer & Calibration Guide

*   **Depth Calibration**:
    *   **Z-Scale**: `1.2` multiplier in `depth_estimator.py` acts as a "distance correction factor."
    *   **Baseline**: Automatically derived from the median depth of pixels tagged as "plate divider."
*   **AI Vision Params**:
    *   **SAM Grid**: Uses a **15x15 (225 points)** prompt grid.
    *   **Foodness Saturation**: Threshold set to `12` (HSV gamut).
    *   **Foodness Texture**: Laplacian variance threshold set to `25`.
*   **Database Synchronization**:
    *   When OCR runs, items with `_enrichedByFallback: true` are added.
    *   Manually review `backend/data/foodDatabase.json` to move fallback estimates to "verified" status.
*   **Service Monitoring**:
    *   Backend: Port 5000 (`/health`).
    *   AI Service: Port 8000 (`/health`).
