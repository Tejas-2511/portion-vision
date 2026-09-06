# PortionVision: The Complete Technical Deconstruction

This document is a principal-level, exhaustive manual for the PortionVision codebase. It provides a file-by-file, function-by-function deconstruction of the entire system, detailing runtime behavior, memory management, and data transformations.

---

## 📑 Table of Contents
- [1. System Architecture & Lifecycle](#-1-system-architecture--lifecycle)
- [2. Backend Deconstruction (`backend/`)](#️-2-backend-deconstruction-backend)
- [3. CV Service Deconstruction (`cv_service/`) — v3.0 Enhanced](#-3-cv-service-deconstruction-cv_service--v30-enhanced)
  - [3.1. CV Deep Dive: The "0 to 100" Journey (v3)](#-31-cv-deep-dive-the-0-to-100-journey-v3)
- [4. Frontend Deconstruction (`frontend/`)](#-4-frontend-deconstruction-frontend)
- [5. Data Schema & Models](#-5-data-schema--models)
- [6. Internal Object Evolution (The "Dal" Life-Cycle)](#-6-internal-object-evolution-the-dal-life-cycle)
- [7. Global Runtime Mechanics & Resilience](#-7-global-runtime-mechanics--resilience)
- [8. Pipeline Diagnostics & Logging System](#-8-pipeline-diagnostics--logging-system)
- [9. Developer Setup & Fast-Start](#-9-developer-setup--fast-start)

---

## 🏗️ 1. System Architecture & Lifecycle

PortionVision is an end-to-end health-tech solution that converts visual food data into nutritional insights. It operates across three specialized services:

1.  **Frontend (React/Vite)**: Orchestrates the User Journey.
2.  **Backend (Node.js/Express)**: The "Orchestrator" handling OCR, logical food matching, and the Recommendation Engine.
3.  **CV Service (Python/FastAPI)**: The "Analyzer" performing deep-learning-based volumetric mass estimation.

### **Data Evolution Life-Cycle**
1.  **Ingestion**: Captured `File` (Binary) $\rightarrow$ `FormData` (Stream).
2.  **OCR Processing**: Image $\rightarrow$ Tesseract (WASM Worker) $\rightarrow$ Sanitized String $\rightarrow$ Parsed Array.
3.  **Portion Logic**: User Context $\rightarrow$ TDEE Matrix $\rightarrow$ Macro Partitioning $\rightarrow$ Scaled Recommendations.
4.  **CV Estimation**: Rectified Top-Down Matrix $\rightarrow$ Quality Gate (blur/tilt) $\rightarrow$ Scale Factor (ellipse-first) $\rightarrow$ Height Map (Depth Anything + food priors) $\rightarrow$ Per-Compartment Binary Masks (Full SAM) $\rightarrow$ Food Classification (MobileNetV3 + OCR fusion) $\rightarrow$ Hungarian Optimal Assignment $\rightarrow$ Dynamic Density $\rightarrow$ Volumetric Integration ($cm^3$) $\rightarrow$ Mass ($g$) $\rightarrow$ Nutrients $\rightarrow$ Composite Confidence.

---

## 🛠️ 2. Backend Deconstruction (`backend/`)

### `server.js` — Core Logic & Routing
*   **Imports (Lines 1-13)**: 
    *   `axios`: Used for proxying image data to the Python service.
    *   `Tesseract.js`: Native WASM engine for local OCR.
    *   `multer`: Middleware for `multipart/form-data`.
*   **Multer Memory Management (Lines 30-52)**:
    *   Uses `multer.diskStorage` to write uploads directly to `backend/uploads/`.
    *   This pattern uses a **Node.js WriteStream**, which prevents large images from being loaded entirely into the Node.js V8 heap, avoiding `OutOfMemory` errors during high-concurrency windows.
*   **OCR Parsing Logic `parseMenuText` (Lines 191-221)**:
    *   `split(/[\n\t]/)`: Sanitizes by breaking on common OCR noise formats.
    *   `OCR_BLACKLIST`: A `Set` (O(1) lookup) containing non-food keywords (Days, Times, "Price").
    *   `norm.split(/[,/&|+]/)`: Sub-parses lines that contain multiple items (e.g., "Rice/Dal").
    *   **Granular Steps**:
        1.  **Splitting**: `rawText.split(/[\n\t]/)` converts the string into an array of lines.
        2.  **Filtering**: `.filter(Boolean)` removes empty elements or pure whitespace lines.
        3.  **Normalization**: `norm` uses regex `/[^a-z\s/,&\-]/g` to strip prices ($Rs$), dates ($2024$), and symbols ($*$), leaving only biological food characters.
        4.  **Compound Splitting**: `part.split(/[,/&|+]/)` breaks lines like "Rice / Dal" into discrete array elements.
        5.  **Deduplication**: Uses a `Set` to ensure "Rice" isn't returned twice from a menu.
*   **OCR Endpoint `POST /ocr` (Lines 223-310)**:
    *   **Workflow**: Save File $\rightarrow$ `Tesseract.recognize` $\rightarrow$ Parse Text $\rightarrow$ DB Sync $\rightarrow$ Cleanup.
    *   **DB Sync Loop**: For each item, it checks `foodDatabase.json`. If missing, `getFallbackDetails` generates a nutritional stub.
    *   **Memory Efficiency**: `fs.unlinkSync` clears the disk immediately after processing.
*   **CV Proxy `POST /api/analyze-plate` (Lines 316-350)**:
    *   **Streaming Strategy**: Uses `fs.createReadStream(originalPath)` to pipe the disk file directly into the `axios` POST request. This is the gold standard for Node.js proxying as it minimizes intermediate memory allocation.

### `portion_recommender.js` — The Intelligence Engine
*   **Reasoning Engine**: Maintains an internal `logicLogs` array to trace decision-making (filter logic, macro splits, calorie gap handling). These logs are exposed via `summary.logicLogs` in the API response for complete transparency.
*   **Mifflin-St Jeor Engine `estimateDailyCalories` (Lines 204-233)**:
    *   **The Math**: $BMR = (10 \times weight) + (6.25 \times height) - (5 \times age) + s$.
    *   **The Logic**: Men ($s=5$), Women ($s=-161$). Result is then scaled by `activityMultipliers` (1.2 for sedentary to 1.725 for active).
*   **Macro Target Logic `computeMacroTargets` (Lines 235-259)**:
    *   Determines `mealFrac` (Breakfast 0.25, Lunch 0.35, Dinner 0.30, Snack 0.10).
    *   Converts calorie targets to grams: Protein (4 kcal/g), Carbs (4 kcal/g), Fat (9 kcal/g).
*   **Recommendation Loop `buildPlate` (Lines 292-384)**:
    1.  **Partitioner**: Groups food into `mixed`, `proteins`, `carbs`, `sides`, `salads`.
    2.  **Selection Logic**:
        *   Checks `mixed` flag first (e.g., Biryani).
        *   If not mixed, picks highest protein item $\rightarrow$ Fills carbs $\rightarrow$ Adds leafy salads.
    3.  **Unit Snapping (`calcServings`) — Granular Steps**:
        1.  **Base Calculation**: `raw = targetCalPerItem / food.calories`. This finds the raw float.
        2.  **The Fat Ceiling**: If `(raw * food.fat) > maxFatPerItem`, the serving is scaled down to fit the fat limit, even if it leaves calories on the table.
        3.  **Discrete Snapping**: If `unit_type` is `piece` (roti/paratha), it uses `Math.round(raw)`. This enforces whole-unit servings for solids.
        4.  **The 0.5 Snapping Trick**: For bowls/glasses, it uses `Math.round(raw * 2) / 2`.
            *   Example: $1.15 \rightarrow 2.3 \rightarrow 2.0 \rightarrow 1.0$ bowl.
            *   Example: $1.35 \rightarrow 2.7 \rightarrow 3.0 \rightarrow 1.5$ bowls.
*   **Diet Filtering `filterFoods` (Lines 154-198)**:
    *   Implements **Jain** and **Vegan** logic.
    *   Jain: Blocks items with `JAIN_AVOID_TAGS` (potatoes, onions, garlic).
    *   Vegan: Blocks `isMeat`, `isEgg`, and `isDairy` tags.

### `utils/db.js` — Internal Persistence
*   **Pattern**: Atomic read-write using `fs.promises`.
*   **Logic**: `ensureDataDir` ensures the `data/` directory exists. `getFoods` reads and parses JSON. `saveFoods` stringifies and overwrites.
*   **Atomicity Warning**: This is not a transactional database; it is a JSON-store. It works because the data set is small and writes are infrequent (only during menu capture).
*   **Corruption Recovery**: If `JSON.parse(data)` fails due to file corruption, the `catch` block (Lines 23-26) returns an empty array `[]` instead of throwing. This allows the system to self-heal and re-populate the database during the next menu scan.

### `utils/fuzzyMatch.js` — OCR Correction
*   **`levenshteinDistance`**: Computes the minimum number of single-character edits (insertions, deletions, substitutions) required to change one word into another.
*   **`fuzzyMatchFood`**: Iterates through the database. If Distance $\le 2$, it is considered a match. This handles OCR errors like "Dai" instead of "Dal".

---

## 🐍 3. CV Service Deconstruction (`cv_service/`) — v3.0 Enhanced

> **Version 3.0 introduces 10 targeted upgrades** organised across 8 files. All upgrades are backward-compatible (no API contract changes). Every new code path has a fallback.

### `main.py` & `api/routes.py`
*   **FastAPI Engine**: Uses `async def` and `UploadFile`.
*   **Binary Buffer Flow**: `image.read()` → `np.frombuffer` → `cv2.imdecode`. The image is now a BGR matrix in RAM.
*   **Quality Error Handling**: If the quality gate (#7) rejects an image, the API returns `HTTP 422` with a structured JSON body `{ "type": "image_quality", "message": "<user-facing string>" }` instead of a 500. The frontend can display this directly.
*   **Debug Parameter**: `/estimate-portion` accepts `debug: bool = Form(True)`. When enabled, the full diagnostic pipeline is activated and the response includes a `_debug` metadata block.

### `image_processing/preprocess.py` — Warp Engine + Quality Gate (#7)
*   **`validate_image_quality(image, blur_thresh=80, tilt_thresh=30)`** *(new)*:
    -   **Blur Detection**: Laplacian variance of the greyscale image. Values below 80 indicate motion blur or an out-of-focus lens.
    -   **Tilt Detection**: Applies `cv2.HoughLines`, extracts the dominant edge orientation, and computes deviation from the nearest cardinal axis (0°/90°). Deviations above 30° indicate the camera is angled.
    -   Returns `{ ok, blur_score, tilt_deg, reason }`. If `ok=False`, `process_image()` raises a `ValueError` with the user-facing `reason` string.
    -   Configurable via `blur_thresh` and `tilt_thresh` kwargs — no code changes needed to tune.
*   **`process_image(image, target_long_edge, ctx, skip_quality_check=False)`**:
    -   Step 0 (new): calls `validate_image_quality()` and aborts early if it fails.
    -   Steps 1-6 unchanged: Resize → Gaussian denoise → LAB normalisation → CLAHE → Canny edges → Perspective warp.
*   **Diagnostics**: When `ctx.debug=True`, saves `Quality Gate` log entry with blur and tilt scores.

### `image_processing/detection.py` — Well Calibration
*   **`find_compartments`**: Uses adaptive threshold + Canny to detect compartment dividers. Filters by 2%–90% of plate area. Unchanged.
*   **`compute_scale`**: Bbox-based pixel-to-cm calibration. Used as fallback when ellipse calibration (#4) fails.

### `depth/depth_estimator.py` — Monocular Vision v2 (#1 #4 #5)

**Enhancement #1 — Hybrid Depth with Food Geometric Priors**
*   **`FOOD_HEIGHT_PRIORS`** *(new)*: A module-level dictionary mapping 40+ canonical food names to `(min_cm, max_cm)` height ranges derived from real serving geometry.
    ```python
    FOOD_HEIGHT_PRIORS = {
        "rice":  (1.5, 4.5),
        "dal":   (1.5, 3.5),
        "roti":  (0.4, 1.5),
        ...
    }
    ```
*   **`apply_food_height_prior(height_map, food_label, alpha=0.70, beta=0.30)`** *(new)*:
    -   Lookup: exact match → substring match → no prior (return unchanged).
    -   Fusion: `fused = 0.70 × depth_anything_height + 0.30 × prior_midpoint`.
    -   Clamp: `np.clip(fused, min_h, max_h)`. Prevents neural depth noise producing impossible 8cm roti or 0.2cm dal.
    -   Called per-mask in `mass_estimator.py` *after* classification assigns a label.

**Enhancement #4 — Ellipse-Based Scale Calibration**
*   **`calibrate_scale_from_ellipse(image_bgr, known_diameter_cm=26.0)`** *(new)*:
    -   Detects the plate rim contour via Canny + `cv2.fitEllipse`.
    -   Sanity checks: ellipse major/minor axis ratio < 2.0 (not elongated), area 10%–95% of frame.
    -   Returns `cm_per_pixel = known_diameter_cm / avg_axis_px` or `None` on failure.
    -   In `mass_estimator.py`, if this returns a value it overrides the bbox-based scale and boosts `scale_confidence` from 0.7 → 1.0.

**Enhancement #5 — Gaussian Smoothing**
*   Inside `estimate_depth()`, `cv2.GaussianBlur(depth, (5,5), 0)` is applied immediately after the Depth Anything `resize`. This suppresses per-pixel shot noise before normalization and volume integration.

*   **`normalize_depth_to_plate`** and **`depth_to_cm`**: Unchanged from baseline.

### `segmentation/sam_segmenter.py` — Deep Segmentation v2 (#8)

**Enhancement #8 — Per-Compartment SAM**
*   **`segment_per_compartment_sam(image_bgr, compartments, ctx=None)`** *(new)*:
    -   Loads `SamPredictor` (prompt-based SAM, same weights as `SamAutomaticMaskGenerator`).
    -   For each compartment bbox, crops the region and sets it as the predictor's image.
    -   Sends a 3×3 grid of foreground point prompts inside the compartment, uses `multimask_output=True`, picks the highest-scoring mask.
    -   Re-maps cropped mask coordinates back to full-image space.
    -   Deduplicates by requiring 25% new area (same heuristic as full-image mode).
    -   **Fallback chain**: if `SamPredictor` is unavailable → `segment_full_image_sam(); if per-compartment returns no masks → `segment_full_image_sam()`.
*   **`segment_full_image_sam`**: Original method, kept intact as fallback.
*   **`_save_segmentation_debug`**: Now includes the classifier label (if available) in the overlay annotation text.

### `classification/classifier.py` — New Module (#2 #3)

**Enhancement #2 — Vision-Based Food Classification**
*   **Model**: `torchvision.models.mobilenet_v3_small` with `IMAGENET1K_V1` weights. Lazy-loaded as a global singleton.
*   **Custom weight hook**: If `cv_service/weights/food_classifier.pth` exists, it is loaded instead of ImageNet weights, enabling production fine-tuning.
*   **`_IMAGENET_TO_FOOD`** dict: 60+ ImageNet class names mapped to canonical Indian food labels (e.g., `"soup" → "dal"`, `"bread" → "roti"`).
*   **`classify_mask_region(image_bgr, mask, allowed_labels=None, top_k=3)`**:
    1.  Crops the mask bounding box; blanks non-mask pixels to neutral grey so the model sees only the food.
    2.  Resizes to 224×224, applies standard ImageNet normalisation.
    3.  Runs `torch.no_grad()` forward pass → 1000-class softmax.
    4.  Maps ImageNet probs → food label probabilities by summing over bridged classes.
    5.  Normalises food-label scores to sum to 1.
    6.  Returns `{ label, confidence, top_k }`.

**Enhancement #3 — OCR + CV Fusion**
*   `classify_mask_region()` accepts `allowed_labels` (list of OCR-extracted food names).
*   If provided, each label in `allowed_labels` gets its probability multiplied by `OCR_BOOST = 2.5`, then all scores are re-normalised. This makes the classifier strongly prefer OCR-confirmed items without making it a hard constraint.
*   No API changes required — `expected_items` (already passed from OCR via Node.js) flows directly into the CV pipeline as `allowed_labels`.

### `config/density_map.py` — Dynamic Density (#6)
*   **`get_density(food_name)`**: Original static lookup — unchanged.
*   **`get_dynamic_density(food_name, mask_region_bgr=None)`** *(new)*:
    -   Extracts three visual features from the food's pixel region:
        -   `mean_brightness` — HSV V-channel mean (0–255)
        -   `mean_saturation` — HSV S-channel mean (0–255)
        -   `texture` — Laplacian variance (higher = chunkier)
    -   Applies food-specific rules:
        | Food | Condition | Adjustment |
        |------|-----------|------------|
        | rice | brightness > 200 (fluffy white) | −0.15 g/ml |
        | rice | brightness < 160 (compact dry) | +0.10 g/ml |
        | dal | saturation < 40 (watery) | −0.10 g/ml |
        | dal | texture > 200 (chunky) | +0.08 g/ml |
        | sabzi/curry | texture > 300 | +0.10 g/ml |
        | roti | texture > 500 (puffed) | −0.10 g/ml |
    -   Falls back to `get_density()` if `mask_region_bgr is None` or image read fails.

### `estimation/mass_estimator.py` — Pipeline Orchestrator v3 (#9 #10)
*   **`estimate_food_mass(image_bgr, expected_items, plate_profile, debug=False)`**:

**Pipeline steps (revised)**:

| Step | Enhancement | Description |
|------|-------------|-------------|
| 0 | #7 | Quality gate via `validate_image_quality()`. Returns `error_type: "image_quality"` on failure. |
| 1 | — | Preprocessing + perspective warp (unchanged) |
| 2 | #4 | Compartment detection → bbox scale → **ellipse refinement** → `scale_confidence` set to 0.7 (bbox) or 1.0 (ellipse) |
| 3 | #1 #5 | `estimate_depth()` (with smoothing) → `normalize_depth_to_plate` → `depth_to_cm` |
| 4 | #8 | `segment_per_compartment_sam()` when compartments exist, else `segment_full_image_sam()` |
| 5 | #2 #3 | `classify_mask_region()` per mask with `allowed_labels=expected_items` |
| 6 | #9 | `_hungarian_assign()` — optimal mask↔expected_item matching via `scipy.optimize.linear_sum_assignment` |
| 7 | #1 #6 | Per-mask: `apply_food_height_prior()` → `get_dynamic_density()` → volume → mass → macros |
| — | #10 | `_composite_confidence()` per item |

**Enhancement #9 — Hungarian Optimal Assignment**
*   **`_hungarian_assign(food_masks, expected_items, compartments)`**:
    -   Builds an `n×n` cost matrix where `cost[i,j]` = weighted dissimilarity between mask *i* and expected item *j*.
    -   Cost components: compartment-label mismatch (1.0), classifier-label mismatch scaled by `1 - class_conf` (0–2.0), spatial overlap penalty (0–1.0 inverse of best compartment overlap fraction).
    -   Uses `scipy.optimize.linear_sum_assignment` for $O(n^3)$ optimal matching.
    -   Falls back to greedy index-based assignment if scipy is unavailable.

**Enhancement #10 — Composite Confidence Score**
*   **`_composite_confidence(seg_score, class_conf, depth_stability, scale_confidence)`**:
    -   All inputs ∈ [0, 1]. Computes geometric mean: `(seg × class × depth × scale) ** 0.25`.
    -   `depth_stability`: 1.0 if a matching food prior exists, else 0.65.
    -   `scale_confidence`: 1.0 if ellipse calibration succeeded, else 0.70.
    -   Result replaces the raw SAM `stability_score` in `food_items[n].confidence`.
    -   Mean composite confidence replaces the old average-SAM-score top-level `confidence`.

**API Response changes** (additive only — backward-compatible):
```json
{
  "food_items": [
    {
      "name":             "rice",
      "volume_ml":        185.4,
      "mass_g":           196.3,
      "calories":         255.2,
      "protein":          5.3,
      "carbs":            54.9,
      "fat":              0.6,
      "confidence":       0.8134,    // NEW: composite score
      "class_label":      "rice",    // NEW: from MobileNetV3
      "class_confidence": 0.6712     // NEW: raw classifier score
    }
  ],
  "confidence": 0.7901
}
```

---

## 🧬 3.1. CV Deep Dive: The "0 to 100" Journey (v3)

Tracking a single **Dal** portion from camera capture to calorie result.

### **Phase 0: Quality Gate (pre-processing) — NEW**
1.  **Blur Check**: Laplacian variance on the grey image. If below 80, the pipeline aborts immediately with `"Image is too blurry..."`. Time saved: ~4 seconds of wasted inference.
2.  **Tilt Check**: HoughLines extracts dominant edge angle. If deviation > 30° from cardinal axis, the pipeline aborts with `"Camera angle is too steep..."`. The frontend surfaces this as an amber retake prompt.

### **Phase 1: Ingestion (0-10%)**
3.  **Mobile Capture**: User takes a photo. `PlateCapture.jsx` enforces "AI Camera Rules" (top-down, focused, full plate visible).
4.  **Node.js Proxy**: `server.js` streams bytes to disk → pipes stream to Python CV Service via `axios`.

### **Phase 2: Rectification (10-30%)**
5.  **Color Space Shift**: `preprocess.py` converts BGR → LAB. This separates lightness from chrominance, enabling shadow-invariant processing.
6.  **Perspective Warp**: If a 4-point boundary is found, a **Non-Linear Homography Matrix** rectifies the tilted plate into a top-down rectangle.

### **Phase 3: Spatial Calibration (30-50%) — Enhanced #4**
7.  **Ellipse Fit**: `calibrate_scale_from_ellipse()` fits an ellipse to the plate rim. Divides known plate diameter (26 cm) by detected axis length → `cm_per_pixel`. `scale_confidence = 1.0`.
8.  **Fallback Ruler**: If ellipse fails, `compute_scale()` matches bounding-box pixel-width to `plate_config.py`. `scale_confidence = 0.7`.
9.  **Well Mapping**: Adaptive threshold finds dividers → defines $Z_{surface}$ baseline.

### **Phase 4: Volumetric Sensing (50-65%) — Enhanced #1 #5**
10. **Depth Anything (smoothed)**: Neural network predicts relative disparity map. Gaussian blur (5×5) is applied to suppress pixel-level noise *before* rescaling.
11. **Baseline Subtraction**: Depth values on dividers are sampled → subtracted. Plate surface = 0.0 cm.
12. **Height Link**: $H_{cm} = (RelDepth / AbsDepth) \times (1.2 \times Width \times Scale)$.

### **Phase 5: Semantic Segmentation (65-75%) — Enhanced #8**
13. **Per-Compartment SAM**: `SamPredictor` runs on each compartment crop separately with a 3×3 grid of foreground prompts. The highest-scoring mask is re-mapped to full-image coordinates.
14. **Result**: One binary mask per food item, tightly bounded within its plate well.

### **Phase 6: Classification & Optimal Assignment (75-85%) — NEW #2 #3 #9**
15. **MobileNetV3 Classifier**: Each mask crop is classified. ImageNet probabilities are bridged to Indian food labels. OCR label set (`allowed_labels`) boosts matching items by 2.5×.
16. **Hungarian Matching**: Cost matrix built from label mismatch + spatial overlap + classifier confidence. `scipy.optimize.linear_sum_assignment` finds the globally optimal mask↔food pairing.

### **Phase 7: Integration & Density (85-100%) — Enhanced #1 #6 #10**
17. **Hybrid Height Fusion**: `apply_food_height_prior("dal")` fuses neural heights with prior midpoint (3.0 cm) at 70/30, then clamps to [1.5, 3.5] cm. Prevents shadow-induced underestimates.
18. **Voxel Summing**: $V = \sum (H_{fused} + D_{well}) \times (cm\_per\_pixel)^2$
19. **Dynamic Density**: HSV brightness/saturation and Laplacian texture are extracted from Dal pixels. Watery, pale dal → `density = 0.95 g/ml`; chunky dal → `density = 1.13 g/ml`.
20. **Composite Confidence**: $\text{conf} = (seg \times class \times depth\_stability \times scale)^{0.25}$.
21. **Macros**: Mass × `macro_map.py` per-gram factors → Protein/Carbs/Fat.
22. **Report**: `RunContext` compiles every intermediate into `report.html`.

---

## 📱 4. Frontend Deconstruction (`frontend/`)

### `contexts/AppContext.jsx` — Global State
*   **State Units**: `userProfile`, `todaysMenu`, `loading`.
*   **Sync Logic**: 
    - Read `localStorage` on mount (Zero-latency UI).
    - Fetch `/api/menu` to verify if the server version has updated (Consistency).
    - Merge server-side items into local menu state.

### `pages/PlateCapture.jsx` — Input Sanitization (Human-in-the-Loop)
*   Instead of a live camera feed (which lacks browser support for high-res layout bounds), this page presents strict **AI Camera Rules** (Top-Down Angle, Clear Boundaries, Good Lighting, Spatial Separation) to the user *before* invoking the native device camera. This heavily increases the quality of the image fed to the CV Service.

### `pages/Analysis.jsx` — Result Orchestration
*   **Flow**:
    1.  `loadRecommendation`: Fetches calculated portions based on profile.
    2.  `analyzeCapturedPlate`: Sends the photo to the backend CV proxy.
    3.  **The Matching Logic**: Maps CV results (`small_1`) to recommended foods (`dal`) by comparing detected volumes against expected serving sizes.
*   **UI Logic (Lines 150-200)**: Calculates `totalDetectedCals` and compares it to `targetMealCals`. If $Delta > 10\%$, it triggers the "Over-portioned" warning.

### `services/api.js` — The API Wrapper
*   A singleton instance that wraps the browser `fetch` API.
*   **Multipart Handler**: For `uploadMenuImage` and `analyzePlate`, it uses `FormData`. It explicitly leaves the `Content-Type` header empty so the browser can automatically set the boundary.
*   **Search**: Handles URL encoding for food search queries (`/api/foods/search?q=...`).

### `hooks/useErrorHandler.js` — Robustness
*   Implements a **Max-3-Retry** pattern. 
*   If a network fetch fails, the user is given a retry button. After 3 failures, it triggers a hard error message to prevent infinite spinner loops.

---

## 📂 5. Data Schema & Models

### `backend/data/foodDatabase.json`
- **Schema**: `Array<{ id, name, calories, protein, carbs, fat, category, tags, veg }>`.
- **Purpose**: Ground truth for all nutritional calculations. Updated automatically during menu scan.

### `cv_service/config/density_map.py`
- **Schema**: Dictionary mapping names to float densities ($g/ml$).
- **Fallback**: 1.0 (water-like). This ensures mass estimation never returns zero even if the food name is unrecognized.

### `cv_service/config/plate_config.py`
- Defines the physical geometry of the "Indian Mess Thali".
- `standard_mess_thali`: `37cm x 27cm`. 
- Specifies the `depth_cm` of every well to bound volume integration.

---

## 🏁 6. Internal Object Evolution (The "Dal" Life-Cycle)

Tracking the transformation of a data object:
1.  **OCR Stub**: `{ name: "Dal Tadka" }`.
2.  **Database Entry**: Stub $\rightarrow$ `{ protein: 11, dish_type: "dal", category: "protein_main" }`.
3.  **Scale Recommendation**: Entry $\rightarrow$ `{ quantity: 1.5, recommendedGrams: 225, calories: 285 }`.
4.  **The CV Vision**: CV receives name $\rightarrow$ calculates volume ($180ml$) $\rightarrow$ mass ($189g$) $\rightarrow$ `{ actual_mass: 189, estimated_calories: 241 }`.
5.  **Final Matrix Object**: Comparison of $285$ kcal (Rec) vs $241$ kcal (Actual).

---

## 🔬 7. Global Runtime Mechanics & Resilience

### **Failure Propagation**
*   **Network & Stream Failures**:
    - **Broken Mid-Transfer**: If the `axios` stream to the Python service breaks, `server.js` catches the error. It returns a `503 Service Unavailable` with `isOffline: true`. The frontend transitions to a "Manual Analysis" mode.
    - **Partial File Write**: If `multer` crashes during writing, the `upload.single("image")` middleware fails. Node's top-level error handler intercepts the `MulterError`, prevents a process crash, and returns a 400 JSON error.
*   **SAM Empty Results**: If SAM finds no food, `mass_estimator.py` checks `if not food_masks`. It returns a 0-conf result. The frontend `Analysis.jsx` detects this and prompts the user to "Try a clearer photo".

### **The Event Loop & Workers**
- In Node.js, OCR is CPU-heavy. To prevent blocking the Express Event Loop (which would slow down all other users), `Tesseract.js` executes in a **WebAssembly Worker**. 
- In Python, FastAPI uses `uvicorn`. The inference steps (Depth Anything/SAM) are synchronous which saturates the CPU for the specific request, but the underlying server handles network I/O asynchronously.

### **Memory Flow Diagram**
`Browser Image (Bytes)` $\rightarrow$ `Node Stream (Chunks)` $\rightarrow$ `Disk File` $\rightarrow$ `Read Stream` $\rightarrow$ `HTTP Proxy` $\rightarrow$ `Python Matrix`.
This "chunked" flow is why PortionVision can handle high-resolution 12MP photos on low-resource cloud servers (vCPUs/2GB RAM).

---

## 🔬 8. Pipeline Diagnostics & Logging System

### Architecture Overview
The diagnostics system is implemented in `cv_service/diagnostics/run_context.py` as the `RunContext` class. It is **not** a global singleton — it is instantiated per-request inside `mass_estimator.py` and passed explicitly via `ctx=` parameters to every stage function. This makes individual functions independently testable without hidden state.

### Output Directory Lifecycle
*   **Creation**: The `outputs/` directory does **not** exist at clone time. It is created lazily on the first pipeline execution.
*   **Location**: `cv_service/outputs/{timestamp}_{uuid}/` (e.g., `20260406_191042_a3f1c8e2/`).
*   **Rule**: Each run gets a unique directory. Outputs are **never overwritten** across runs.
*   **Git Integrity**: Specific directories designed to hold dynamic or sensitive intermediate outputs are excluded via the project root `.gitignore`. This includes `cv_service/outputs/`, `backend/uploads/` (multer cache), and `backend/data/menu.json` (daily parsed strings).

### Directory Structure (per run)
```
cv_service/outputs/20260406_191042_a3f1c8e2/
├── input/
│   ├── original.png              # Unaltered input image
│   └── metadata.json             # Resolution, dtype, expected_items, plate_profile
├── preprocessing/
│   ├── 01_resized.png
│   ├── 02_denoised.png           # Gaussian blur (5×5)
│   ├── 03_color_normalized.png   # LAB mean-shift
│   ├── 04_contrast_enhanced.png  # CLAHE
│   ├── 05_edges.png              # Canny edge detection
│   └── 06_perspective_warp.png   # 4-point transform (or skip)
├── compartments/
│   ├── 01_adaptive_threshold.png
│   ├── 02_combined_edges.png
│   └── 03_compartments_overlay.png  # Bounding boxes + contours
├── depth/
│   ├── 01_raw_depth.npy          # Float32 Depth array
│   ├── 02_depth_normalized.png   # Grayscale 0–255
│   ├── 03_depth_colored.png      # INFERNO colormap
│   ├── 04_height_relative.npy    # Baseline-subtracted
│   ├── 05_height_relative_colored.png  # JET colormap
│   └── 06_height_cm.npy          # Real-world centimeters
├── segmentation/
│   ├── 01_mask_item_1.png        # Binary mask per food item
│   ├── 02_mask_item_2.png
│   └── NN_segmentation_overlay.png  # Combined colored overlay
├── features/
│   ├── compartments.json         # Detected well labels, bboxes, depths
│   ├── item_1_rice.json          # Per-item area, height, volume, mass
│   └── item_2_dal.json
├── volume/
│   ├── 01_height_map.png         # TURBO heatmap of pixel heights
│   ├── 02_final_annotated.png    # Original + masks + "rice: 185g" labels
│   └── results.json              # Final API response dict
├── logs/
│   ├── pipeline.log              # Human-readable execution log
│   └── run_log.json              # Structured log entries array
└── report.html                   # Self-contained dark-themed HTML viewer
```

### `RunContext` API
| Method | Purpose |
|---|---|
| `next_index(stage)` | Returns next sequential 1-based index for a stage (ensures `01_`, `02_`, ... naming) |
| `save_image(stage, filename, ndarray)` | Writes PNG via `cv2.imwrite`, records in file manifest |
| `save_npy(stage, filename, ndarray)` | Writes `.npy` via `np.save` |
| `save_json(stage, filename, data)` | Writes indented JSON with UTF-8 encoding |
| `log(step, message, params, elapsed, ...)` | Appends structured entry to both `pipeline.log` and in-memory list |
| `generate_report()` | Builds `report.html` from all saved files and log entries |

### Debug Flag Behavior
| `debug=` | Intermediates saved? | Final outputs saved? | HTML Report? |
|---|---|---|---|
| `True` (Default) | ✅ All images + `.npy` arrays + per-item JSONs | ✅ Annotated image + `results.json` | ✅ |
| `False` | ❌ Skipped | ✅ Annotated image + `results.json` | ✅ |
*Note: In the current `routes.py`, `debug` defaults to `True` to ensure full logging for developers.*

### Log Format
Each pipeline step writes to `logs/pipeline.log`:
```
2026-04-06 19:10:42 │ INFO │ [Preprocessing] Resize applied │ params={'original': '4032x3024', 'target_long_edge': 1024, 'scale': 0.254} │ time=0.0123s │ output=01_resized.png
2026-04-06 19:10:44 │ INFO │ [Depth Estimation] Depth Anything depth map computed │ params={'device': 'cpu', 'shape': [768, 1024]} │ time=1.8421s │ output=03_depth_colored.png
2026-04-06 19:10:46 │ INFO │ [Pipeline] ✅ Pipeline complete │ params={'total_food_items': 3, 'avg_confidence': 0.89} │ time=4.231s
```

### HTML Report
The `report.html` file is a self-contained dark-themed page that:
1.  Displays run metadata (ID, debug flag, file count).
2.  Shows every saved image grouped by pipeline stage, in processing order.
3.  Renders JSON files as formatted `<pre>` blocks.
4.  Includes a full execution log table (step, message, params, elapsed time).

### API Usage
```bash
# Normal mode — only final outputs saved
curl -X POST http://localhost:8000/estimate-portion \
  -F "image=@plate.jpg" -F "expected_items=rice,dal,sabzi"

# Debug mode — full intermediate pipeline saved
curl -X POST http://localhost:8000/estimate-portion \
  -F "image=@plate.jpg" -F "expected_items=rice,dal,sabzi" -F "debug=true"
```
The debug response includes:
```json
{
  "food_items": [...],
  "confidence": 0.82,
  "_debug": {
    "run_id": "20260406_191042_a3f1c8e2",
    "run_dir": "cv_service/outputs/20260406_191042_a3f1c8e2",
    "report": "cv_service/outputs/20260406_191042_a3f1c8e2/report.html",
    "pipeline_time_s": 4.231
  }
}
```

---

## 🚀 9. Developer Setup & Fast-Start

The PortionVision ecosystem requires 3 distinct processes. To run locally, spawn three separate terminals from the repository root.

### The 3-Terminal Execution
**1. Terminal: CV Service (Python Engine)**
```powershell
cd cv_service
.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
*Note: Binds to `0.0.0.0` so it can receive proxy calls originating from network interfaces.*

**2. Terminal: Backend (Node.js/OCR)**
```powershell
cd backend
 run dev
```
*Note: Binds to `http://localhost:5000` but uses Express's default `0.0.0.0` allowing local intranet connections.*

**3. Terminal: Frontend (React UI)**
```powershell
cd frontend
npm run dev
```

### 📱 Mobile Device Testing Architecture
Running the AI stack live on a mobile phone requires connecting to the Vite server via the Laptop's local network IP.

1. Locate the **Network URI** from Vite's startup log (e.g., `http://10.174.1.162:5173/`).
2. Type this exact URI into the mobile Safari/Chrome browser. Both devices must be on the same WiFi.

**Proxy Workflow**:
Because of the setup in `frontend/vite.config.js`:
* `host: true` broadcasts the front-end over the network.
* `proxy: { '/api': { target: 'http://127.0.0.1:5000' } }` handles the CORS boundary. 
When the phone (at `10.174.x.x`) sends an image, it posts to `/api/analyze-plate`. The laptop's Vite dev server intercepts this call, routes it directly into the `server.js` running on `localhost:5000`, which streams it via axios to `localhost:8000`. This entire chained proxy means the mobile browser requires NO configurations to communicate with the heavy backend engines.

---

---
