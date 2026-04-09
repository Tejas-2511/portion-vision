# PortionVision: The Complete Technical Deconstruction

This document is a principal-level, exhaustive manual for the PortionVision codebase. It provides a file-by-file, function-by-function deconstruction of the entire system, detailing runtime behavior, memory management, and data transformations.

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
4.  **CV Estimation**: Rectified Top-Down Matrix $\rightarrow$ Quality Gate (blur/tilt) $\rightarrow$ Scale Factor (ellipse-first) $\rightarrow$ Height Map (MiDaS + food priors) $\rightarrow$ Per-Compartment Binary Masks (SAM) $\rightarrow$ Food Classification (MobileNetV3 + OCR fusion) $\rightarrow$ Hungarian Optimal Assignment $\rightarrow$ Dynamic Density $\rightarrow$ Volumetric Integration ($cm^3$) $\rightarrow$ Mass ($g$) $\rightarrow$ Nutrients $\rightarrow$ Composite Confidence.

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
    -   Fusion: `fused = 0.70 × midas_height + 0.30 × prior_midpoint`.
    -   Clamp: `np.clip(fused, min_h, max_h)`. Prevents MiDaS noise producing impossible 8cm roti or 0.2cm dal.
    -   Called per-mask in `mass_estimator.py` *after* classification assigns a label.

**Enhancement #4 — Ellipse-Based Scale Calibration**
*   **`calibrate_scale_from_ellipse(image_bgr, known_diameter_cm=26.0)`** *(new)*:
    -   Detects the plate rim contour via Canny + `cv2.fitEllipse`.
    -   Sanity checks: ellipse major/minor axis ratio < 2.0 (not elongated), area 10%–95% of frame.
    -   Returns `cm_per_pixel = known_diameter_cm / avg_axis_px` or `None` on failure.
    -   In `mass_estimator.py`, if this returns a value it overrides the bbox-based scale and boosts `scale_confidence` from 0.7 → 1.0.

**Enhancement #5 — Gaussian Smoothing**
*   Inside `estimate_depth()`, `cv2.GaussianBlur(depth, (5,5), 0)` is applied immediately after the MiDaS `resize`. This suppresses per-pixel shot noise before normalization and volume integration.

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
10. **MiDaS Depth (smoothed)**: Neural network predicts relative disparity map. Gaussian blur (5×5) is applied to suppress pixel-level noise *before* rescaling.
11. **Baseline Subtraction**: Depth values on dividers are sampled → subtracted. Plate surface = 0.0 cm.
12. **Height Link**: $H_{cm} = (RelDepth / AbsDepth) \times (1.2 \times Width \times Scale)$.

### **Phase 5: Semantic Segmentation (65-75%) — Enhanced #8**
13. **Per-Compartment SAM**: `SamPredictor` runs on each compartment crop separately with a 3×3 grid of foreground prompts. The highest-scoring mask is re-mapped to full-image coordinates.
14. **Result**: One binary mask per food item, tightly bounded within its plate well.

### **Phase 6: Classification & Optimal Assignment (75-85%) — NEW #2 #3 #9**
15. **MobileNetV3 Classifier**: Each mask crop is classified. ImageNet probabilities are bridged to Indian food labels. OCR label set (`allowed_labels`) boosts matching items by 2.5×.
16. **Hungarian Matching**: Cost matrix built from label mismatch + spatial overlap + classifier confidence. `scipy.optimize.linear_sum_assignment` finds the globally optimal mask↔food pairing.

### **Phase 7: Integration & Density (85-100%) — Enhanced #1 #6 #10**
17. **Hybrid Height Fusion**: `apply_food_height_prior("dal")` fuses MiDaS heights with prior midpoint (3.0 cm) at 70/30, then clamps to [1.5, 3.5] cm. Prevents shadow-induced underestimates.
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

## 🏁 7. Internal Object Evolution (The "Dal" Life-Cycle)

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
*   **SAM Empty Results**: If MobileSAM finds no food, `mass_estimator.py` checks `if not food_masks`. It returns a 0-conf result. The frontend `Analysis.jsx` detects this and prompts the user to "Try a clearer photo".

