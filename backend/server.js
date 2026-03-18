const express = require("express");
const cors = require("cors");
const multer = require("multer");
const Tesseract = require("tesseract.js");
const fs = require("fs");
const sharp = require("sharp");
const path = require("path");
const { normalizeFoodName } = require("./utils/normalize");
const { fuzzyMatchFood, levenshteinDistance } = require("./utils/fuzzyMatch");
const { getFallbackDetails } = require("./portion_recommender");

const app = express();

// Security: CORS configuration - Allow all origins for development
app.use(cors());

app.use(express.json({ limit: '10mb' })); // Limit JSON payload size

// Security: File upload configuration with validation
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    const uploadDir = 'uploads/';
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: function (req, file, cb) {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, 'upload-' + uniqueSuffix + path.extname(file.originalname));
  }
});

const upload = multer({
  storage: storage,
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB max file size
    files: 1 // Only 1 file per request
  },
  fileFilter: function (req, file, cb) {
    // Accept only image files
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
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// Clean and parse OCR text to extract individual menu items
// Removes common headers, noise, and short strings
// Uses regex to split lines by commas, slashes, and ampersands
function cleanMenuItems(rawText) {
  const blacklist = ["menu", "breakfast", "lunch", "dinner"];

  return rawText
    .split("\n")
    .flatMap(line => line.split(","))
    .flatMap(line => line.split("/"))
    .flatMap(line => line.split("&"))
    .map(normalizeFoodName) // Use shared normalization
    .filter(line => line.length > 2) // Filter very short garbage
    .filter(line => !blacklist.some(word => line.includes(word)))
    .filter((item, index, self) => self.indexOf(item) === index)
    .sort(); // Sort alphabetically
}

// ============================================
// Food Database API Endpoints
// ============================================

// GET /api/foods - Retrieve all foods from database
app.get('/api/foods', (req, res) => {
  try {
    const foodDbPath = './data/foodDatabase.json';

    if (!fs.existsSync(foodDbPath)) {
      // console.log('📂 Food database not found, returning empty array');
      return res.json([]);
    }

    const data = fs.readFileSync(foodDbPath, 'utf8');
    const foods = JSON.parse(data);

    if (!Array.isArray(foods)) {
      console.error('⚠️ Food database is not an array');
      return res.json([]);
    }

    // console.log(`✅ Retrieved ${foods.length} foods from database`);
    res.json(foods);
  } catch (err) {
    console.error('❌ Error reading food database:', err);
    res.status(500).json({
      error: 'Failed to load food database',
      message: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
  }
});

// GET /api/foods/search?q=query - Search foods by name
app.get('/api/foods/search', (req, res) => {
  try {
    const normalizedQuery = normalizeFoodName(req.query.q);

    if (!normalizedQuery) {
      return res.status(400).json({
        error: 'Search query required',
        message: 'Please provide a valid search query'
      });
    }

    const foodDbPath = './data/foodDatabase.json';

    if (!fs.existsSync(foodDbPath)) {
      return res.json([]);
    }

    const data = fs.readFileSync(foodDbPath, 'utf8');
    const foods = JSON.parse(data);

    if (!Array.isArray(foods)) {
      return res.json([]);
    }



    // First, try exact/partial substring match
    let results = foods.filter(food =>
      food.name && normalizeFoodName(food.name).includes(normalizedQuery)
    );

    // If few results, complement with fuzzy search
    if (results.length < 5) {
      const fuzzyResults = foods
        .filter(food => food.name && !results.some(r => r.name === food.name))
        .map(food => ({
          food,
          score: levenshteinDistance(normalizedQuery, normalizeFoodName(food.name))
        }))
        .filter(item => item.score <= 3) // threshold
        .sort((a, b) => a.score - b.score)
        .map(item => item.food);

      results = [...results, ...fuzzyResults].slice(0, 10);
    }
    res.json(results);
  } catch (err) {
    console.error('❌ Search failed:', err);
    res.status(500).json({
      error: 'Search failed',
      message: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
  }
});

// GET /api/menu - Get current menu
app.get('/api/menu', (req, res) => {
  try {
    const menuPath = './data/menu.json';
    if (fs.existsSync(menuPath)) {
      const menu = JSON.parse(fs.readFileSync(menuPath, 'utf8'));
      const items = Array.isArray(menu.items)
        ? menu.items
        : Array.isArray(menu.menuItems)
          ? menu.menuItems
          : [];

      res.json({
        ...menu,
        // Frontend expects `items`; keep `menuItems` for backward compatibility
        items,
        menuItems: items,
      });
    } else {
      res.json(null);
    }
  } catch (err) {
    console.error("Error reading menu:", err);
    res.status(500).json({ error: "Failed to read menu" });
  }
});



// POST /api/recommend - Generate portion recommendations
// POST /api/recommend - Generate balanced plate recommendation
app.post('/api/recommend', (req, res) => {
  // console.log("Recommend endpoint hit. Body keys:", Object.keys(req.body));
  try {
    const { userProfile, mealType, menuItems: clientMenuItems } = req.body;

    if (!userProfile) {
      return res.status(400).json({ error: 'User profile is required' });
    }

    let menuItems = clientMenuItems || [];

    // Fallback if client didn't send items
    if (!menuItems.length) {
      const menuPath = './data/menu.json';
      if (fs.existsSync(menuPath)) {
        try {
          const menuData = JSON.parse(fs.readFileSync(menuPath, 'utf8'));
          if (Array.isArray(menuData.items) && menuData.items.length) {
            menuItems = menuData.items;
          } else if (Array.isArray(menuData.menuItems) && menuData.menuItems.length) {
            menuItems = menuData.menuItems;
          }
        } catch (e) {
          console.error("Error reading menu.json fallback:", e);
        }
      }
    }

    if (!menuItems.length) {
      return res.json({ recommendedPlate: [], summary: { notes: "No menu available" } });
    }

    // Reconstruct user object from frontend profile, including diet preference
    const user = {
      weight_kg: parseFloat(userProfile.weight),
      height_cm: parseFloat(userProfile.height),
      age: parseInt(userProfile.age),
      sex: userProfile.gender,
      activity_level: (userProfile.activityLevel || 'moderate').toLowerCase().split(' ')[0],
      goal: (userProfile.goalType || 'maintain').toLowerCase(),
      goalType: userProfile.goalType,
      dietPreference: userProfile.dietPreference || 'non-veg',
      avoidTags: userProfile.avoidTags || []
    };

    const { recommendPlate } = require("./portion_recommender");

    const recommendation = recommendPlate({
      user,
      menuItems,
      mealType: mealType || 'lunch'
    });

    // console.log(`🥗 Generated plate for ${user.sex}, ${user.goal} (${mealType})`);
    res.json(recommendation);

  } catch (err) {
    console.error('❌ Recommendation failed:', err);
    res.status(500).json({ error: 'Failed to generate recommendations' });
  }
});

// ============================================
// OCR Endpoint
// ============================================

app.post("/ocr", upload.single("image"), async (req, res) => {
  let originalPath = null;
  let processedPath = null;

  try {
    if (!req.file) {
      return res.status(400).json({ error: "No image uploaded" });
    }

    originalPath = req.file.path;
    processedPath = `uploads/processed-${Date.now()}.png`;

    // Image processing with security considerations
    // 1. Extend canvas to add white border (helps OCR with edge text)
    // 2. Resize to width 1200px (optimal for Tesseract)
    // 3. Convert to grayscale (removes color noise)
    // 4. Normalize and threshold (binarization for high contrast)
    // 5. Sharpen (enhances text edges)
    await sharp(originalPath)
      .extend({
        top: 40,
        bottom: 20,
        left: 20,
        right: 20,
        background: { r: 255, g: 255, b: 255 }
      })
      .resize({ width: 1200 })
      .grayscale()
      .normalize()
      .threshold(160)
      .sharpen()
      .toFile(processedPath);

    const result = await Tesseract.recognize(processedPath, "eng", {
      tessedit_pageseg_mode: 6,
    });

    const rawText = result.data.text;
    const menuItems = cleanMenuItems(rawText);

    const data = {
      date: new Date().toISOString(),
      items: menuItems,
      menuItems,
    };

    // Ensure data directory exists
    const dataDir = './data';
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    fs.writeFileSync("./data/menu.json", JSON.stringify(data, null, 2));


    // Update foodDatabase.json with new items
    const foodDbPath = './data/foodDatabase.json';
    let foodDatabase = [];

    console.log('📊 Updating food database...');

    // Load existing database
    if (fs.existsSync(foodDbPath)) {
      try {
        const existingData = fs.readFileSync(foodDbPath, 'utf8');
        foodDatabase = JSON.parse(existingData);
        // Handle if it's an object instead of array
        if (!Array.isArray(foodDatabase)) {
          console.log('⚠️ Database was not an array, resetting...');
          foodDatabase = [];
        } else {
          console.log(`✅ Loaded ${foodDatabase.length} existing items`);
        }
      } catch (e) {
        console.error("❌ Error reading foodDatabase.json, creating new:", e);
        foodDatabase = [];
      }
    } else {
      console.log('📝 No existing database found, creating new one');
    }

    // Get existing food names (normalized for consistent comparison)
    const existingNames = new Set(
      foodDatabase
        .filter(item => item && item.name) // Filter out invalid items
        .map(item => normalizeFoodName(item.name))
    );

    console.log(`📋 Menu items to process: ${menuItems.join(', ')}`);

    // Add new items that don't exist yet — enrich with fallback details so
    // they have realistic macro estimates and can be used by the recommender
    let addedCount = 0;
    menuItems.forEach(itemName => {
      if (!existingNames.has(itemName)) {
        console.log(`➕ Adding new item with fallback enrichment: ${itemName}`);
        const fallback = getFallbackDetails(itemName);
        foodDatabase.push({
          id: itemName.toLowerCase().replace(/\s+/g, '_'),
          name: itemName,
          diet: fallback.veg !== undefined ? (fallback.veg ? "veg" : "non-veg") : "veg",
          dishType: fallback.dish_type || "",
          category: fallback.category || "",
          serving: {
            size: fallback.serving_size || 100,
            unit: fallback.serving_unit || "g",
            unitType: fallback.unit_type || "serving"
          },
          nutrition: {
            calories: fallback.calories || 0,
            protein: fallback.protein || 0,
            carbs: fallback.carbs || 0,
            fat: fallback.fat || 0,
            fiber: fallback.fiber || 0
          },
          proteinLevel: fallback.protein_level || "low",
          mealRole: fallback.meal_role || "single",
          tags: fallback.tags || [],
          _enrichedByFallback: true // flag for future manual review
        });
        existingNames.add(itemName);
        addedCount++;
      } else {
        console.log(`⏭️ Skipping existing item: ${itemName}`);
      }
    });

    console.log(`✨ Added ${addedCount} new items to database`);

    // Sort database alphabetically by name
    foodDatabase.sort((a, b) => a.name.localeCompare(b.name));

    // Save updated database
    fs.writeFileSync(foodDbPath, JSON.stringify(foodDatabase, null, 2));
    console.log(`💾 Saved database with ${foodDatabase.length} total items`);


    res.json(data);
  } catch (err) {
    console.error("OCR ERROR:", err);
    res.status(500).json({
      error: "OCR processing failed",
      message: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
  } finally {
    // Always cleanup temp files
    if (originalPath && fs.existsSync(originalPath)) {
      try {
        fs.unlinkSync(originalPath);
      } catch (e) {
        console.error("Failed to delete original file:", e);
      }
    }
    if (processedPath && fs.existsSync(processedPath)) {
      try {
        fs.unlinkSync(processedPath);
      } catch (e) {
        console.error("Failed to delete processed file:", e);
      }
    }
  }
});

// ============================================
// Plate Analysis Endpoint (Integration w/ CV)
// ============================================

const axios = require("axios");
const FormData = require("form-data");

app.post("/api/analyze-plate", upload.single("image"), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: "No image uploaded" });
  }

  const { expectedItems } = req.body; // e.g., "rice, dal, roti, sabzi"
  let originalPath = req.file.path;

  try {
    // 1. Prepare form data to send to Python microservice
    const form = new FormData();
    form.append("image", fs.createReadStream(originalPath));
    if (expectedItems) {
      form.append("expected_items", expectedItems);
    }

    // 2. Call the CV microservice
    // console.log("Calling CV service with expected items:", expectedItems);
    const cvResponse = await axios.post("http://127.0.0.1:8000/estimate-portion", form, {
      headers: { ...form.getHeaders() },
      timeout: 10000 // 10 second timeout
    });

    // 3. Return the portion estimates to frontend
    res.json(cvResponse.data);

  } catch (err) {
    if (err.code === 'ECONNREFUSED') {
      res.status(503).json({
        error: "CV service is currently offline. Please ensure the Python service is running on port 8000.",
        isOffline: true
      });
    } else {
      res.status(500).json({
        error: "Portion analysis failed",
        message: process.env.NODE_ENV === 'development' ? err.message : undefined
      });
    }
  } finally {
    // Cleanup the uploaded temp file
    if (originalPath && fs.existsSync(originalPath)) {
      try {
        fs.unlinkSync(originalPath);
      } catch (e) {
        console.error("Failed to delete original file:", e);
      }
    }
  }
});

// Global error handling middleware
app.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    if (err.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({ error: 'File too large. Maximum size is 10MB.' });
    }
    if (err.code === 'LIMIT_FILE_COUNT') {
      return res.status(400).json({ error: 'Too many files. Only 1 file allowed.' });
    }
    return res.status(400).json({ error: err.message });
  }

  if (err.message === 'Not allowed by CORS') {
    return res.status(403).json({ error: 'CORS policy: Origin not allowed' });
  }

  if (err.message && err.message.includes('Invalid file type')) {
    return res.status(400).json({ error: err.message });
  }

  console.error("Unhandled error:", err);
  res.status(500).json({ error: 'Internal server error' });
});

const PORT = process.env.PORT || 5000;
const HOST = process.env.HOST || '0.0.0.0';

app.listen(PORT, HOST, () => {
  console.log(`Backend running on http://${HOST}:${PORT}`);
  console.log('CORS: All origins allowed');
});
