const express = require("express");
const cors = require("cors");
const multer = require("multer");
const Tesseract = require("tesseract.js");
const fs = require("fs");
const sharp = require("sharp");
const path = require("path");

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

// Security: Simple rate limiting (Removed for development)
// Rate limiting logic was here

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
    .map(line => line.trim())
    .filter(line => line.length > 1)
    .map(line => {
      line = line.replace(/[^A-Za-z, &/]/g, "");
      line = line.replace(/\s+/g, " ").trim();

      let parts = [line];

      parts = parts
        .flatMap(x => x.split(","))
        .flatMap(x => x.split("/"))
        .flatMap(x => x.split("&"))
        .map(x => x.trim())
        .filter(x => x.length > 1);

      return parts;
    })
    .flat()
    .map(line => line.toLowerCase()) // Normalize to lowercase
    .filter(line => line.length > 1)
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
      console.log('📂 Food database not found, returning empty array');
      return res.json([]);
    }

    const data = fs.readFileSync(foodDbPath, 'utf8');
    const foods = JSON.parse(data);

    if (!Array.isArray(foods)) {
      console.error('⚠️ Food database is not an array');
      return res.json([]);
    }

    console.log(`✅ Retrieved ${foods.length} foods from database`);
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
    const query = req.query.q?.toLowerCase().trim();

    if (!query) {
      return res.status(400).json({
        error: 'Search query required',
        message: 'Please provide a search query using ?q=yourquery'
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

    // Search by name (case-insensitive, partial match)
    const results = foods.filter(food =>
      food.name && food.name.toLowerCase().includes(query)
    );

    console.log(`🔍 Search for "${query}" returned ${results.length} results`);
    res.json(results);
  } catch (err) {
    console.error('❌ Search failed:', err);
    res.status(500).json({
      error: 'Search failed',
      message: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
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
      date: new Date().toISOString().split("T")[0],
      menuItems,
    };

    // Ensure data directory exists
    const dataDir = './data';
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    fs.writeFileSync("./data/menu.json", JSON.stringify(data, null, 2));

    /*
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

    // Get existing food names (lowercase for comparison)
    const existingNames = new Set(
      foodDatabase
        .filter(item => item && item.name) // Filter out invalid items
        .map(item => item.name.toLowerCase())
    );

    console.log(`📋 Menu items to process: ${menuItems.join(', ')}`);

    // Add new items that don't exist yet
    let addedCount = 0;
    menuItems.forEach(itemName => {
      if (!existingNames.has(itemName)) {
        console.log(`➕ Adding new item: ${itemName}`);
        foodDatabase.push({
          name: itemName,
          category: "",
          serving_size: 0,
          serving_unit: "g/ml",
          calories: 0,
          protein: 0,
          carbs: 0,
          fat: 0,
          fiber: 0,
          veg: true
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
    */

    res.json({ menuItems });
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