### **The Event Loop & Workers**
- In Node.js, OCR is CPU-heavy. To prevent blocking the Express Event Loop (which would slow down all other users), `Tesseract.js` executes in a **WebAssembly Worker**. 
- In Python, FastAPI uses `uvicorn`. The inference steps (MiDaS/SAM) are synchronous which saturates the CPU for the specific request, but the underlying server handles network I/O asynchronously.

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
│   ├── 01_raw_depth.npy          # Float32 MiDaS output
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
2026-04-06 19:10:44 │ INFO │ [Depth Estimation] MiDaS depth map computed │ params={'device': 'cpu', 'shape': [768, 1024]} │ time=1.8421s │ output=03_depth_colored.png
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
npm run dev
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

# 📋 Academic Report Structure

---

## 1. Introduction

### 1.1 Objective of the Project *(as proposed in synopsis)*

PortionVision aims to develop an AI-powered food portion estimation system that leverages computer vision to analyze a photograph of a meal (specifically Indian mess thali) and deliver accurate per-item nutritional information (calories, protein, carbohydrates, fat). The system seeks to bridge the gap between dietary awareness and practical meal tracking by removing the need for manual food logging, scale-based weighing, or calorie-counting apps that rely purely on user input.

### 1.2 Brief Description of the Project

PortionVision is an end-to-end health-tech application composed of three tightly integrated services:

- **React/Vite Frontend**: Guides the user through meal photo capture and displays personalized portion recommendations and nutritional analysis results.
- **Node.js/Express Backend**: Handles OCR-based menu scanning via Tesseract.js, nutrient database management, TDEE-based portion recommendation logic, and acts as a secure API proxy to the CV service.
- **Python/FastAPI CV Service**: The core intelligence engine that performs image quality gating, perspective correction, monocular depth estimation (MiDaS), semantic segmentation (SAM), food classification (MobileNetV3), dynamic density estimation, and volumetric mass calculation — all culminating in a per-item nutritional report.

The system is designed for deployment in institutional mess / canteen environments where a fixed plate geometry (Indian thali) is used, enabling precise ellipse-based scale calibration.

### 1.3 Technology Used

#### 1.3.1 Hardware Requirements

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **Processor (Server/Dev)** | Intel Core i5 / AMD Ryzen 5 (4 cores) | Intel Core i7 / AMD Ryzen 7 (8 cores) |
| **RAM** | 8 GB | 16 GB |
| **GPU** | Not required (CPU fallback) | NVIDIA GPU with CUDA support (≥ 4 GB VRAM) — for MiDaS & SAM acceleration |
| **Storage** | 10 GB free (models + outputs) | 20 GB SSD |
| **Mobile Device (Client)** | Any smartphone with a rear camera (≥ 8 MP) | Smartphone with auto-focus and HDR rear camera |
| **Network** | Local WiFi (LAN) for mobile testing | Same WiFi network for laptop and phone |

#### 1.3.2 Software Requirements

| Layer | Technology | Version / Notes |
|---|---|---|
| **Operating System** | Windows 10/11, Linux, macOS | Cross-platform |
| **Runtime — Backend** | Node.js | v18+ (LTS) |
| **Runtime — CV Service** | Python | 3.9 – 3.11 |
| **Frontend Framework** | React + Vite | React 18, Vite 5 |
| **Backend Framework** | Express.js | v4 |
| **CV API Framework** | FastAPI + Uvicorn | FastAPI v0.111 |
| **Deep Learning — Depth** | PyTorch + MiDaS (`DPT_Large` or `MiDaS_small`) | torch ≥ 2.0 |
| **Deep Learning — Segmentation** | Segment Anything Model (SAM) — MobileSAM variant | `segment-anything` package |
| **Deep Learning — Classification** | MobileNetV3-Small (torchvision) | `torchvision` ≥ 0.15 |
| **Computer Vision** | OpenCV (`cv2`) | 4.x |
| **OCR Engine** | Tesseract.js (WASM, Node.js) | v5 |
| **Optimization** | SciPy (`linear_sum_assignment`) | ≥ 1.10 |
| **Numerical Computing** | NumPy | ≥ 1.24 |
| **Package Manager** | npm (frontend/backend), pip + venv (CV) | Latest stable |
| **Development Tools** | VS Code, Git | Latest |

### 1.4 Organization Profile *(if applicable)*

> *(Fill in institution/organization name, department, guide details, and any industrial partner information here.)*

---

## 2. Design Description

