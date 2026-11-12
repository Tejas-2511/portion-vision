const express = require("express");
const cors = require("cors");
const multer = require("multer");
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const FormData = require("form-data");
const Tesseract = require("tesseract.js");
const crypto = require("crypto");

const Database = require("./utils/db");
const { normalizeFoodName } = require("./utils/normalize");
const { findBestFoodMatch, calculateSimilarity } = require("./utils/fuzzyMatch");
const { recommendPlate, getFallbackDetails } = require("./portion_recommender");

// ============================================================================
// BACKEND CONFIGURATION
// Whether OCR menu scans automatically insert unrecognized dishes into foodDatabase.json:
//   • true  -> Auto-save new dishes permanently to foodDatabase.json
//   • false -> Keep database read-only (uses fallback nutrition for unrecognized items)
// Change the boolean below to `true` or `false` whenever you want,
// or set the environment variable: ALLOW_OCR_DB_UPDATE=true|false
// ============================================================================
const CONFIG_ALLOW_OCR_DB_UPDATE = false; // <--- EDIT HERE: true or false

let globalAllowOcrDbUpdate = process.env.ALLOW_OCR_DB_UPDATE !== undefined
    ? process.env.ALLOW_OCR_DB_UPDATE === 'true'
    : CONFIG_ALLOW_OCR_DB_UPDATE;

const app = express();

// Security: CORS configuration
app.use(cors());

// Middleware
app.use(express.json({ limit: '10mb' }));

// Utility for path safety
const uploadsPath = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsPath)) {
    fs.mkdirSync(uploadsPath, { recursive: true });
}

// Security: File upload configuration with validation
const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, uploadsPath),
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, 'upload-' + uniqueSuffix + path.extname(file.originalname));
    }
});

const upload = multer({
    storage: storage,
    limits: {
        fileSize: 10 * 1024 * 1024, // 10MB
        files: 1
    },
    fileFilter: (req, file, cb) => {
        const allowedMimeTypes = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp'];
        if (allowedMimeTypes.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error('Invalid file type. Only JPEG, PNG, and WEBP images are allowed.'));
        }
    }
});

// Security: Basic security headers
app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    next();
});

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// Settings: OCR Database auto-update toggle
app.get('/api/settings/ocr-db-update', (req, res) => {
    res.json({
        allowOcrDbUpdate: globalAllowOcrDbUpdate,
        description: "Controls whether OCR menu scanning automatically saves unrecognized items to the permanent food database."
    });
});

app.post('/api/settings/ocr-db-update', (req, res) => {
    if (req.body && typeof req.body.enabled === 'boolean') {
        globalAllowOcrDbUpdate = req.body.enabled;
        console.log(`⚙️ Global OCR DB update setting changed to: ${globalAllowOcrDbUpdate}`);
        return res.json({ success: true, allowOcrDbUpdate: globalAllowOcrDbUpdate });
    }
    res.status(400).json({ error: "Missing or invalid boolean 'enabled' field in request body." });
});

// ============================================
// Food Database API Endpoints
// ============================================

app.get('/api/foods', async (req, res) => {
    try {
        const foods = await Database.getFoods();
        res.json(foods);
    } catch (err) {
        console.error('API Error (GET /api/foods):', err);
        res.status(500).json({ error: 'Failed to load food database' });
    }
});

app.get('/api/foods/search', async (req, res) => {
    try {
        const query = req.query.q;
        const normalizedQuery = normalizeFoodName(query);

        if (!normalizedQuery) {
            return res.status(400).json({ error: 'Search query required' });
        }

        const foods = await Database.getFoods();

        // Exact/Partial matches
        let results = foods.filter(food =>
            food.name && normalizeFoodName(food.name).includes(normalizedQuery)
        );

        // Complement with fuzzy search if needed using the unified fuzzy engine
        if (results.length < 5) {
            const fuzzyResults = foods
                .filter(food => food.name && !results.some(r => r.name === food.name))
                .map(food => ({
                    food,
                    similarity: calculateSimilarity(normalizedQuery, food.name)
                }))
                .filter(item => item.similarity >= 0.60)
                .sort((a, b) => b.similarity - a.similarity)
                .map(item => item.food);

            results = [...results, ...fuzzyResults].slice(0, 10);
        }
        res.json(results);
    } catch (err) {
        console.error('API Error (GET /api/foods/search):', err);
        res.status(500).json({ error: 'Search failed' });
    }
});

