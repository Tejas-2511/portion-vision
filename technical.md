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
4.  **CV Estimation**: Rectified Top-Down Matrix $\rightarrow$ Scale Factor $\rightarrow$ Height Map (MiDaS) $\rightarrow$ Binary Masks (SAM) $\rightarrow$ Volumetric Integration ($cm^3$) $\rightarrow$ Mass ($g$) $\rightarrow$ Nutrients.

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

## 🐍 3. CV Service Deconstruction (`cv_service/`)

### `main.py` & `api/routes.py`
*   **FastAPI Engine**: Uses `async def` and `UploadFile`. 
*   **Binary Buffer Flow**: `image.read()` pulls bytes $\rightarrow$ `np.frombuffer` $\rightarrow$ `cv2.imdecode`. The image is now a BGR matrix in RAM.
*   **Debug Parameter**: The `/estimate-portion` endpoint accepts an optional `debug: bool = Form(False)` field. When enabled, the full diagnostic pipeline is activated and the response includes a `_debug` metadata block containing the `run_id`, `run_dir` path, and `report` HTML path.

### `image_processing/preprocess.py` — The Warp Engine
*   **`process_image(image, target_long_edge, ctx=None)`**:
    1.  Resizes longest edge to 1024px for consistent inference.
    2.  Gaussian denoise (5×5 kernel).
    3.  LAB color normalization (mean-shift on L/A/B channels).
    4.  CLAHE contrast enhancement (clipLimit=2.0, 8×8 grid).
    5.  `Canny` edges $\rightarrow$ `findContours`.
    6.  If a 4-point polygon (the plate) is found, it calls `_four_point_transform`.
*   **`_four_point_transform`**: 
    - Uses **Perspective Warp** to rectify the camera angle. This ensures that a tilted photo is converted into a geometrically accurate top-down view for pixel-to-area calculations.
*   **Diagnostics**: When `ctx.debug=True`, saves 6 intermediates: `01_resized.png`, `02_denoised.png`, `03_color_normalized.png`, `04_contrast_enhanced.png`, `05_edges.png`, `06_perspective_warp.png`.

### `image_processing/detection.py` — Well Calibration
*   **`find_compartments(image, ctx=None)`**: 
    - Uses `adaptiveThreshold` ($15 \times 15$ window) to find divider walls under varying lighting.
    - Filters by $2\%$ to $90\%$ of plate area to isolate wells from noise.
    - **Diagnostics**: Saves adaptive threshold, combined edge map, and a bounding-box overlay with contour annotations.
*   **`compute_scale`**: 
    - Critical calibration step. Matches the largest detected contour to the largest width/height in `config/plate_config.py`.
    - Result: A fixed `cm_per_pixel` scale factor (e.g., 0.045).

### `depth/depth_estimator.py` — Monocular Vision
*   **Model**: MiDaS v2.1 Small loader via `torch.hub`.
*   **`estimate_depth(image_bgr, ctx=None)`**: Runs MiDaS inference. When debugging, saves raw `.npy`, normalized grayscale, and INFERNO-colored depth visualization.
*   **`normalize_depth_to_plate(depth_map, plate_mask, ctx=None)`**: Subtracts the median value of the dividers (mask) from the depth map. This sets the stainless steel plate surface to $Z = 0$. Saves relative height `.npy` and JET-colored visualization.
*   **`depth_to_cm(height_map_relative, raw_depth, cm_per_pixel, image_width_px, ctx=None)`**:
    - **Mathematics**: $H_{cm} = (RelativeDepth / AbsoluteDepth) \times Z_{est}$.
    - $Z_{est}$ is calibrated as $1.2 \times image\_width \times scale$. This is camera-distance invariant.
    - **Diagnostics**: Saves the final height-in-cm array as `.npy`.

### `segmentation/sam_segmenter.py` — Deep Segmentation
*   **`segment_full_image_sam(image_bgr, ctx=None)`**:
*   **MobileSAM Integration**: Lightweight Vit-T model for fast inference.
*   **Foodness Heuristics**:
    - **Saturation Filter**: `Mean Sat < 12`. Discards stainless steel (neutral gray).
    - **Texture Filter**: `Mean Laplacian < 15`. Discards smooth surfaces.
    - Result: Only areas with color or texture (food) are segmented.
*   **Diagnostics**: Saves each food item's binary mask (`01_mask_item_N.png`) and a combined semi-transparent overlay with contour borders, confidence labels, and distinct colors per item.

### `estimation/mass_estimator.py` — Pipeline Orchestrator
*   **`estimate_food_mass(image_bgr, expected_items, plate_profile, debug=False)`**:
*   Creates a `RunContext` instance, passes it (`ctx=`) to every stage function.
*   Pipeline steps:
    1.  **Input Preservation**: Saves original image and metadata JSON.
    2.  **Preprocessing**: Calls `process_image(img, ctx=ctx)`.
    3.  **Compartment Detection**: Calls `find_compartments(img, ctx=ctx)` → `compute_scale` → `match_compartments_to_profile`.
    4.  **Depth Estimation**: Calls `estimate_depth` → `normalize_depth_to_plate` → `depth_to_cm`, all with `ctx=ctx`.
    5.  **Segmentation**: Calls `segment_full_image_sam(img, ctx=ctx)`.
    6.  **Volume & Mass**: Per-pixel height integration, compartment matching, density lookup, macro calculation.
*   **Always saves** (regardless of debug flag): original input, final annotated image (with food labels + grams overlay), `results.json`, `pipeline.log`, and the HTML report.
*   **Debug-only saves**: All preprocessing intermediates, depth `.npy` arrays, individual masks, per-item feature JSONs, height-map heatmaps.
*   **The Majority-Area Loop**: The most expensive computation — for every mask:
    1.  **Pixel Height Mapping**: `pixel_heights = height_from_divider[mask] + well_depth_map[mask]`.
    2.  **Majority-Choice Compartment Matching**: Assigns each food mask to the compartment it overlaps the most.
    3.  **Applies Density**: $Mass = Volume \times Density$ from `density_map.py`.
*   **Final Mass**: `Volume (ml) * Density (g/ml)`.
*   **Macros**: Multiplies mass by the `config/macro_map.py` lookup.
*   **Return**: Dict with `food_items`, `confidence`, and `_debug` metadata (run_id, run_dir, report path, pipeline_time_s).


---

## 📱 4. Frontend Deconstruction (`frontend/`)

### `contexts/AppContext.jsx` — Global State
*   **State Units**: `userProfile`, `todaysMenu`, `loading`.
*   **Sync Logic**: 
    - Read `localStorage` on mount (Zero-latency UI).
    - Fetch `/api/menu` to verify if the server version has updated (Consistency).
    - Merge server-side items into local menu state.

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

## 🧬 6. Internal Object Evolution (The "Dal" Life-Cycle)

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
*   **Git**: The `cv_service/outputs/` directory is in `.gitignore`.

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