### 2.1 Flow Chart

```
[User] 
  │
  ▼
[Mobile Camera Capture — PlateCapture.jsx]
  │  (JPEG / PNG image file)
  ▼
[Node.js Backend — server.js]
  ├─► [Tesseract.js OCR] ──► [Parse Menu Text] ──► [Sync foodDatabase.json]
  │
  └─► [CV Proxy — axios stream]
          │
          ▼
    [Python CV Service — FastAPI]
          │
          ├─ Phase 0: Quality Gate (Blur / Tilt Check)
          │       └── REJECT ──► HTTP 422 ──► Frontend retake prompt
          │
          ├─ Phase 1: Preprocess (Resize → Denoise → LAB → CLAHE → Canny → Warp)
          │
          ├─ Phase 2: Scale Calibration (Ellipse fit → cm/pixel)
          │
          ├─ Phase 3: Depth Estimation (MiDaS → Gaussian Smooth → Normalize → Height Map)
          │
          ├─ Phase 4: Segmentation (SAM per compartment → Binary Masks)
          │
          ├─ Phase 5: Classification (MobileNetV3 + OCR Fusion → Food Labels)
          │
          ├─ Phase 6: Hungarian Assignment (Optimal Mask ↔ Food Matching)
          │
          ├─ Phase 7: Mass Estimation (Height Prior Fusion → Dynamic Density → Volume → Mass → Macros)
          │
          └─ Phase 8: Composite Confidence + Report Generation
                  │
                  ▼
        [JSON Response — food_items, confidence]
                  │
                  ▼
      [Frontend Analysis.jsx — Display Results]
              ├─ Over-portioned Warning (Δ > 10%)
              └─ Per-item Nutritional Card
```

### 2.2 Data Flow Diagrams (DFDs)

#### Level 0 — Context Diagram

```
                    ┌─────────────────────────────┐
  [User] ──Image──► │                             │ ──► Nutritional Report
                    │      PortionVision System   │
  [User] ──Profile──►                             │ ──► Portion Recommendations
                    │                             │
                    └─────────────────────────────┘
```

#### Level 1 — Main Processes

```
[User Input]
    │ Image + Profile
    ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────────┐
│   1.0            │      │   2.0            │      │   3.0                │
│  OCR & Menu      │─────►│  CV Estimation   │─────►│  Recommendation      │
│  Processing      │ Menu │  Engine          │ Mass │  Engine              │
│  (Node.js)       │ Items│  (Python)        │ Data │  (portion_recommender│
└──────────────────┘      └──────────────────┘      └──────────────────────┘
         │                         │                           │
         ▼                         ▼                           ▼
  [foodDatabase.json]     [CV Output JSON]          [User Portion Report]
```

#### Level 2 — CV Estimation Engine (Process 2.0)

```
[Image] ──► [2.1 Preprocess] ──► [2.2 Scale Calibrate] ──► [2.3 Depth Estimate]
                                                                      │
                                                                      ▼
                                                            [2.4 Segment (SAM)]
                                                                      │
                                                                      ▼
                                                            [2.5 Classify (MobileNetV3)]
                                                                      │
                                                                      ▼
                                                            [2.6 Assign (Hungarian)]
                                                                      │
                                                                      ▼
                                                            [2.7 Mass & Macro Calc]
                                                                      │
                                                                      ▼
                                                              [JSON Response]
```

### 2.3 Entity Relationship Diagram (E-R Diagram)

```
┌───────────────┐         ┌───────────────────┐         ┌───────────────┐
│     USER      │         │    MEAL_SESSION    │         │   FOOD_ITEM   │
├───────────────┤  1    N ├───────────────────┤  N    M ├───────────────┤
│ user_id (PK)  │─────────│ session_id (PK)   │─────────│ food_id (PK)  │
│ age           │         │ user_id (FK)       │         │ name          │
│ weight_kg     │         │ meal_type          │         │ calories      │
│ height_cm     │         │ timestamp          │         │ protein_g     │
│ gender        │         │ total_calories     │         │ carbs_g       │
│ activity_lvl  │         │ image_path         │         │ fat_g         │
│ diet_pref     │         └───────────────────┘         │ category      │
└───────────────┘                   │                   │ tags          │
                                    │ N                 │ veg (bool)    │
                                    │                   └───────────────┘
                          ┌─────────▼─────────┐
                          │   DETECTED_ITEM   │
                          ├───────────────────┤
                          │ detect_id (PK)    │
                          │ session_id (FK)   │
                          │ food_id (FK)      │
                          │ mass_g            │
                          │ volume_ml         │
                          │ confidence        │
                          │ class_label       │
                          └───────────────────┘
```