app.get('/api/menu', async (req, res) => {
    try {
        const menu = await Database.getMenu();
        res.json(menu);
    } catch (err) {
        console.error("API Error (GET /api/menu):", err);
        res.status(500).json({ error: "Failed to read menu" });
    }
});

app.post('/api/recommend', async (req, res) => {
    try {
        const { userProfile, mealType, menuItems: clientMenuItems } = req.body;

        if (!userProfile) {
            return res.status(400).json({ error: 'User profile is required' });
        }

        let menuItems = clientMenuItems || [];

        if (!menuItems.length) {
            const menuData = await Database.getMenu();
            if (menuData && Array.isArray(menuData.items)) {
                menuItems = menuData.items;
            }
        }

        if (!menuItems.length) {
            return res.json({ recommendedPlate: [], summary: { notes: "No menu available" } });
        }

        // Normalize user profile for the recommender
        const user = {
            weight_kg: parseFloat(userProfile.weight),
            height_cm: parseFloat(userProfile.height),
            age: parseInt(userProfile.age),
            sex: userProfile.gender,
            activity_level: (userProfile.activityLevel || 'moderate').toLowerCase().split(' ')[0],
            goalType: userProfile.goalType,
            proteinPct: userProfile.proteinPct,
            carbsPct: userProfile.carbsPct,
            fatPct: userProfile.fatPct,
            dietPreference: userProfile.dietPreference || 'non-veg',
            avoidTags: userProfile.avoidTags || []
        };
        console.log(`[DEBUG] Recommending for ${user.dietPreference} (${mealType})`);


        const recommendation = await recommendPlate({
            user,
            menuItems,
            mealType: mealType || 'lunch'
        });

        res.json(recommendation);
    } catch (err) {
        console.error('API Error (POST /api/recommend):', err);
        res.status(500).json({ error: 'Failed to generate recommendations' });
    }
});

// ============================================
// OCR Pipeline
// ============================================

const OCR_BLACKLIST = new Set([
    'menu', 'breakfast', 'lunch', 'dinner', 'snack', 'snacks',
    'today', 'date', 'day', 'monday', 'tuesday', 'wednesday',
    'thursday', 'friday', 'saturday', 'sunday',
    'mess', 'hostel', 'canteen', 'cafeteria',
    'special', 'note', 'notes', 'timings', 'timing',
    'price', 'rate', 'rupees', 'rs', 'amount', 'total',
    'veg', 'non-veg', 'nonveg', 'jain'
]);

