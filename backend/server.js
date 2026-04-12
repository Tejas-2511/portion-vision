const express = require("express");
const cors = require("cors");
const multer = require("multer");
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const FormData = require("form-data");
const Tesseract = require("tesseract.js");

const Database = require("./utils/db");
const { normalizeFoodName } = require("./utils/normalize");
const { fuzzyMatchFood, levenshteinDistance } = require("./utils/fuzzyMatch");
const { recommendPlate, getFallbackDetails } = require("./portion_recommender");

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

        // Complement with fuzzy search if needed
        if (results.length < 5) {
            const fuzzyResults = foods
                .filter(food => food.name && !results.some(r => r.name === food.name))
                .map(food => ({
                    food,
                    score: levenshteinDistance(normalizedQuery, normalizeFoodName(food.name))
                }))
                .filter(item => item.score <= 3)
                .sort((a, b) => a.score - b.score)
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

        // Sync with Food Database
        let foodDatabase = await Database.getFoods();
        const getCompareKey = (name) => (name || "").toLowerCase().replace(/[^a-z0-9]/g, '');

        const cleanedMenuItems = [];
        let addedCount = 0;

        console.log("🔍 Checking items against Food Database...");
        for (const itemName of menuItems) {
            const compareKey = getCompareKey(itemName);
            const existing = foodDatabase.find(f => getCompareKey(f.name) === compareKey);

            if (!existing) {
                console.log(`   ➕ ADDING NEW ITEM: "${itemName}" (Creating fallback nutrition)`);
                const fallback = getFallbackDetails(itemName);
                const newItem = {
                    id: itemName.toLowerCase().replace(/\s+/g, '_'),
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
                foodDatabase.push(newItem);
                addedCount++;
                cleanedMenuItems.push(itemName);
            } else {
                console.log(`   ✅ FOUND IN DB: "${existing.name}"`);
                cleanedMenuItems.push(existing.name);
            }
        }

        if (addedCount > 0) {
            console.log(`💾 Saved ${addedCount} new items to the Food Database.`);
            foodDatabase.sort((a, b) => a.name.localeCompare(b.name));
            await Database.saveFoods(foodDatabase);
        }

        const resultData = {
            date: new Date().toISOString(),
            items: cleanedMenuItems.sort(),
            text,
            confidence: Math.round(confidence)
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

app.post("/api/analyze-plate", upload.single("image"), async (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: "No image uploaded" });
    }

    const { expectedItems } = req.body;
    let originalPath = req.file.path;

    try {
        const form = new FormData();
        form.append("image", fs.createReadStream(originalPath));
        if (expectedItems) form.append("expected_items", expectedItems);

        const cvResponse = await axios.post("http://127.0.0.1:8000/estimate-portion", form, {
            headers: { ...form.getHeaders() },
            timeout: 300000
        });

        res.json(cvResponse.data);
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
});