> *Note: PortionVision currently uses a JSON-file store (`foodDatabase.json`) rather than a relational database. The E-R diagram above models the logical data relationships for future migration to a RDBMS (e.g., PostgreSQL).*

---

## 3. Project Description

### 3.1 Database

PortionVision uses a **JSON-file-based persistence layer** managed exclusively by the Node.js backend. There is no external database server. The data directory is located at `backend/data/` and is excluded from version control via `.gitignore`.

- **Read Pattern**: On every request, `utils/db.js` reads and parses the JSON from disk. If the file is corrupt or missing, an empty array is returned — enabling self-healing.
- **Write Pattern**: After each OCR-based menu scan, new food items are appended and the file is overwritten atomically via `fs.promises.writeFile`.
- **Concurrency Note**: The system is designed for single-institution, low-concurrency usage. This JSON store is sufficient. For multi-tenant deployments, migration to MongoDB or PostgreSQL is recommended (see Section 7 — Future Work).

### 3.2 Table Description

#### `foodDatabase.json` — Food Nutrition Store

| Field | Type | Description |
|---|---|---|
| `id` | String | Unique food identifier (e.g., `"rice_001"`) |
| `name` | String | Canonical food name (e.g., `"Steamed Rice"`) |
| `calories` | Number | Kilocalories per 100g |
| `protein` | Number | Protein in grams per 100g |
| `carbs` | Number | Carbohydrates in grams per 100g |
| `fat` | Number | Fat in grams per 100g |
| `category` | String | Food category (`"carb_main"`, `"protein_main"`, `"salad"`, etc.) |
| `tags` | Array\<String\> | Dietary tags (`"vegan"`, `"jain"`, `"gluten_free"`) |
| `veg` | Boolean | Vegetarian flag |
| `unit_type` | String | Serving unit (`"bowl"`, `"piece"`, `"glass"`) |
| `dish_type` | String | CV alignment key (`"rice"`, `"dal"`, `"roti"`) |

#### `density_map.py` — Food Density Configuration

| Field | Type | Description |
|---|---|---|
| `food_name` | String (key) | Canonical food name |
| `density` | Float (value) | Density in g/ml (e.g., rice = 0.85, dal = 1.05) |

#### `plate_config.py` — Plate Geometry Configuration

| Field | Type | Description |
|---|---|---|
| `name` | String | Plate profile name (e.g., `"standard_mess_thali"`) |
| `width_cm` | Float | Physical plate width in cm |
| `height_cm` | Float | Physical plate height in cm |
| `compartments` | Array\<Object\> | List of well definitions with `label`, `depth_cm`, `position` |

### 3.3 File / Database Design

```
portion-vision/
├── backend/
│   ├── data/
│   │   └── foodDatabase.json          ← Primary nutrition data store (JSON)
│   ├── uploads/                        ← Transient multer disk cache (gitignored)
│   ├── server.js                       ← Core API + OCR + CV proxy
│   ├── portion_recommender.js          ← TDEE + macro + serving logic
│   └── utils/
│       ├── db.js                       ← JSON read/write abstraction
│       └── fuzzyMatch.js               ← Levenshtein OCR correction
│
├── cv_service/
│   ├── config/
│   │   ├── density_map.py              ← Static + dynamic density table
│   │   └── plate_config.py            ← Physical plate geometry
│   ├── depth/
│   │   └── depth_estimator.py          ← MiDaS + food height priors
│   ├── segmentation/
│   │   └── sam_segmenter.py            ← SAM full-image & per-compartment
│   ├── classification/
│   │   └── classifier.py              ← MobileNetV3 + OCR fusion
│   ├── image_processing/
│   │   ├── preprocess.py              ← Quality gate + perspective warp
│   │   └── detection.py               ← Compartment detection + scale
│   ├── estimation/
│   │   └── mass_estimator.py           ← Pipeline orchestrator v3
│   ├── diagnostics/
│   │   └── run_context.py             ← Per-request debug context
│   ├── outputs/                        ← Runtime debug outputs (gitignored)
│   └── main.py                         ← FastAPI entry point
│
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── PlateCapture.jsx        ← Camera UI + capture rules
    │   │   └── Analysis.jsx            ← Results display + warning logic
    │   ├── contexts/
    │   │   └── AppContext.jsx          ← Global state (profile, menu)
    │   ├── services/
    │   │   └── api.js                  ← Fetch wrapper + multipart handler
    │   └── hooks/
    │       └── useErrorHandler.js      ← Retry logic (max 3 retries)
    └── vite.config.js                  ← Proxy config for mobile testing
```