function parseMenuText(rawText) {
    if (!rawText) return [];

    const lines = rawText.split(/[\n\t]/).map(l => l.trim()).filter(Boolean);
    const items = [];
    const seen = new Set();

    for (const line of lines) {
        let norm = line.toLowerCase()
            .replace(/[^a-z\s/,&\-]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();

        if (!norm || norm.length < 3) continue;

        const parts = norm.split(/[,/&|+]/).map(p => p.trim()).filter(p => p.length >= 3);

        for (const part of parts) {
            if (OCR_BLACKLIST.has(part)) continue;

            const words = part.split(' ');
            if (words.every(w => OCR_BLACKLIST.has(w))) continue;

            if (!seen.has(part)) {
                seen.add(part);
                items.push(part);
            }
        }
    }
    return items.sort();
}

app.post("/ocr", upload.single("image"), async (req, res) => {
    let originalPath = null;

    try {
        if (!req.file) {
            return res.status(400).json({ error: "No image uploaded" });
        }

        originalPath = req.file.path;
        console.log(`🔍 Running Tesseract OCR: ${req.file.originalname}`);

        const { data: { text, confidence } } = await Tesseract.recognize(originalPath, 'eng', {
            gzip: false,
            langPath: __dirname,
            logger: m => {
                if (m.status === 'recognizing text') {
                    if (Math.round(m.progress * 100) % 25 === 0) {
                        console.log(`📄 OCR Progress: ${Math.round(m.progress * 100)}%`);
                    }
                }
            }
        });

        const menuItems = parseMenuText(text);
        console.log(`📝 Parsed Items from OCR: [${menuItems.join(", ")}]`);

        // Check if database updating is enabled for this request:
        // 1. Explicit request body flag `updateDatabase` (boolean or 'true'/'false')
        // 2. Query param `update_db`
        // 3. Fallback to server setting `globalAllowOcrDbUpdate`
        let allowDbUpdate = globalAllowOcrDbUpdate;
        if (req.body && req.body.updateDatabase !== undefined) {
            allowDbUpdate = req.body.updateDatabase === true || req.body.updateDatabase === 'true' || req.body.updateDatabase === '1';
        } else if (req.query && req.query.update_db !== undefined) {
            allowDbUpdate = req.query.update_db === 'true' || req.query.update_db === '1';
        }

        console.log(`⚙️ OCR Database Update Mode: ${allowDbUpdate ? 'ENABLED (unrecognized items will be saved)' : 'DISABLED (database is read-only)'}`);

        // Sync with Food Database
        let foodDatabase = await Database.getFoods();
        const cleanedMenuItems = [];
        let addedCount = 0;
        let matchedCount = 0;

        console.log("🔍 Checking OCR items against Food Database with fuzzy matching...");
        for (const itemName of menuItems) {
            // 1. Try fuzzy match with similarity scoring & synonym expansion (e.g. roti/chapati, sambhar/sambar)
            const matchResult = findBestFoodMatch(itemName, foodDatabase, 0.65);

            if (matchResult && matchResult.food) {
                const existing = matchResult.food;
                matchedCount++;
                console.log(`   ✅ FUZZY MATCHED: "${itemName}" -> "${existing.name}" (confidence: ${(matchResult.score * 100).toFixed(0)}%, matchType: ${matchResult.type})`);
                cleanedMenuItems.push(existing.name);
            } else {
                console.log(`   ❓ NO MATCH FOUND FOR: "${itemName}" (generating fallback nutrition)`);
                const fallback = getFallbackDetails(itemName);
                const newItem = {
                    id: itemName.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '') || `item_${Date.now()}`,
                    name: itemName,
                    veg: fallback.veg !== undefined ? fallback.veg : true,
                    dish_type: fallback.dish_type || 'sabji',
                    category: fallback.category || 'side',
                    serving_size: fallback.serving_size || 100,
                    serving_unit: fallback.serving_unit || 'g',
                    unit_type: fallback.unit_type || 'bowl',
                    calories: fallback.calories || 0,
                    protein: fallback.protein || 0,
                    carbs: fallback.carbs || 0,
                    fat: fallback.fat || 0,
                    fiber: fallback.fiber || 0,
                    protein_level: fallback.protein_level || 'low',
                    meal_role: fallback.meal_role || 'single',
                    tags: fallback.tags || []
                };

                cleanedMenuItems.push(itemName);

                if (allowDbUpdate) {
                    console.log(`   ➕ ADDING NEW ITEM TO DB: "${itemName}"`);
                    foodDatabase.push(newItem);
                    addedCount++;
                } else {
                    console.log(`   🛡️ DB UPDATE OFF: "${itemName}" will use fallback nutrition for this session without saving to database.`);
                }
            }
        }

        if (allowDbUpdate && addedCount > 0) {
            console.log(`💾 Saved ${addedCount} new items to the Food Database.`);
            foodDatabase.sort((a, b) => a.name.localeCompare(b.name));
            await Database.saveFoods(foodDatabase);
        }

        const resultData = {
            date: new Date().toISOString(),
            items: cleanedMenuItems.sort(),
            text,
            confidence: Math.round(confidence),
            dbUpdateEnabled: allowDbUpdate,
            dbUpdated: allowDbUpdate && addedCount > 0,
            addedCount: allowDbUpdate ? addedCount : 0,
            matchedCount: matchedCount
        };

        await Database.saveMenu(resultData);
        res.json(resultData);

    } catch (err) {
        console.error('OCR ERROR:', err);
        res.status(500).json({ error: 'OCR processing failed' });
    } finally {
        if (originalPath && fs.existsSync(originalPath)) {
            try { fs.unlinkSync(originalPath); } catch (e) { console.error('Cleanup failed:', e); }
        }
    }
});

// ============================================
// Plate Analysis Integration
// ============================================

let activeCvPromise = null;
let activeCvKey = null;
const cvResultCache = new Map(); // reqKey -> { data, timestamp }

