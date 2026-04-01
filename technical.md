# PortionVision - Full Technical Documentation (System Encyclopedia)

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
    *   `Home.jsx`: Main dashboard with biometric summaries, automatic meal inference, and manual meal selector.
    *   `MenuUpload.jsx`: Interface for capturing and uploading mess menus (Streamlined).
    *   `PlateCapture.jsx`: Camera interface with pulsing top-down alignment guide for accurate CV analysis.
    *   `Analysis.jsx`: Results page with "Done" navigation and passed-meal-type persistence.
    *   `Preferences.jsx`: Profile settings with 100% Macro Split validation and automatic biometric recommendations.
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
    4.  Items are checked against `foodDatabase.json`. New items are added using the standardized flat schema.

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
3.  **Dynamic Meal Targets**: Automatically infers current meal based on system clock (Breakfast 6am, Lunch 11am, Snack 4pm, Dinner 7pm).
4.  **Percentage-Based Macros**: Calculates targets based on user-defined (or auto-recommended) splits (Protein/Carb/Fat % totaling 100%).
5.  **Biometric Failsafe**: Protein target is back-calculated from calories if manual % is not set, using athletic multipliers (1.0g - 2.0g per kg).
4.  **Macro-Aware Fallbacks**: Fallback items (for unknown OCR results) are generated through a logic-heavy wrapper that calculates `protein_level` (High/Medium/Low) based on actual macros, ensuring they behave identical to database entries in the selection logic.
5.  **Plate Building Phases**:
    *   **Phase 1**: Reserve exact calories for a high-fiber "veg side".
    *   **Phase 2**: Select a "protein_main". If multiple, pick the most protein-efficient (Protein/Calorie ratio).
    *   **Phase 3**: Allocate remaining calories (Carb Target) to "carb_base". Logic intelligently splits between Roti and Rice if calorie needs are high (>300 excess).
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

### A. Flat Food Database Schema (`foodDatabase.json`)
The database uses a flattened schema to eliminate runtime transformation overhead and ensure strict logic consistency.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (e.g., `dal_makhani`) |
| `name` | string | Display name |
| `veg` | boolean | `true` if vegetarian, `false` otherwise |
| `category` | string | `protein_main`, `carb_base`, `side`, `dessert`, `beverage` |
| `dish_type` | string | `dal`, `curry`, `sabji`, `rice`, `roti`, `salad`, etc. |
| `unit_type` | string | `bowl`, `piece`, `glass`, `tsp` (Controls portion snapping) |
| `serving_size` | number | Weight in `serving_unit` (usually 150g for bowls, 40g for roti) |
| `calories` | number | Energy content per serving |
| `protein` | number | Protein (g) per serving |
| `carbs` | number | Carbohydrates (g) per serving |
| `fat` | number | Fat (g) per serving |
| `protein_level`| string | `high` (≥15g), `medium` (8-14g), `low` (<8g) |

### B. Dietary Preference Logic
The recommendation engine strictly filters using `MEAT_TAGS`, `isEgg()`, and `isDairy()` logic:

| Diet | Exclusions |
|------|------------|
| **Jain** | `MEAT_TAGS` + `Egg` + `Root_Veg` (potato, onion, garlic, carrot, etc.) |
| **Vegan** | `MEAT_TAGS` + `Egg` + `Dairy` (milk, ghee, butter, paneer) |
| **Lacto-Veg** | `MEAT_TAGS` + `Egg` |
| **Ovo-Veg** | `MEAT_TAGS` + `Dairy` |
| **Vegetarian** | `MEAT_TAGS` |

### C. Standardized Unit Snapping
*   **Piece**: Snaps to integer values (1, 2, 3). Used for Bread, Roti, Eggs, Fruit.
*   **Bowl/Glass**: Snaps to 0.5 increments. Used for Dal, Rice, Beverages.
*   **Tsp/Tbsp**: Fine increments for condiments.

---

## 🛠️ 6. Developer & Calibration Guide

*   **Depth Calibration**:
    *   **Z-Scale**: `1.2` multiplier in `depth_estimator.py` acts as a "distance correction factor."
    *   **Baseline**: Automatically derived from the median depth of pixels tagged as "plate divider."
*   **AI Vision Params**:
    *   **SAM Grid**: Uses a **15x15 (225 points)** prompt grid.
    *   **Foodness Saturation**: Threshold set to `12` (HSV gamut).
    *   **Foodness Texture**: Laplacian variance threshold set to `25`.
*   **OCR Fallback Intelligence**:
    *   When OCR finds a food not in `foodDatabase.json`, it uses a fuzzy keyword matcher to assign a "Category Fallback" (e.g., "Veg Curry" for any unknown vegetable dish).
    *   This prevents analysis failure and provides a safe nutritional estimate during live demos.
*   **Service Monitoring**:
    *   Backend: Port 5000 (`/health`).
    *   AI Service: Port 8000 (`/health`).