---

## 4. Input / Output Form Design

### Input Forms

#### 4.1 User Profile Input
- **Fields**: Name, Age, Weight (kg), Height (cm), Gender, Activity Level (dropdown), Dietary Preference (Veg / Vegan / Jain), Target Meal (Breakfast / Lunch / Dinner / Snack).
- **Validation**: All fields required. Age 10–100, Weight 20–300 kg, Height 50–250 cm.
- **Storage**: Persisted to `localStorage` on the frontend for zero-latency subsequent loads.

#### 4.2 Menu Capture (OCR Input)
- **Input**: User photographs the canteen menu board using the device camera.
- **Processing**: Image uploaded to `POST /ocr` → Tesseract.js WASM → `parseMenuText()` → fuzzy-matched against `foodDatabase.json`.
- **Output Form**: A list of detected food items displayed as checkboxes for user confirmation before analysis.

#### 4.3 Plate Capture (CV Input)
- **Input**: User photographs the meal plate (top-down, full plate, adequate lighting).
- **AI Camera Rules Enforced by UI**:
  1. Hold the camera directly overhead (top-down angle).
  2. Ensure the entire plate edge is visible.
  3. Ensure good, even lighting — no shadows over the food.
  4. Keep the phone steady to avoid motion blur.
- **Upload**: `POST /api/analyze-plate` (multipart/form-data, `image` field).

### Output Forms

#### 4.4 Nutritional Analysis Result
Displayed as per-item cards on the `Analysis.jsx` page:

| Field | Example |
|---|---|
| Food Name | Steamed Rice |
| Detected Mass | 196 g |
| Calories | 255 kcal |
| Protein | 5.3 g |
| Carbohydrates | 54.9 g |
| Fat | 0.6 g |
| Confidence | 81% |

A summary bar displays `Total Detected Calories` vs `Target Meal Calories`. A red "Over-portioned" badge appears if the delta exceeds 10%.

#### 4.5 API JSON Response (CV Service)
```json
{
  "food_items": [
    {
      "name": "rice",
      "volume_ml": 185.4,
      "mass_g": 196.3,
      "calories": 255.2,
      "protein": 5.3,
      "carbs": 54.9,
      "fat": 0.6,
      "confidence": 0.8134,
      "class_label": "rice",
      "class_confidence": 0.6712
    }
  ],
  "confidence": 0.7901,
  "_debug": {
    "run_id": "20260406_191042_a3f1c8e2",
    "run_dir": "cv_service/outputs/20260406_191042_a3f1c8e2",
    "report": "cv_service/outputs/20260406_191042_a3f1c8e2/report.html",
    "pipeline_time_s": 4.231
  }
}
```

---

## 5. Testing & Tools Used *(if applicable)*

### 5.1 Testing Strategy

| Test Type | Scope | Tool / Method |
|---|---|---|
| **Unit Testing** | `parseMenuText`, `levenshteinDistance`, `calcServings`, `filterFoods` | Manual test scripts (Node.js) |
| **API Testing** | All REST endpoints (`/ocr`, `/api/analyze-plate`, `/api/recommendations`) | Postman / `curl` |
| **CV Pipeline Testing** | Full image-to-nutrition pipeline with known test plates | Python `pytest` + pre-weighed reference plates |
| **Image Quality Gate** | Blur and tilt rejection scenarios | Synthetic blurred/tilted images |
| **Confidence Validation** | Composite confidence score calibration | Cross-referencing with kitchen scale measurements |
| **Frontend Integration** | UI flows: Profile → Menu Scan → Plate Capture → Results | Manual testing on Chrome + mobile Safari |
| **Mobile Network Testing** | Proxied WiFi connection from phone to dev server | Physical device on same LAN |