app.post("/api/analyze-plate", upload.single("image"), async (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: "No image uploaded" });
    }

    const { expectedItems, plateProfile, mealType } = req.body;
    const requestedProfile = plateProfile || req.body.plate_profile || '';
    const requestedMeal = mealType || req.body.meal_type || '';
    let originalPath = req.file.path;

    try {
        const fileBuffer = fs.readFileSync(originalPath);
        const hash = crypto.createHash('sha256').update(fileBuffer).digest('hex');
        const reqKey = `${hash}_${expectedItems || ''}_${requestedProfile}_${requestedMeal}`;

        // 1. If we already computed results for this image within the last 15 minutes, return immediately
        const cached = cvResultCache.get(reqKey);
        if (cached && (Date.now() - cached.timestamp < 15 * 60 * 1000)) {
            console.log(`[analyze-plate] Found cached CV analysis for image ${hash.slice(0, 8)}. Returning immediately (0ms).`);
            return res.json(cached.data);
        }

        // 2. If an estimation for this exact image is currently running, wait for it instead of starting another
        if (activeCvPromise && activeCvKey === reqKey) {
            console.log(`[analyze-plate] Concurrent duplicate request detected for hash ${hash.slice(0, 8)}. Awaiting active CV estimation.`);
            const sharedData = await activeCvPromise;
            return res.json(sharedData);
        }

        // Always merge client-provided items with the current menu so the CV
        // service knows exactly which foods to constrain classification to.
        const clientItems = expectedItems
            ? expectedItems.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
            : [];

        let menuItems = [];
        const shouldIgnoreMenu = req.body.ignoreMenu === 'true' || req.body.ignoreMenu === true ||
            req.body.openVocabulary === 'true' || req.body.openVocabulary === true;

        if (!shouldIgnoreMenu) {
            try {
                const menuData = await Database.getMenu();
                if (menuData && Array.isArray(menuData.items)) {
                    menuItems = menuData.items.map(s => s.trim().toLowerCase()).filter(Boolean);
                }
            } catch (menuErr) {
                console.warn('[analyze-plate] Could not load menu for CV constraint:', menuErr.message);
            }
        }

        // Union of menu items and any recommendation items sent by the client
        const mergedSet = new Set([...menuItems, ...clientItems]);
        const mergedItems = [...mergedSet].filter(Boolean);
        console.log(`[analyze-plate] CV expected_items: [${mergedItems.join(', ')}], meal: '${requestedMeal || 'auto'}', profile: '${requestedProfile || 'default'}'`);

        const form = new FormData();
        form.append("image", fs.createReadStream(originalPath));
        if (mergedItems.length > 0) {
            form.append("expected_items", mergedItems.join(','));
        }
        if (requestedProfile) {
            form.append("plate_profile", requestedProfile);
        }
        if (requestedMeal) {
            form.append("meal_type", requestedMeal);
        }
        form.append("debug", "true");

        activeCvKey = reqKey;
        activeCvPromise = axios.post("http://127.0.0.1:8000/estimate-portion", form, {
            headers: { ...form.getHeaders() },
            timeout: 300000
        }).then(r => {
            const data = r.data;
            cvResultCache.set(reqKey, { data, timestamp: Date.now() });
            return data;
        }).finally(() => {
            if (activeCvKey === reqKey) {
                activeCvPromise = null;
                activeCvKey = null;
            }
        });

        const cvData = await activeCvPromise;
        res.json(cvData);
    } catch (err) {
        if (err.code === 'ECONNREFUSED') {
            res.status(503).json({
                error: "CV service is offline",
                isOffline: true
            });
        } else if (err.response) {
            // Forward the exact error from CV Service if available (e.g. 422 Quality Gate)
            console.error('CV API Error:', err.response.data);
            res.status(err.response.status).json(err.response.data);
        } else {
            console.error('CV Error (Other):', err.code, err.message);
            res.status(500).json({ error: "Portion analysis failed: " + err.message });
        }
    } finally {
        if (originalPath && fs.existsSync(originalPath)) {
            try { fs.unlinkSync(originalPath); } catch (e) { console.error("Cleanup failed:", e); }
        }
    }
});

// Global error handling
app.use((err, req, res, next) => {
    if (err instanceof multer.MulterError) {
        return res.status(400).json({ error: err.message });
    }
    console.error("Unhandled error:", err);
    res.status(500).json({ error: 'Internal server error' });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Backend running on http://localhost:${PORT}`);
    console.log(`⚙️ OCR Database Auto-Update: ${globalAllowOcrDbUpdate ? 'ENABLED (auto-saves dishes)' : 'DISABLED (read-only)'}`);
});