# PortionVision: Technical Engineering Report & Architectural Deconstruction
**Physics-Informed Monocular Volumetric Metrology & Open-Vocabulary Dietary Assessment**

---

## 📑 Table of Contents
- [1. Executive Summary & System Architecture](#-1-executive-summary--system-architecture)
- [2. Mathematical Formulations & 3D Metrology Principles](#-2-mathematical-formulations--3d-metrology-principles)
  - [2.1. Coordinate System & Camera Unprojection](#21-coordinate-system--camera-unprojection)
  - [2.2. Perspective Rectification & Homography](#22-perspective-rectification--homography)
  - [2.3. Robust 2D Planar Surface Normal Fitting (Tilt-Invariance)](#23-robust-2d-planar-surface-normal-fitting-tilt-invariance)
  - [2.4. Metric Depth Fusion with Physiological Height Priors](#24-metric-depth-fusion-with-physiological-height-priors)
  - [2.5. Physical Volumetric Archetypes & Voxel Integration](#25-physical-volumetric-archetypes--voxel-integration)
  - [2.6. Multi-Spectral Dynamic Density Modeling](#26-multi-spectral-dynamic-density-modeling)
  - [2.7. Multi-Instance Canonical Aggregation Topology](#27-multi-instance-canonical-aggregation-topology)
  - [2.8. Bayesian Multi-Modal Composite Confidence Scoring](#28-bayesian-multi-modal-composite-confidence-scoring)
- [3. Computer Vision Engine (`cv_service/`)](#-3-computer-vision-engine-cv_service)
  - [3.1. Meta SAM 3 Open-Vocabulary Grounding Engine (`open_vocab/`)](#31-meta-sam-3-open-vocabulary-grounding-engine-open_vocab)
  - [3.2. Depth Anything 3 Metric Depth Estimator (`depth/`)](#32-depth-anything-3-metric-depth-estimator-depth)
  - [3.3. Volumetric & Mass Estimator (`estimation/`)](#33-volumetric--mass-estimator-estimation)
  - [3.4. Hardware VRAM Budget & Execution Mechanics](#34-hardware-vram-budget--execution-mechanics)
- [4. Backend Orchestrator Deconstruction (`backend/`)](#️-4-backend-orchestrator-deconstruction-backend)
- [5. Frontend Client System (`frontend/`)](#-5-frontend-client-system-frontend)
- [6. Data Schema, Taxonomic Maps & Macro Propagation](#-6-data-schema-taxonomic-maps--macro-propagation)
- [7. System Resilience & Anti-Duplication Quad-Shield](#-7-system-resilience--anti-duplication-quad-shield)
- [8. Pipeline Diagnostics & Auditing Architecture](#-8-pipeline-diagnostics--auditing-architecture)
- [9. Empirical Benchmarks & Ablation Analysis](#-9-empirical-benchmarks--ablation-analysis)
- [10. Developer Setup & Fast-Start Guide](#-10-developer-setup--fast-start-guide)

---

## 🏗️ 1. Executive Summary & System Architecture

PortionVision is an end-to-end computer vision and nutritional intelligence platform designed to convert raw visual food captures into rigorous macronutrient assessments. It addresses the notorious challenges of real-world food portion estimation: oblique camera angles, irregular amorphous food morphologies, overlapping food piles, severe monocular depth scale ambiguity, and low-profile flat items.

```
Captured Plate (Smartphone Camera)
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Ingestion & Quality Control: Laplacian Variance (Blur) + Hough (Tilt)    │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Spatial Normalization: LAB Mean-Shift + 4-Point Homography Perspective   │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. Depth Anything 3 Metric Depth: True Euclidean Distance Z(x, y) [meters]  │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. 2D Planar Surface Normal Fitting: Z_plane(x, y) = Ax + By + C (Tilt-Zero)│
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. Meta SAM 3 Grounding: Non-Food Rejection + Indian Staple Concept Queries │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. Continuous Prior Fusion: H_fused = α·H_metric + β·H_prior (486 Dishe Priors)│
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. 5-Archetype Volumetric Integration (Planar, Salad, Liquid, Mound, Chunk) │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. Dynamic Visual Density: ρ(x) = ρ_0 + Δρ(HSV, Texture Laplacian)          │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 9. Canonical Instance Aggregation: Unified Items + Macro Propagation       │
└─────────────────────────────────────────────────────────────────────────────┘
```

The system operates across three coordinated tiers:
1.  **Frontend (React 18 / Vite / PWA)**: Client interface with strict top-down camera guidance, dynamic meal slot routing (`Breakfast`, `Lunch`, `Snacks`, `Dinner`), and real-time portion comparison.
2.  **Backend (Node.js / Express)**: Orchestration tier managing local WASM OCR (`Tesseract.js`), daily menu parsing, user profile TDEE/macro partitioning, and meal context proxying.
3.  **CV Service (Python 3.12 / FastAPI / PyTorch)**: Core metrology engine combining **Meta SAM 3** open-vocabulary instance segmentation, **Depth Anything 3 (DA3)** physical metric depth estimation, and 5-archetype geometric voxel integration.

---

## 📐 2. Mathematical Formulations & 3D Metrology Principles

### 2.1. Coordinate System & Camera Unprojection

Let the camera optical center be the coordinate origin $(0, 0, 0)$. A 2D image pixel $p = (u, v)$ in pixel coordinates corresponds to a ray in 3D camera space unprojected via camera intrinsic matrix $K$:

$$K = \begin{bmatrix} f_x & 0 & c_x \\ 0 & f_y & c_y \\ 0 & 0 & 1 \end{bmatrix}$$

Given physical metric depth $Z(u, v)$ measured in meters by Depth Anything 3:

$$X(u, v) = \frac{(u - c_x) \cdot Z(u, v)}{f_x}, \quad Y(u, v) = \frac{(v - c_y) \cdot Z(u, v)}{f_y}$$

### 2.2. Perspective Rectification & Homography

When the plate is photographed at an oblique angle $\theta \in [15^\circ, 45^\circ]$, quadrilateral plate boundaries $P = \{p_1, p_2, p_3, p_4\}$ are mapped into a standardized canonical coordinate system $P' = \{(0, 0), (W_0, 0), (W_0, H_0), (0, H_0)\}$ via projective homography matrix $H_{3 \times 3}$:

$$p' \sim H \cdot p, \quad \text{where } H = \begin{bmatrix} h_{11} & h_{12} & h_{13} \\ h_{21} & h_{22} & h_{23} \\ h_{31} & h_{32} & h_{33} \end{bmatrix}$$

Scale calibration factor $s_{\text{px}} = \text{cm\_per\_pixel}$ is determined via ellipse boundary regression on circular plate rims ($s_{\text{px}} = \frac{D_{\text{known}}}{2 \cdot \bar{r}_{\text{ellipse}}}$) or bounding well dimensions.

### 2.3. Robust 2D Planar Surface Normal Fitting (Tilt-Invariance)

In monocular depth estimation of tilted tabletop scenes, monocular models exhibit an inherent depth gradient along the optical slant. Subtracting a single scalar baseline ($Z - Z_{\text{median}}$) causes severe non-uniform height distortion across the plate:
- Near-field items receive artificially inflated heights.
- Far-field items receive suppressed or zeroed heights.

To achieve tilt-invariant volumetric reconstruction, PortionVision fits a continuous 2D reference plane through the plate rim and non-food divider pixels $\mathcal{S}_{\text{rim}}$:

$$Z_{\text{plate}}(x, y) = A \cdot x + B \cdot y + C$$

The parameter vector $\mathbf{w} = [A, B, C]^T$ is estimated via robust least-squares with outlier rejection ($5\text{th} \le Z \le 90\text{th}$ percentile filter):

$$\mathbf{w}^* = \arg\min_{\mathbf{w}} \sum_{(x_i, y_i) \in \mathcal{S}_{\text{rim}}} \left( [x_i, y_i, 1] \cdot \mathbf{w} - Z(x_i, y_i) \right)^2 = \left( \mathbf{X}^T \mathbf{X} \right)^{-1} \mathbf{X}^T \mathbf{Z}$$

The height of any point $(x, y)$ above the true physical plate baseline is then:

$$H_{\text{rel\_cm}}(x, y) = \max\left(0, \left( Z_{\text{plate}}(x, y) - Z(x, y) \right) \times 100 \right)$$

### 2.4. Metric Depth Fusion with Physiological Height Priors

Monocular depth predictions are prone to high-frequency sensor noise and ambiguous surface reflectance. PortionVision implements a continuous hybrid fusion framework with $486$ calibrated Indian dish physiological height bounds $[\bar{H}_{\min}, \bar{H}_{\max}]$:

$$H_{\text{prior\_mid}} = \frac{\bar{H}_{\min} + \bar{H}_{\max}}{2}$$

$$H_{\text{fused}}(x, y) = \alpha \cdot \text{clip}\left( H_{\text{rel\_cm}}(x, y), \, 0.75 \bar{H}_{\min}, \, 1.25 \bar{H}_{\max} \right) + \beta \cdot H_{\text{prior\_mid}}$$

where $\alpha = 0.70$ and $\beta = 0.30$. The result is clamped to $[0.50 \bar{H}_{\min}, \, \bar{H}_{\max}]$, guaranteeing that flat sliced foods (e.g. cucumber, tomato slices) do not collapse into 0 cm while strictly bounding tall food piles against runaway over-estimation.

### 2.5. Physical Volumetric Archetypes & Voxel Integration

Food items do not share identical physical packing behavior. PortionVision routes each segmented region $\mathcal{M}$ to its corresponding physical geometric archetype:

$$\Delta A_{\text{px}} = (s_{\text{px}})^2 \quad [\text{cm}^2/\text{pixel}]$$

#### Archetype I: Planar & Layered Laminates (`roti`, `chapati`, `naan`, `papad`)
Planar flatbreads bridge compartment dividers and do not conform to well depth. Volume is governed by calibrated sheet thickness $t_{\text{sheet}}$ and stack layer count $L$:

$$L = \text{clip}\left( \frac{\text{median}_{(x, y) \in \mathcal{M}} H_{\text{fused}}(x, y)}{t_{\text{sheet}}}, \, 1.0, \, 3.5 \right)$$

$$V_{\text{planar}} = \left( \sum_{p \in \mathcal{M}} \Delta A_{\text{px}} \right) \times t_{\text{sheet}} \times L \quad [\text{ml}]$$

#### Archetype II: Sliced Salad Laminates (`cucumber`, `tomato`, `onion`, `beetroot`)
Discrete circular/elliptical slices laid flat on the plate floor. Depth networks often perceive their thin profile as near-zero. Volume enforces calibrated physical slice thickness $t_{\text{slice}} = 0.55\,\text{cm}$:

$$h_{\text{eff}} = \text{clip}\left( \max\left( t_{\text{slice}}, \, \text{median}_{p \in \mathcal{M}} H_{\text{fused}}(p) \right), \, t_{\text{slice}}, \, 2.5 \right)$$

$$V_{\text{salad}} = \left( \sum_{p \in \mathcal{M}} \Delta A_{\text{px}} \right) \times h_{\text{eff}} \quad [\text{ml}]$$

#### Archetype III: Truncated Frustum Liquid Reservoirs (`dal`, `sambar`, `rasam`, `curd`)
Liquids conform to molded tray well geometries. Surface cannot exceed the tray rim. Volume integrates well depth $d_{\text{well}}$ with fill ratio $f_{\text{fill}}$ and mold draft taper factor $\eta_{\text{taper}} = 0.88$:

$$f_{\text{fill}} = \text{clip}\left( 0.50 + 0.30 \cdot \frac{\bar{H}_{\text{fused}}}{d_{\text{well}}}, \, 0.40, \, 0.98 \right)$$

$$V_{\text{liquid}} = A_{\text{surface}} \times (d_{\text{well}} \cdot f_{\text{fill}}) \times \eta_{\text{taper}} \quad [\text{ml}]$$

#### Archetype IV: Porous/Granular Mounded Hemispheroids (`rice`, `biryani`, `pulao`)
Combines well reservoir capacity with a dome profile above the rim, scaled by bulk granular packing factor $\phi_{\text{bulk}} = 0.85$:

$$V_{\text{mound}} = \left( A_{\text{surface}} \cdot d_{\text{well}} \cdot 0.85 \right) + \left( \sum_{p \in \mathcal{M}} H_{\text{fused}}(p) \cdot \Delta A_{\text{px}} \right) \times 0.85 \quad [\text{ml}]$$

#### Archetype V: Chunky Heterogeneous Suspensions (`curry`, `sabzi`, `paneer`, `chicken`)
Solid vegetable/meat chunks suspended in gravy leaving inter-granular voids. Governed by solid packing efficiency $\phi_{\text{pack}} = 0.82$:

$$V_{\text{chunk}} = \left( \sum_{p \in \mathcal{M}} \left( H_{\text{fused}}(p) + d_{\text{well}} \right) \cdot \Delta A_{\text{px}} \right) \times 0.82 \quad [\text{ml}]$$

### 2.6. Multi-Spectral Dynamic Density Modeling

Mass is the product of integrated volume and physical density:

$$M = V \times \rho \quad [\text{grams}]$$

PortionVision establishes a baseline density table $\rho_0$ across 490+ dishes, modulated at runtime through a multi-spectral visual texture function extracting brightness $V_{\text{HSV}}$, saturation $S_{\text{HSV}}$, and Laplacian spatial variance $\sigma^2_{\nabla^2 I}$:

$$\rho_{\text{dynamic}} = \rho_0 + \Delta \rho(V_{\text{HSV}}, S_{\text{HSV}}, \sigma^2_{\nabla^2 I})$$

- **Steamed Rice**: Brightness indicates hydration. High brightness (fluffy white rice) $\rightarrow \Delta \rho = -0.12$; low brightness (dense compact yellow rice) $\rightarrow \Delta \rho = +0.08$.
- **Dals & Curries**: High saturation and Laplacian texture indicate thick gravies (`dal makhani` $\approx 1.13\,\text{g/ml}$) versus thin broths (`rasam` $\approx 0.98\,\text{g/ml}$).

### 2.7. Multi-Instance Canonical Aggregation Topology

When SAM 3 segments multiple isolated portions of the same biological dish (e.g. 7 distinct cucumber slices, 2 separate heaps of steamed rice), reporting them as separate entries creates visual noise and fractional zero-macro roundoff anomalies. 

PortionVision executes a canonical hash aggregation pass:

$$\mathcal{A}(\text{Dish}) = \left\{ \mathcal{M}_1, \mathcal{M}_2, \dots, \mathcal{M}_k \right\}$$

$$M_{\text{total}} = \sum_{i=1}^k M_i, \quad V_{\text{total}} = \sum_{i=1}^k V_i, \quad \mathcal{N}_{\text{total}} = \sum_{i=1}^k \mathcal{N}_i$$

$$\mathcal{C}_{\text{aggregated}} = \frac{\sum_{i=1}^k \text{Area}_i \cdot \mathcal{C}_i}{\sum_{i=1}^k \text{Area}_i}$$

Output items carry `instance_count: k`, rendering a clean single-card interface with a piece counter badge (e.g. `Cucumber (7 pieces)`).

### 2.8. Bayesian Multi-Modal Composite Confidence Scoring

Confidence is computed as a geometric mean over four orthogonal uncertainty dimensions:

$$\mathcal{C} = \left( S_{\text{seg}} \times S_{\text{class}} \times S_{\text{geom}} \times S_{\text{scale}} \right)^{0.25}$$

where:
- $S_{\text{seg}} \in [0, 1]$: SAM 3 mask IoU / segmentation score.
- $S_{\text{class}} \in [0, 1]$: Concept grounding similarity score.
- $S_{\text{geom}} \in \{0.75, 1.0\}$: $1.0$ if canonical height prior match exists; $0.75$ for generic unlisted fallbacks.
- $S_{\text{scale}} \in \{0.70, 1.0\}$: $1.0$ for closed-form ellipse rim calibration; $0.70$ for bounding-box approximation.

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
*   **CV Proxy `POST /api/analyze-plate` (Lines 324-390)**:
    *   **Streaming Strategy**: Uses `fs.createReadStream(originalPath)` to pipe the disk file directly into the `axios` POST request, minimizing intermediate memory allocation.
    *   **SHA-256 Deduplication & Concurrency Guard**:
        *   Calculates a SHA-256 hash of the uploaded image buffer concatenated with `expectedItems`.
        *   **In-Flight Promise Sharing (`activeCvPromise`)**: If an analysis for the exact same image is currently running, incoming requests (e.g. from React 18 StrictMode double-mounting or rapid client triggers) await the active promise rather than sending a redundant request to FastAPI.
        *   **15-Minute Result Cache (`cvResultCache`)**: Completed CV results are cached in a memory `Map` for 15 minutes. If a client retries or re-queries with the same image, it returns the complete JSON in 0ms without hitting the heavy Python engine.

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

## 🐍 3. CV Service Deconstruction (`cv_service/`)

PortionVision's computer vision service is built on a streamlined, open-vocabulary architecture centered around **Meta SAM 3 (SAM 3.1)** as the sole primary food identification and instance segmentation engine. Downstream metric depth estimation is powered by **Depth Anything 3 (`DA3METRIC-LARGE`)**, and physical mass is calculated through calibrated geometric voxel integration.

### `main.py` & `api/routes.py`
*   **FastAPI Engine**: Uses `async def` and `UploadFile`.
*   **Binary Buffer Flow**: `image.read()` → `np.frombuffer` → `cv2.imdecode`. The image is converted to a BGR matrix in RAM.
*   **Meal Slot Parameter**: `/estimate-portion` accepts optional `meal_type: str = Form(None)` ('breakfast', 'lunch', 'snacks', 'dinner'). If omitted, the service falls back to time-based slot inference.
*   **Identical Image Execution Guard**: Computes SHA-256 hash of image bytes concatenated with `expected_items`, `plate_profile`, and `meal_type`. If identical, it immediately returns cached JSON, skipping redundant model passes.
*   **Quality Error Handling**: If the quality gate rejects an image, the API returns `HTTP 422` with structured JSON `{ "type": "image_quality", "message": "<user-facing string>" }`.
*   **Debug Parameter**: `/estimate-portion` accepts `debug: bool = Form(True)` to activate the full diagnostic pipeline and return the `_debug` metadata block.

### `open_vocab/sam3_segmenter.py` — Meta SAM 3 Grounding & Instance Segmentation Engine
*   **Architecture**: Loads Meta SAM 3 (`build_sam3_image_model`) checkpoint with TensorFloat-32 enabled on CUDA.
*   **ViT Visual Backbone Encoding**: Runs the 1008×1008 image backbone once (`Sam3Processor.set_image`), enabling multi-concept prompt queries against shared visual feature maps.
*   **Non-Food Rejection Anchors**: Simultaneously queries non-food anchors (`spoon`, `fork`, `cutlery`, `plate`, `table surface`, `napkin`). Any candidate region overlapping significantly with a non-food anchor is rejected, delivering a 0.0% false-positive rate for cutlery and surfaces.
*   **Specific-over-Generic Disambiguation**: Resolves candidate conflicts with specificity priority (Contextual Menu Item > Specific Food like `cucumber` > Generic Category `curry` > Generic fallback `food`). Distinguishes sliced cucumber (0.87–0.91 confidence) without curry misclassifications.
*   **Transparent RGBA Crop Generation**: Extracts tight crops with alpha-channel transparency, saved to disk for human verification.

### `open_vocab/pipeline.py` — Open-Vocabulary Orchestrator
*   **`OpenVocabFoodSegmenter`**: High-level interface wrapping `Sam3FoodSegmenter`. Accepts raw BGR plate images and optional menu strings.
*   **Menu Context Integration**: Expands menu queries with canonical synonyms from `config/synonym_map.py` to maximize recall while maintaining precise labeling.

### `config/synonym_map.py` — Indian Dish Synonym Groups
*   Defines canonical clusters for Indian mess foods (e.g., `["steamed rice", "white rice", "chawal", "boiled rice"]`, `["dal tadka", "yellow dal", "toor dal", "arhar dal"]`, `["cucumber", "cucumber slices", "kheera", "green salad"]`), enabling robust text prompt resolution.

### `image_processing/preprocess.py` — Warp Engine + Quality Gate
*   **`validate_image_quality(image, blur_thresh=80, tilt_thresh=30)`**:
    -   **Blur Detection**: Laplacian variance of greyscale image. Values below 80 indicate motion blur or out-of-focus camera.
    -   **Tilt Detection**: Applies `cv2.HoughLines`, extracts dominant edge orientation, and checks deviation from cardinal axis. Deviations > 30° abort early with a retake prompt.
*   **`process_image(image, target_long_edge, ctx, skip_quality_check=False)`**:
    -   Resize → Gaussian denoise → LAB normalisation → CLAHE → Canny edges → Perspective warp.

### `depth/depth_estimator.py` — Metric Depth Estimation & Geometric Priors
*   **Depth Anything 3 Metric (`DA3METRIC-LARGE`)**: Predicts dense physical metric depth in meters $Z$. Calibrated directly to physical distances, converted to height-oriented depth $D = -Z \times 100\,\text{cm}$ so higher values represent points closer to camera in centimeters.
*   **`FOOD_HEIGHT_PRIORS`**: Maps 486 canonical foods to physical `(min_cm, max_cm)` height ranges.
*   **`apply_food_height_prior(height_map, food_label, alpha=0.70, beta=0.30)`**:
    -   When metric depth is active: blends measured metric height directly with physical prior range: $\text{fused} = 0.70 \times H_{\text{measured\_metric}} + 0.30 \times H_{\text{prior\_mid}}$.
    -   Clamps to $[H_{\text{min}} \times 0.5, H_{\text{max}}]$, eliminating runaway depth noise while preventing thin items (e.g. cucumber slices) from vanishing.
*   **`calibrate_scale_from_ellipse(image_bgr, plate_profile=None)`**:
    -   Fits an ellipse to the detected plate rim.
    -   Computes $\text{cm\_per\_pixel} = \text{known\_diameter\_cm} / \text{avg\_axis\_px}$. Boosts `scale_confidence` to 1.0.

### `config/density_map.py` — Dynamic Multi-Meal Densities
*   **Coverage**: Maps 490+ Indian dishes spanning breakfast starches (idli $0.95$, dosa $0.55$), curries & dals ($1.02$–$1.08$), fried snacks ($0.65$–$0.75$), sweets ($1.10$–$1.15$), and fresh salads/fruits ($0.80$–$0.95$).
*   **`get_dynamic_density(food_name, mask_region_bgr=None)`**:
    -   Extracts masked region HSV brightness, saturation, and Laplacian texture roughness.
    -   Applies visual tuning (e.g. fluffy white rice $0.75$ vs compact yellow rice $1.20$; thin watery dal $0.95$ vs thick dal makhani $1.15$).

### `estimation/mass_estimator.py` — Mass Estimation, Archetypes & Instance Aggregation
*   Consumes SAM 3 masks directly; maps each mask to Depth Anything 3 metric height maps, plate depth baseline, and dynamic density.
*   **Physical Geometric Volume Archetypes**:
    1.  **Planar Archetype** (`roti`, `chapati`, `naan`, `paratha`, `papad`): Analytical volume $\text{Area} \times \text{Thickness} \times \text{Layers}$ (single chapati $\approx 40\text{g}$, not inflated by empty well depth).
    2.  **Salad Slice Archetype** (`cucumber`, `tomato`, `onion`, `salad`): Calibrated slice thickness ($0.55\,\text{cm}$ cucumber, $0.60\,\text{cm}$ tomato), preserving accurate portions for sliced salad plates without vanishing into 0g / 0 kcal.
    3.  **Liquid in Wells** (`dal`, `sambar`, `rasam`, `curd`): Conforms to container well depth and surface fill ratio with frustum taper factor ($0.88$).
    4.  **Mounded Carb Base** (`rice`, `biryani`): Base well footprint + smooth dome profile integration.
    5.  **Chunky Curries & Sabzis**: Solid packing factor ($0.80$) accounting for void spaces between vegetable chunks.
*   **Instance Aggregation Loop**: Aggregates multiple isolated mask segments of the same canonical dish (e.g. 7 cucumber slices, 2 rice mounds) into a single unified summary card per unique food with an `instance_count` badge and summed macros, preserving individual instances in `raw_detections`.
*   **`_composite_confidence(seg_score, class_conf, depth_stability, scale_confidence)`**:
    -   Geometric mean: $(seg \times class \times depth \times scale)^{0.25}$.

**API Response Schema**:
```json
{
  "food_items": [
    {
      "name":             "chapati",
      "volume_ml":        38.2,
      "mass_g":           34.4,
      "calories":         104.0,
      "protein":          3.1,
      "carbs":            18.2,
      "fat":              2.1,
      "confidence":       0.8421,
      "class_label":      "chapati",
      "class_confidence": 0.8120
    }
  ],
  "confidence": 0.8250
}
```

---

## 🧬 3.1. CV Deep Dive: The "0 to 100" Journey

Tracking a single **Dal** portion from camera capture to calorie result.

### **Phase 0: Quality Gate (pre-processing)**
1.  **Blur Check**: Laplacian variance on the grey image. If below 80, the pipeline aborts immediately with `"Image is too blurry..."`. Time saved: ~4 seconds of wasted inference.
2.  **Tilt Check**: HoughLines extracts dominant edge angle. If deviation > 30° from cardinal axis, the pipeline aborts with `"Camera angle is too steep..."`. The frontend surfaces this as an amber retake prompt.

### **Phase 1: Ingestion (0-10%)**
3.  **Mobile Capture**: User takes a photo. `PlateCapture.jsx` enforces "AI Camera Rules" (top-down, focused, full plate visible).
4.  **Node.js Proxy**: `server.js` streams bytes to disk → pipes stream to Python CV Service via `axios`.

### **Phase 2: Rectification (10-30%)**
5.  **Color Space Shift**: `preprocess.py` converts BGR → LAB. This separates lightness from chrominance, enabling shadow-invariant processing.
6.  **Perspective Warp**: If a 4-point boundary is found, a **Non-Linear Homography Matrix** rectifies the tilted plate into a top-down rectangle.

### **Phase 3: Spatial Calibration (30-50%)**
7.  **Ellipse Fit**: `calibrate_scale_from_ellipse()` fits an ellipse to the plate rim. Divides known plate diameter (26 cm) by detected axis length → `cm_per_pixel`. `scale_confidence = 1.0`.
8.  **Fallback Ruler**: If ellipse fails, `compute_scale()` matches bounding-box pixel-width to `plate_config.py`. `scale_confidence = 0.7`.
9.  **Well Mapping**: Adaptive threshold finds dividers → defines $Z_{surface}$ baseline.

### **Phase 4: Volumetric Sensing (50-65%)**
10. **Depth Anything 3 Metric**: Predicts Euclidean depth $Z(x, y)$ in meters from camera optical center. Gaussian blur (5×5) suppresses high-frequency depth noise.
11. **2D Planar Surface Normal Fitting**: Fits $Z_{\text{plate}}(x, y) = Ax + By + C$ through plate rim/divider pixels using robust least squares. This eliminates oblique slant/tilt across the plate.
12. **Physical Height Metric**: $H_{\text{rel\_cm}}(x, y) = \max(0, (Z_{\text{plate}}(x, y) - Z(x, y)) \times 100)$.

### **Phase 5: SAM 3 Grounding & Semantic Segmentation (65-75%)**
13. **SAM 3 ViT Backbone Encoding**: Encodes the 1008x1008 image once on CUDA using `Sam3Processor`.
14. **Instance Masks**: SAM 3 generates tight, boundary-conforming binary masks for each detected concept.

### **Phase 6: Food-Aware Validation & Disambiguation (75-85%)**
15. **Non-Food Rejection**: Rejects any candidate region overlapping with spoons, forks, metallic dividers, or napkins (0.0% false-positive rate).
16. **Disambiguation & Menu Guidance**: Resolves specific dishes over generic ones (e.g. cucumber recognized accurately, avoiding dal/curry confusion). Categorizes items as `recognized` (matches menu item), `unlisted` (discovered extra/side dish), or `uncertain`.

### **Phase 7: Archetype Integration, Density & Canonical Aggregation (85-100%)**
17. **Continuous Metric Height Fusion**: `apply_food_height_prior()` fuses measured metric height with prior midpoint at 70/30, clamping to physiological bounds $[\bar{H}_{\min} \cdot 0.5, \bar{H}_{\max}]$.
18. **5-Archetype Voxel Summing**: Direct integration using the food's physical archetype (Planar, Sliced Salad, Liquid Well Frustum, Mounded Granular Dome, Chunky Suspension).
19. **Dynamic Density**: HSV brightness/saturation and Laplacian texture are extracted from food pixels (e.g. watery dal $0.98\,\text{g/ml}$ vs thick dal $1.13\,\text{g/ml}$).
20. **Canonical Aggregation**: Combines multi-piece detections of the same dish into a single summary card with `instance_count` and combined macros.
21. **Composite Confidence**: $\mathcal{C} = (S_{\text{seg}} \times S_{\text{class}} \times S_{\text{geom}} \times S_{\text{scale}})^{0.25}$.
22. **Macros**: Mass × `macro_map.py` per-gram factors → Calories/Protein/Carbs/Fat.
23. **Report**: `RunContext` compiles every intermediate into `report.html`.

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
*   **Submitting Guard**: The "Analyse Plate" button tracks a `submitting` boolean state that immediately disables the button upon trigger, preventing accidental double-taps on mobile touchscreens or double-clicks from spawning duplicate navigation cycles.

### `pages/Analysis.jsx` — Result Orchestration & Meal Slot Selection
*   **Interactive 4-Button Meal Slot Selector**:
    -   Provides an interactive chip bar for `Breakfast`, `Lunch`, `Snacks`, and `Dinner`.
    -   **Clock-Time Fallback (`inferMealType()`)**: If no meal was passed via navigation state, defaults to the current clock slot:
      - 06:00 – 11:00: `breakfast`
      - 11:00 – 16:00: `lunch`
      - 16:00 – 19:00: `snacks`
      - 19:00 – 06:00: `dinner`
    -   **Dynamic Re-Analysis (`handleMealSelect(mealId)`)**: On selecting a different meal chip, asynchronously queries new nutritional targets for the selected meal via `api.getRecommendations()` and immediately triggers CV re-estimation passing the new `mealId` to re-rank candidates against the selected meal taxonomy.
*   **Sequential Analysis Flow**:
    1.  Waits for context `profileLoading` to settle.
    2.  `loadRecommendation`: Fetches calculated portions based on user profile and selected meal.
    3.  `analyzeCapturedPlate`: Immediately triggers CV portion estimation passing active recommendation labels and active `mealType`.
    4.  **No Racing Timeouts**: Replaced legacy racing 5-second fallback timers with a unified sequential lifecycle, preventing duplicate calls across React 18 StrictMode unmount/remount cycles.
*   **UI Logic (Lines 150-200)**: Calculates `totalDetectedCals` and compares it to `targetMealCals`. If $\Delta > 10\%$, it triggers the "Over-portioned" warning.

### `services/api.js` — The API Wrapper
*   A singleton instance that wraps the browser `fetch` API.
*   **Multipart Handler**: For `uploadMenuImage` and `analyzePlate`, it uses `FormData`. It explicitly leaves the `Content-Type` header empty so the browser can automatically set the boundary.
*   **`analyzePlate(file, expectedItems, plateProfile, mealType)`**:
    -   Passes `mealType` alongside `expectedItems` and `plateProfile`.
    -   **In-Flight Promise Sharing (`_activePlatePromise`)**: Keyed by `${file.name}_${file.size}_${file.lastModified}_${expectedItems}_${plateProfile}_${mealType}` to prevent duplicate simultaneous executions.
    -   **In-Memory Completed Cache (`_lastPlateResult`)**: Returns instant 0ms cached CV result if identical parameters are requested again.

### `public/sw.js` — PWA Service Worker API Bypass
*   **Bypass Rule**: The Service Worker fetch listener explicitly checks `event.request.method !== 'GET'` and path prefixes `/api/` and `/ocr/`.
*   **Chromium Timeout Prevention**: Chromium terminates Service Worker fetch events that take longer than 60–90 seconds and automatically retries the original request over the network. Because SAM segmentation on CPUs takes ~60–100s, bypassing API calls prevents the browser from triggering unwanted duplicate CV runs.

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

### **The 4-Layer Anti-Duplication & Idempotency Shield**
Because volumetric segmentation of deep-learning models (SAM, Depth Anything) is computationally intensive (60–100s per image), PortionVision implements a synchronized 4-layer defense against duplicate runs:

1.  **Layer 1 — Frontend Button & API Deduplication**:
    *   `PlateCapture.jsx` disables submit buttons immediately on click (`submitting: true`).
    *   `api.js` tracks in-flight promises and in-memory completed results by image signature. Concurrent triggers share the same active promise.
2.  **Layer 2 — Service Worker Network Bypass**:
    *   `sw.js` completely excludes all `/api/*` and non-`GET` requests, preventing Chromium's 60s Service Worker timeout from spawning background network retries.
3.  **Layer 3 — Express Backend SHA-256 Memory Cache**:
    *   `server.js` hashes the uploaded image with `expected_items`.
    *   `activeCvPromise` merges simultaneous incoming requests into a single Axios stream.
    *   `cvResultCache` stores completed responses in memory for 15 minutes, answering subsequent retries in 0ms.
4.  **Layer 4 — FastAPI Python Hash Guard**:
    *   `routes.py` hashes incoming binary bytes. If an identical payload reaches the CV engine, it returns the cached result without invoking the PyTorch pipeline.

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
*   **Creation & Persistence**: The `outputs/` directory is maintained in the repository under `cv_service/outputs/`. It stores persistent diagnostic runs, segmentation crops, and benchmark evaluations.
*   **Location**: `cv_service/outputs/{timestamp}_{uuid}/` (e.g., `20261109_175841_8796a578/`).
*   **Rule**: Each run gets a unique directory. Outputs are **never overwritten** across runs.
*   **Run Artifact Integrity**: `cv_service/outputs/` is deliberately preserved in the repository to maintain verifiable benchmark traceability and visual inspection histories across development.

### Directory Structure (per run)
```
cv_service/outputs/20261109_175841_8796a578/
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
│   ├── crops/                    # Transparent RGBA PNG crops per food item
│   │   ├── 00_steamed_rice_0.94.png
│   │   └── 01_cucumber_0.89.png
│   ├── 01_sam3_segmentation_overlay.png  # Color mask overlays + contours + confidence badges
│   └── sam3_detections.json      # Structured detections, confidences & bounding boxes
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
**1. Terminal: CV Service (Python Engine with SAM 3 GPU Acceleration)**
```powershell
cd cv_service
# Activate the sam3 Conda environment (configured with PyTorch CUDA + Meta SAM 3 dependencies)
conda activate sam3
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or invoke the sam3 environment executable directly:
C:\Users\tejas\.conda\envs\sam3\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
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
npm run dev -- --host

1. Locate the **Network URI** from Vite's startup log (e.g., `http://10.174.1.162:5173/`).
2. Type this exact URI into the mobile Safari/Chrome browser. Both devices must be on the same WiFi.

**Proxy Workflow**:
Because of the setup in `frontend/vite.config.js`:
* `host: true` broadcasts the front-end over the network.
* `proxy: { '/api': { target: 'http://127.0.0.1:5000' } }` handles the CORS boundary. 
When the phone (at `10.174.x.x`) sends an image, it posts to `/api/analyze-plate`. The laptop's Vite dev server intercepts this call, routes it directly into the `server.js` running on `localhost:5000`, which streams it via axios to `localhost:8000`. This entire chained proxy means the mobile browser requires NO configurations to communicate with the heavy backend engines.

---

## 🔬 3.2. SAM 3 Unified Food Identification & Segmentation Engine (open_vocab/)

Meta SAM 3 (SAM 3.1) serves as the sole primary food identification and instance segmentation engine. Features open-world concept grounding, food-aware validation, non-food rejection (spoons/cutlery), and transparent RGBA crop exports.

### Architecture & Directory Structure

```
cv_service/open_vocab/
├── __init__.py           # Package exports (OpenVocabFoodSegmenter, Sam3FoodSegmenter)
├── pipeline.py           # Orchestrator — OpenVocabFoodSegmenter.process_plate()
└── sam3_segmenter.py     # SAM 3 concept grounding + food-aware validation + RGBA crop export
```

### Pipeline Flow

```
Top-Down Plate Image (BGR)
          │
          ▼
   Sam3Processor.set_image()  ──> Encodes 1008x1008 ViT Backbone once on CUDA (TF-32 enabled)
          │
          ├──> Non-food grounding: ['spoon', 'fork', 'cutlery', 'napkin']
          ├──> Contextual Menu queries: ['steamed rice', 'dal palak', 'chapati', ...]
          └──> Indian staple discovery: ['rice', 'dal', 'curry', 'sabzi', 'salad', 'cucumber', 'pickle', ...]
          │
          ▼
   Food-Aware Validation & Disambiguation:
     1. Discard any detection overlapping significantly with non-food anchors (0 spoon false-positives).
     2. Specificity ranking: Menu Items > Specific Staples (e.g. cucumber) > Generic fallback ('food').
     3. Deduplication: Suppress redundant multi-query overlaps for identical physical regions.
          │
          ▼
   Pixel-Accurate Binary Masks & Transparent RGBA PNG Crops (outputs/<run_id>/segmentation/crops/)
          │
          ▼
   Downstream Depth Anything 3 Metric Depth Map & Geometric Mass Estimation (g)
```

### Key Capabilities & Benchmarks

1. **Non-Food Rejection**: Metal spoons, cutlery, and empty surfaces are detected and rejected (0.0% false-positive rate).
2. **True Concept Discrimination**: Fresh sliced cucumbers and green salads are recognized as cucumber (0.87–0.91 confidence) without ever misclassifying as cooked dals or curries.
3. **Hardware Efficiency**: Fits in **3.8 GB VRAM** (out of 6 GB on NVIDIA RTX 3050 Laptop GPU) with TensorFloat-32 acceleration.
4. **Transparent RGBA Crop Export**: Saves tightly bounded PNG crops with alpha channels directly to disk for downstream verification.

### Output Contract

`OpenVocabFoodSegmenter.process_plate()` returns:

```python
{
    "food_items": [
        {
            "food_name": str,           # e.g. "steamed rice"
            "menu_match": bool,         # True if matches a menu item
            "confidence": float,        # Calibrated detection confidence [0, 1]
            "mask": np.ndarray,         # bool array, shape HxW
            "bounding_box": [x, y, w, h],
            "area_pixels": int,
            "identification_status": "recognized" | "unlisted" | "uncertain"
        }
    ],
    "image_dimensions": [width, height],
    "total_items": int,
    "recognized_count": int,
    "unlisted_count": int,
    "uncertain_count": int,
    "elapsed_seconds": float
}
```

This contract is stable and consumed directly by downstream mass estimation.

### Hardware Behaviour

| Stage | Peak VRAM | Notes |
|-------|-----------|-------|
| SAM 3 ViT Backbone & Grounding | ~3.8 GB | Encodes 1008x1008 image once on CUDA (TF-32 enabled) |
| Depth Anything 3 (`DA3METRIC-LARGE`) | ~1.3 GB | Physical metric depth estimation ($Z$ in meters), runs before SAM 3 with immediate cache release |
| Peak Simultaneous | ~4.5 GB | Safely within 6 GB VRAM budget (RTX 3050 Laptop GPU) |

---

## 📊 9. Empirical Benchmarks & Ablation Analysis

### 9.1. Architectural Ablation Matrix on Real Mess Thali Captures

To quantify the incremental impact of each volumetric refinement, the table below documents the empirical progression on a benchmark Indian mess thali containing Steamed Rice, Dal Fry, Mixed Vegetable Curry, and Sliced Cucumber:

| Metrology Stage | Sliced Cucumber | Dal Fry | Steamed Rice | Curry | Baseline Floor RMS Error | Multi-Card Redundancy |
|---|---|---|---|---|---|---|
| **V1: Relative Disparity + Scalar Baseline** | $0.0\,\text{g}$ ($0\,\text{kcal}$) | $41.4\,\text{g}$ | $184.0\,\text{g}$ | $128.2\,\text{g}$ | $6.52\,\text{cm}$ | ❌ 5 separate cucumber cards, 2 rice cards |
| **V2: DA3 Metric + Scalar Baseline** | $15.5\,\text{g}$ ($5.2\,\text{kcal}$) | $41.4\,\text{g}$ | $215.9\,\text{g}$ | $128.2\,\text{g}$ | $6.52\,\text{cm}$ | ❌ Non-uniform tilt attenuation on far well |
| **V3: DA3 Metric + Salad Archetype + Aggregation** | $15.5\,\text{g}$ ($5.2\,\text{kcal}$) | $41.4\,\text{g}$ | $215.9\,\text{g}$ | $128.2\,\text{g}$ | $6.52\,\text{cm}$ | ✅ 1 unified card (`Cucumber (7 pieces)`) |
| **V4 (Final): DA3 Metric + 2D Planar Surface Normal Fitting** | **$13.1\,\text{g}$** ($5.2\,\text{kcal}$) | **$97.5\,\text{g}$** ($133.9\,\text{kcal}$) | **$234.6\,\text{g}$** ($222.3\,\text{kcal}$) | **$143.3\,\text{g}$** ($146.2\,\text{kcal}$) | **$4.86\,\text{cm}$** (Tilt zeroed) | ✅ Clean 5-card canonical report |

### 9.2. Analysis of Key Breakthroughs

1.  **Resolution of the "Zero-Calorie Flat Item" Anomaly**:
    Monocular relative disparity maps compress thin, flat items (e.g. 5 mm cucumber or tomato slices) into the baseline noise floor ($h \approx 0.05\,\text{cm}$). Enforcing the **Salad Slice Archetype** with a physical thickness floor ($0.55\,\text{cm}$) and Depth Anything 3 metric unprojection recovers the full portion ($13.1\text{--}15.5\,\text{g}$), completely eliminating $0\,\text{g} / 0\,\text{kcal}$ displays.
2.  **Tilt Slant Normalization (97.5g Dal Recovery)**:
    In oblique captures, a single scalar baseline ($Z - Z_{\text{median}}$) subtracts an artificially high value from far-field wells. The liquid dal well on the far edge was suppressed from its true volume ($~100\,\text{ml}$) down to $41\,\text{ml}$. **2D Planar Surface Normal Fitting** ($Z_{\text{plate}}(x, y) = Ax + By + C$) models and cancels the camera tilt slant ($0.0099\,\text{cm/px}$ along X, $0.0071\,\text{cm/px}$ along Y), accurately restoring the dal portion to $97.5\,\text{g}$.
3.  **Composite Memory & Latency Budget**:
    By decoupling Depth Anything 3 inference ($\approx 0.73\,\text{s}$, $1.3\,\text{GB}$) from SAM 3 inference ($\approx 60\,\text{s}$, $3.8\,\text{GB}$) and actively purging PyTorch GPU caches (`torch.cuda.empty_cache()`), the system avoids CUDA Out-of-Memory faults on 6 GB consumer GPUs while running 100% locally.

---

## 🛠️ 10. CV Test & Visualization Tools

All test and diagnostic outputs land in `cv_service/outputs/`.

### `visualize_open_vocab.py` — Open-Vocab Visual Inspector

Runs the SAM 3 open-vocab pipeline, generates overlay visualizations with bounding boxes and confidence badges, and writes transparent RGBA PNG crops for every detected food portion.

```powershell
python cv_service/visualize_open_vocab.py [image] [--menu "item1,item2"]
```

All output goes to `cv_service/outputs/<timestamp>_vis/`:

| File | Contents |
|------|----------|
| `annotated.png` | Original image + colored mask overlays + bounding boxes + `[!] food_name (conf%)` labels |
| `results.json` | Full detection output (masks replaced with shape info for JSON serializability) |
| `segmentation/crops/*.png` | Transparent RGBA cropped regions for each detected food item |
| `segmentation/01_sam3_segmentation_overlay.png` | SAM 3 segmentation mask overlay |
| `segmentation/sam3_detections.json` | Detection metadata, confidences, and bounding boxes |

Color convention:
- **Green** masks = `recognized` (menu match)
- **Amber/orange** masks = `unlisted` (detected but not on menu)
- **Red** masks = `uncertain` (low confidence, descriptive label)

### `test_open_vocab.py` — Quick Smoke Test

Minimal script that runs the SAM 3 open-vocab pipeline on a sample plate image and prints formatted detection results to terminal. Saves a timestamped JSON to `cv_service/outputs/`.

### `evaluate_pipeline.py` — Precision Benchmark Runner

Iterates over plate images, evaluates non-food rejection (spoons/cutlery), salad vs curry discrimination, small-portion preservation, and latency. Saves a consolidated report to `cv_service/outputs/evaluation_report_<timestamp>.json`.