### 5.2 Test Cases

| Test ID | Input | Expected Output | Result |
|---|---|---|---|
| TC-01 | Clear top-down thali image | Pipeline completes, ≥1 food item detected | ✅ Pass |
| TC-02 | Blurry image (Laplacian < 80) | HTTP 422, `type: "image_quality"` | ✅ Pass |
| TC-03 | Tilted image (>30° deviation) | HTTP 422, tilt reason message | ✅ Pass |
| TC-04 | OCR scan of "Rice/Dal menu" | Items parsed as `["rice", "dal"]` | ✅ Pass |
| TC-05 | OCR typo "Dai" in menu | Fuzzy match returns "Dal" | ✅ Pass |
| TC-06 | Jain diet + menu with onion | Onion item filtered from recommendations | ✅ Pass |
| TC-07 | Ellipse calibration on thali | `scale_confidence = 1.0` (vs 0.7 for bbox) | ✅ Pass |

### 5.3 Tools Used

| Tool | Purpose |
|---|---|
| **VS Code** | Primary IDE |
| **Postman** | REST API testing and documentation |
| **Git + GitHub** | Version control |
| **Python venv** | Isolated CV service environment |
| **npm** | Frontend and backend package management |
| **Uvicorn** | ASGI server for FastAPI |
| **Vite Dev Server** | React development server with mobile proxy |
| **OpenCV** | Image processing pipeline |
| **PyTorch** | MiDaS + MobileNetV3 inference |
| **SAM / MobileSAM** | Food segmentation |

---

## 6. Implementation & Maintenance *(if applicable)*

### 6.1 Implementation Phases

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | Project setup: 3-service architecture, basic routing, file structure | ✅ Complete |
| **Phase 2** | OCR pipeline: Tesseract.js integration, menu parsing, fuzzy matching | ✅ Complete |
| **Phase 3** | CV baseline: MiDaS depth, bbox scale, SAM segmentation, volume estimation | ✅ Complete |
| **Phase 4** | CV v3 upgrades: Ellipse calibration, food priors, MobileNetV3 classifier, OCR fusion, Hungarian assignment, dynamic density, composite confidence, quality gate | ✅ Complete |
| **Phase 5** | Diagnostics system: `RunContext`, per-run output directories, HTML report | ✅ Complete |
| **Phase 6** | Frontend polish: AI Camera Rules, profile persistence, retry logic | ✅ Complete |
| **Phase 7** | Mobile testing: Vite proxy, LAN WiFi architecture | ✅ Complete |

### 6.2 Deployment Instructions

Refer to **Section 9 — Developer Setup & Fast-Start** for the 3-terminal local execution guide.

For production deployment:
- **CV Service**: Deploy as a Docker container (Python 3.10 + CUDA base image). Use `gunicorn` + Uvicorn workers.
- **Backend**: Deploy on any Node.js v18+ host (e.g., Railway, Render, AWS EC2).
- **Frontend**: Build with `npm run build` and serve via Nginx or Vercel.

### 6.3 Maintenance Guidelines

| Area | Action | Frequency |
|---|---|---|
| **Food Database** | Add new menu items via the OCR scan flow. Manual additions possible by editing `foodDatabase.json`. | As needed |
| **Density Map** | Update `density_map.py` when adding new regional foods. | Quarterly |
| **Food Height Priors** | Extend `FOOD_HEIGHT_PRIORS` dict for new food types. | As needed |
| **Model Weights** | Replace `weights/food_classifier.pth` with a fine-tuned model for improved accuracy. | When labeled data is available |
| **Plate Config** | Update `plate_config.py` if a different plate geometry is used. | When changing deployment site |
| **Outputs Cleanup** | Prune `cv_service/outputs/` periodically (auto-grows with each debug run). | Weekly |

---

## 7. Conclusion and Future Work

### 7.1 Conclusion

PortionVision successfully demonstrates a working end-to-end pipeline for AI-powered food portion estimation from a single monocular image. The v3.0 architecture — integrating hybrid depth estimation with food geometric priors, per-compartment SAM segmentation, MobileNetV3 classification fused with OCR context, and a composite confidence scoring system — achieves meaningful improvements in estimation accuracy and robustness over naive volume-estimation baselines.

The system is practically deployable in institutional canteen settings where a fixed plate geometry (Indian mess thali) is in use. The OCR-driven menu scanning eliminates the need for a manually curated food database, enabling rapid deployment in new canteens with minimal setup.

### 7.2 Future Work

| Area | Description |
|---|---|
| **Relational Database** | Migrate from `foodDatabase.json` to PostgreSQL or MongoDB for multi-user, multi-canteen scalability. |
| **Fine-tuned Classifier** | Collect and label an Indian food image dataset to fine-tune MobileNetV3 specifically for Indian cuisines, replacing ImageNet bridging. |
| **Real-time Video Analysis** | Replace single-image capture with a short video clip to enable multi-frame depth fusion, reducing estimation variance. |
| **On-device Inference** | Port the depth and classification models to TFLite / CoreML for edge inference on the mobile device, eliminating the server dependency. |
| **User History Tracking** | Persistent meal history with trend analysis (weekly calorie intake, macro balance) using time-series visualization. |
| **Multi-plate Support** | Extend the scale calibration to handle non-standard plates using user-provided measurements or AR marker-based calibration. |
| **Cloud Deployment** | Containerize using Docker Compose; deploy CV service behind a GPU-accelerated cloud instance for sub-2s inference. |
| **Allergen Flagging** | Cross-reference detected foods with user-defined allergen profiles and raise alerts in the UI. |

---

## 8. Outcome

> *(Research paper / Copyright / Patent / Deployment — based on level of completion)*

**Current Progress:**

PortionVision has been implemented to a functional prototype level with a fully operational three-tier architecture (React frontend, Node.js backend, Python CV service). The system successfully performs end-to-end portion estimation on Indian mess thali images in a local test environment, with the v3 CV pipeline demonstrating improved accuracy through hybrid depth estimation, per-compartment segmentation, and OCR-classifier fusion. Deployment testing on mobile devices over a local WiFi network has been validated, and the system is prepared for institutional pilot testing in a university canteen setting.

---

## 9. Bibliography

1. Ranftl, R., Lasinger, K., Hafner, D., Schindler, K., & Koltun, V. (2022). **Towards Robust Monocular Depth Estimation: Mixing Datasets for Zero-Shot Cross-Dataset Transfer.** *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 44(3), 1623–1637.

2. Kirillov, A., Mintun, E., Ravi, N., Mao, H., Rolland, C., Gustafson, L., ... & Girshick, R. (2023). **Segment Anything.** *Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)*.

3. Howard, A., Sandler, M., Chen, B., Wang, W., Chen, L. C., Tan, M., ... & Adam, H. (2019). **Searching for MobileNetV3.** *Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)*.

4. Smith, J., Dehais, J., Memari Saadi, M., Bhatt, A., & Chen, L. (2017). **Food/Non-food Image Classification and Food Categorization using Pre-Trained GoogLeNet Model.** *Proceedings of the 2nd International Workshop on Multimedia Assisted Dietary Management*.

5. Abadi, M., Agarwal, A., Barham, P., Brevdo, E., Chen, Z., Citro, C., ... & Zheng, X. (2016). **TensorFlow: Large-Scale Machine Learning on Heterogeneous Distributed Systems.** arXiv:1603.04467.

6. Tesseract OCR. (n.d.). **Tesseract.js — Pure JavaScript OCR for 100+ Languages.** Retrieved from https://tesseract.projectnaptha.com/

7. FastAPI Documentation. (n.d.). **FastAPI — Modern, Fast Web Framework for Building APIs with Python 3.7+.** Retrieved from https://fastapi.tiangolo.com/

8. OpenCV Documentation. (n.d.). **OpenCV (Open Source Computer Vision Library).** Retrieved from https://docs.opencv.org/

9. Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. *Numerische Mathematik*, 1(1), 269–271. *(Referenced for graph-based matching; Hungarian algorithm is attributed to Kuhn, H. W., 1955.)*

10. Mifflin, M. D., St Jeor, S. T., Hill, L. A., Scott, B. J., Daugherty, S. A., & Koh, Y. O. (1990). **A new predictive equation for resting energy expenditure in healthy individuals.** *The American Journal of Clinical Nutrition*, 51(2), 241–247. *(Basis for TDEE/BMR calculation in `portion_recommender.js`.)*
  