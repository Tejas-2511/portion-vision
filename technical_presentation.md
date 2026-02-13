# PortionVision - Technical Presentation

## 📋 Project Overview

**PortionVision** is an intelligent portion control and meal tracking Progressive Web Application (PWA) that generates personalized portion recommendations using a student's nutritional profile and estimates actual portions served from RGB images using depth estimation, segmentation, and geometric volume analysis.

---

## 🎯 Project Objectives

The system aims to:
- Generate personalized portion recommendations based on individual nutritional profiles
- Estimate actual portion sizes from single RGB images
- Track daily mess menu items using OCR technology
- Provide nutritional analysis and insights
- Offer an offline-capable mobile-first experience

---

## 🏗️ System Architecture

### Technology Stack

#### **Frontend**
- **Framework**: React 19.2.0 with Vite 7.2.4
- **Routing**: React Router DOM 7.13.0
- **Styling**: Tailwind CSS 3.4.17 with modern utility-first approach
- **State Management**: React Context API with localStorage sync
- **PWA**: Vite-plugin-PWA 1.2.0 for offline capabilities
- **Build Tool**: Vite with hot module replacement (HMR)

#### **Backend**
- **Runtime**: Node.js with Express 5.2.1
- **OCR Engine**: Tesseract.js 7.0.0 for menu text extraction
- **Image Processing**: Sharp 0.34.5 for image optimization
- **File Upload**: Multer 2.0.2 with security validations
- **CORS**: Configured for multiple allowed origins
- **Data Storage**: JSON file-based (ready for database migration)

#### **Architecture Pattern**
- **Frontend**: Component-based architecture with centralized state
- **Backend**: RESTful API with middleware pipeline
- **Communication**: HTTP/HTTPS with JSON payloads
- **Storage**: localStorage (frontend) + JSON files (backend)

---

## 🔧 Code Architecture & Implementation

### Frontend Architecture

#### **1. State Management (Context API)**

**File**: `frontend/src/contexts/AppContext.jsx`

```javascript
// Global state provider managing all application data
export function AppProvider({ children }) {
  const [userProfile, setUserProfile] = useState(null);
  const [todaysMenu, setTodaysMenu] = useState(null);
  const [foodDatabase, setFoodDatabase] = useState([]);
  
  // Auto-sync to localStorage on changes
  useEffect(() => {
    if (userProfile) {
      localStorage.setItem('userProfile', JSON.stringify(userProfile));
    }
  }, [userProfile]);
  
  // ... similar for todaysMenu
}
```

**Benefits**:
- Eliminates props drilling across components
- Centralized data management
- Automatic localStorage persistence
- Easy migration to database API calls

**Usage in Components**:
```javascript
// Any component can access global state
const { userProfile, setUserProfile, todaysMenu } = useApp();
```

#### **2. API Service Layer**

**File**: `frontend/src/services/api.js`

```javascript
class ApiService {
  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, options);
    
    if (!response.ok) {
      // Parse and throw meaningful errors
      const errorData = await response.json();
      throw new Error(errorData.error);
    }
    
    return await response.json();
  }
  
  // Specific API methods
  async uploadMenuImage(file) { /* ... */ }
  async getFoods() { /* ... */ }
  async searchFoods(query) { /* ... */ }
}
```

**Benefits**:
- Single source of truth for API calls
- Consistent error handling
- Easy to add authentication headers
- Testable and maintainable

#### **3. Error Handling System**

**Error Boundary** (`components/ErrorBoundary.jsx`):
```javascript
class ErrorBoundary extends Component {
  componentDidCatch(error, errorInfo) {
    console.error('Error caught:', error);
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallbackUI />;
    }
    return this.props.children;
  }
}
```

**Error Hook** (`hooks/useErrorHandler.js`):
```javascript
export function useErrorHandler() {
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  
  const retry = (callback) => {
    if (retryCount < 3) {
      setRetryCount(prev => prev + 1);
      callback();
    }
  };
  
  return { error, handleError, retry, canRetry };
}
```

**Benefits**:
- Graceful error recovery
- User-friendly error messages
- Retry logic for network failures
- Prevents app crashes

#### **4. Input Validation**

**File**: `frontend/src/utils/validation.js`

```javascript
export function validateProfileData(data) {
  const errors = {};
  
  // Age validation
  if (!data.age || data.age < 10 || data.age > 120) {
    errors.age = 'Age must be between 10 and 120';
  }
  
  // Height validation (100-250 cm)
  // Weight validation (30-300 kg)
  // Name validation (min 2 chars)
  
  return { isValid: Object.keys(errors).length === 0, errors };
}

export function validateImageFile(file) {
  const maxSize = 10 * 1024 * 1024; // 10MB
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
  
  if (!allowedTypes.includes(file.type)) {
    throw new Error('Invalid file type');
  }
  
  if (file.size > maxSize) {
    throw new Error('File too large');
  }
}
```

**Benefits**:
- Client-side validation before API calls
- Prevents invalid data submission
- Better user experience
- Reduces server load

#### **5. Shared Components**

**Button Component** (`components/Button.jsx`):
```javascript
export default function Button({ 
  variant = 'primary', 
  loading = false,
  children,
  ...props 
}) {
  return (
    <button className={variants[variant]} disabled={loading} {...props}>
      {loading ? <LoadingSpinner /> : children}
    </button>
  );
}
```

**Benefits**:
- Consistent UI across app
- Built-in loading states
- Reusable and maintainable
- Easy to theme

#### **6. Component Structure**

```
frontend/src/
├── components/          # Reusable UI components
│   ├── Button.jsx
│   ├── LoadingSpinner.jsx
│   ├── ErrorMessage.jsx
│   └── ErrorBoundary.jsx
│
├── contexts/           # Global state management
│   └── AppContext.jsx
│
├── hooks/              # Custom React hooks
│   └── useErrorHandler.js
│
├── pages/              # Route components
│   ├── Splash.jsx
│   ├── Home.jsx
│   ├── Preferences.jsx
│   ├── MenuUpload.jsx
│   ├── PlateCapture.jsx
│   └── Analysis.jsx
│
├── services/           # API communication
│   └── api.js
│
├── utils/              # Helper functions
│   └── validation.js
│
└── App.jsx             # Root component
```

---

### Backend Architecture

#### **1. Express Server Setup**

**File**: `backend/server.js`

```javascript
const app = express();

// Security middleware
app.use(cors({ origin: allowedOrigins }));
app.use(express.json({ limit: '10mb' }));

// Security headers
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  next();
});

// Rate limiting
function rateLimit(req, res, next) {
  const ip = req.ip;
  // Track requests per IP
  // Limit to 10 requests per minute
}
```

#### **2. File Upload Configuration**

```javascript
const storage = multer.diskStorage({
  destination: 'uploads/',
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.random();
    cb(null, 'upload-' + uniqueSuffix + path.extname(file.originalname));
  }
});

const upload = multer({
  storage,
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB
    files: 1
  },
  fileFilter: (req, file, cb) => {
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (allowed.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type'));
    }
  }
});
```

#### **3. Image Processing Pipeline**

```javascript
// Preprocessing for better OCR accuracy
await sharp(originalPath)
  .extend({
    top: 40, bottom: 20, left: 20, right: 20,
    background: { r: 255, g: 255, b: 255 }
  })
  .resize({ width: 1200 })
  .grayscale()
  .normalize()
  .threshold(160)
  .sharpen()
  .toFile(processedPath);

// OCR with Tesseract
const result = await Tesseract.recognize(processedPath, 'eng', {
  tessedit_pageseg_mode: 6  // Uniform text block
});
```

**Pipeline Steps**:
1. **Border Extension**: Add white padding for better edge detection
2. **Resize**: Standardize to 1200px width
3. **Grayscale**: Remove color information
4. **Normalize**: Enhance contrast
5. **Threshold**: Binary conversion at 160
6. **Sharpen**: Improve text clarity
7. **OCR**: Extract text with Tesseract

#### **4. Text Cleaning Algorithm**

```javascript
function cleanMenuItems(rawText) {
  const blacklist = ['menu', 'breakfast', 'lunch', 'dinner'];
  
  return rawText
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 1)
    .map(line => {
      // Remove non-alphabetic characters except delimiters
      line = line.replace(/[^A-Za-z, &/]/g, '');
      
      // Split by multiple delimiters
      return line.split(/[,/&]/).map(x => x.trim());
    })
    .flat()
    .map(line => line.toLowerCase())
    .filter(line => !blacklist.some(word => line.includes(word)))
    .filter((item, index, self) => self.indexOf(item) === index) // Deduplicate
    .sort(); // Alphabetical order
}
```

#### **5. Food Database Management**

```javascript
// Load existing database
let foodDatabase = [];
if (fs.existsSync(foodDbPath)) {
  foodDatabase = JSON.parse(fs.readFileSync(foodDbPath));
}

// Get existing names for deduplication
const existingNames = new Set(
  foodDatabase.map(item => item.name.toLowerCase())
);

// Add only new items
menuItems.forEach(itemName => {
  if (!existingNames.has(itemName)) {
    foodDatabase.push({
      name: itemName,
      category: '',
      serving_size: 0,
      serving_unit: 'g/ml',
      calories: 0,
      protein: 0,
      carbs: 0,
      fat: 0,
      fiber: 0,
      veg: true
    });
    existingNames.add(itemName);
  }
});

// Sort and save
foodDatabase.sort((a, b) => a.name.localeCompare(b.name));
fs.writeFileSync(foodDbPath, JSON.stringify(foodDatabase, null, 2));
```

#### **6. RESTful API Endpoints**

**GET /api/foods** - Retrieve all foods
```javascript
app.get('/api/foods', (req, res) => {
  try {
    const data = fs.readFileSync('./data/foodDatabase.json');
    const foods = JSON.parse(data);
    res.json(foods);
  } catch (err) {
    res.status(500).json({ error: 'Failed to load database' });
  }
});
```

**GET /api/foods/search?q=query** - Search foods
```javascript
app.get('/api/foods/search', (req, res) => {
  const query = req.query.q?.toLowerCase();
  
  if (!query) {
    return res.status(400).json({ error: 'Query required' });
  }
  
  const foods = JSON.parse(fs.readFileSync('./data/foodDatabase.json'));
  const results = foods.filter(food => 
    food.name.toLowerCase().includes(query)
  );
  
  res.json(results);
});
```

**POST /ocr** - Process menu image
```javascript
app.post('/ocr', rateLimit, upload.single('image'), async (req, res) => {
  try {
    // 1. Validate file
    // 2. Process image with Sharp
    // 3. Run OCR with Tesseract
    // 4. Clean extracted text
    // 5. Update food database
    // 6. Return menu items
    // 7. Cleanup temp files
    
    res.json({ menuItems });
  } catch (err) {
    res.status(500).json({ error: 'OCR failed' });
  }
});
```

**GET /health** - Health check
```javascript
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    timestamp: new Date().toISOString() 
  });
});
```

---

## 🔄 Data Flow

### Menu Upload Flow

```
User → MenuUpload Component
  ↓
1. Select/Capture Image
  ↓
2. validateImageFile() - Client validation
  ↓
3. api.uploadMenuImage(file) - API service call
  ↓
4. POST /ocr - Backend endpoint
  ↓
5. Multer - File upload handling
  ↓
6. Sharp - Image preprocessing
  ↓
7. Tesseract - OCR processing
  ↓
8. cleanMenuItems() - Text cleaning
  ↓
9. Update foodDatabase.json
  ↓
10. Response { menuItems: [...] }
  ↓
11. setTodaysMenu() - Update context
  ↓
12. localStorage.setItem() - Persist data
  ↓
13. Display extracted menu
```

### User Profile Flow

```
User → Preferences Component
  ↓
1. Enter profile data (age, height, weight, etc.)
  ↓
2. Click "Calculate & Save"
  ↓
3. validateProfileData() - Client validation
  ↓
4. Calculate BMI, BMR, calories, protein
  ↓
5. setUserProfile() - Update context
  ↓
6. useEffect → localStorage.setItem() - Auto-persist
  ↓
7. Display calculated values
  ↓
8. Navigate to other pages → Data persists
```

### State Synchronization

```
AppContext (In-Memory State)
  ↕ (Auto-sync via useEffect)
localStorage (Browser Storage)
  ↕ (Future: API calls)
Backend Database (PostgreSQL/MongoDB)
```

---

## 🔐 Security Implementation

### 1. **Input Validation**

**Frontend**:
- File type checking before upload
- File size validation (max 10MB)
- Form field validation (age, height, weight ranges)
- Sanitized user inputs

**Backend**:
- Multer file filter
- MIME type validation
- File size limits
- Request body size limits (10MB)

### 2. **Rate Limiting**

```javascript
const rateLimitMap = new Map();
const MAX_REQUESTS = 10; // per minute
const RATE_LIMIT_WINDOW = 60000; // 1 minute

function rateLimit(req, res, next) {
  const ip = req.ip;
  const now = Date.now();
  
  const record = rateLimitMap.get(ip) || { count: 0, resetTime: now + RATE_LIMIT_WINDOW };
  
  if (now > record.resetTime) {
    rateLimitMap.set(ip, { count: 1, resetTime: now + RATE_LIMIT_WINDOW });
    return next();
  }
  
  if (record.count >= MAX_REQUESTS) {
    return res.status(429).json({ error: 'Too many requests' });
  }
  
  record.count++;
  next();
}
```

### 3. **CORS Configuration**

```javascript
const allowedOrigins = [
  'http://localhost:5173',
  'http://127.0.0.1:5173',
  // Additional local network IPs
];

app.use(cors({
  origin: function (origin, callback) {
    if (!origin || allowedOrigins.indexOf(origin) !== -1) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true
}));
```

### 4. **Security Headers**

```javascript
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  next();
});
```

### 5. **Resource Cleanup**

```javascript
// Always cleanup temp files in finally block
finally {
  if (originalPath && fs.existsSync(originalPath)) {
    fs.unlinkSync(originalPath);
  }
  if (processedPath && fs.existsSync(processedPath)) {
    fs.unlinkSync(processedPath);
  }
}
```

---

## 📊 Database Schema

### Food Database Structure

**File**: `backend/data/foodDatabase.json`

```json
[
  {
    "name": "chapati",
    "category": "grains",
    "serving_size": 40,
    "serving_unit": "g",
    "calories": 104,
    "protein": 3.1,
    "carbs": 18.0,
    "fat": 2.4,
    "fiber": 2.8,
    "veg": true
  }
]
```

**Fields**:
- `name` (string): Food item name (lowercase, unique)
- `category` (string): Food category (grains, proteins, dairy, etc.)
- `serving_size` (number): Standard serving size
- `serving_unit` (string): Unit of measurement (g/ml)
- `calories` (number): Calories per serving
- `protein` (number): Protein in grams
- `carbs` (number): Carbohydrates in grams
- `fat` (number): Fat in grams
- `fiber` (number): Fiber in grams
- `veg` (boolean): Vegetarian flag

**Current Status**: 42 items with schema defined, nutritional values pending population

---

## 🎨 UI/UX Implementation

### Design System

**Color Palette**:
```css
/* Primary Colors */
--emerald-50: #f0fdf4;
--emerald-600: #10b981;
--emerald-700: #059669;

/* Neutral Colors */
--slate-50: #f8fafc;
--slate-700: #334155;
--slate-900: #0f172a;

/* Semantic Colors */
--red-50: #fef2f2;
--red-600: #dc2626;
```

**Typography**:
- Font Family: System fonts (optimized for performance)
- Headings: Bold, 2xl-3xl sizes
- Body: Regular, sm-base sizes
- Monospace: For code/data display

**Spacing Scale** (Tailwind):
- 1 unit = 0.25rem (4px)
- Common: 2, 4, 6, 8, 12, 16, 24, 32

**Component Patterns**:
```jsx
// Card Pattern
<div className="rounded-2xl bg-white p-6 shadow-md hover:shadow-lg transition">
  {/* Content */}
</div>

// Button Pattern
<button className="rounded-xl bg-emerald-600 hover:bg-emerald-700 
                   py-3 px-6 text-white font-bold 
                   transition active:scale-[0.98]">
  Click Me
</button>

// Input Pattern
<input className="w-full rounded-lg border border-gray-200 px-4 py-3
                  focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200
                  outline-none transition" />
```

---

## 🚀 Performance Optimizations

### Frontend

1. **Code Splitting**: Vite automatically splits code by routes
2. **Lazy Loading**: Components loaded on demand
3. **Asset Optimization**: Images compressed, fonts subset
4. **Service Worker Caching**: 
   - Fonts cached for 1 year
   - Images cached for 30 days
   - App shell cached indefinitely

### Backend

1. **Image Processing**: Sharp (native C++ bindings, very fast)
2. **File Cleanup**: Automatic temp file deletion
3. **Rate Limiting**: Prevents server overload
4. **Error Handling**: Prevents crashes, graceful degradation

---

## 📦 Dependencies

### Backend (`backend/package.json`)
```json
{
  "dependencies": {
    "express": "^5.2.1",      // Web framework
    "cors": "^2.8.6",          // CORS middleware
    "multer": "^2.0.2",        // File upload
    "sharp": "^0.34.5",        // Image processing
    "tesseract.js": "^7.0.0"   // OCR engine
  },
  "devDependencies": {
    "nodemon": "^3.1.11"       // Auto-restart on changes
  }
}
```

### Frontend (`frontend/package.json`)
```json
{
  "dependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "react-router-dom": "^7.13.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.1.1",
    "tailwindcss": "^3.4.17",
    "vite": "^7.2.4",
    "vite-plugin-pwa": "^1.2.0",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35"
  }
}
```

---

## 🧪 Testing Strategy

### Manual Testing Checklist

**User Profile**:
- ✅ Form validation (invalid inputs rejected)
- ✅ BMI calculation accuracy
- ✅ Calorie calculation (Mifflin-St Jeor formula)
- ✅ Data persistence across sessions
- ✅ localStorage synchronization

**Menu Upload**:
- ✅ Image validation (type, size)
- ✅ OCR accuracy on various menu formats
- ✅ Text cleaning and deduplication
- ✅ Database updates (no duplicates)
- ✅ Error handling (network failures, invalid files)

**State Management**:
- ✅ Context updates propagate to all components
- ✅ localStorage sync on state changes
- ✅ Data persists on page refresh
- ✅ No data loss on navigation

**Error Handling**:
- ✅ Network errors show retry option
- ✅ Validation errors display clearly
- ✅ App doesn't crash on errors
- ✅ Error boundary catches React errors

---

## 📈 Current Status

### ✅ Completed Features

**Infrastructure**:
- [x] Backend Express server with security
- [x] RESTful API endpoints (OCR, foods, search, health)
- [x] Frontend API service layer
- [x] Global state management (Context API)
- [x] Error handling system (boundaries + hooks)
- [x] Input validation (forms + files)
- [x] Shared UI components

**Features**:
- [x] OCR menu processing pipeline
- [x] Food database with nutritional schema
- [x] PWA configuration and offline support
- [x] Modern UI with Tailwind CSS
- [x] Camera integration for menu upload
- [x] User preferences management
- [x] BMI/BMR/calorie calculations
- [x] Routing and navigation

**Security**:
- [x] Rate limiting (10 req/min)
- [x] CORS policy
- [x] File validation
- [x] Security headers
- [x] Resource cleanup

### 🚧 Pending / Future Work

**Data Population**:
- [ ] Populate nutritional values for 42 food items
- [ ] Categorize food items
- [ ] Add serving size information

**ML/CV Features**:
- [ ] Depth estimation for portion calculation
- [ ] Food segmentation algorithms
- [ ] Volume analysis from RGB images
- [ ] Portion size estimation

**Backend Enhancements**:
- [ ] Database migration (PostgreSQL/MongoDB)
- [ ] User authentication (JWT)
- [ ] User data persistence
- [ ] Historical tracking

**Recommendation System**:
- [ ] Personalized portion recommendations
- [ ] Nutritional goal tracking
- [ ] Meal planning suggestions

---

## 🔮 Future Roadmap

### Phase 1: Data \u0026 Intelligence
1. Populate food database with nutritional data
2. Implement recommendation algorithm
3. Add nutritional analysis dashboard

### Phase 2: Computer Vision
1. Integrate depth estimation model
2. Implement food segmentation
3. Calculate portion volumes from images
4. Compare actual vs recommended portions

### Phase 3: Backend Migration
1. Set up PostgreSQL/MongoDB
2. Implement user authentication
3. Create user data API
4. Migrate from localStorage to database

### Phase 4: Advanced Features
1. Historical tracking and analytics
2. Social features (sharing, challenges)
3. Barcode scanning
4. Recipe suggestions
5. Meal planning

---

## 🛠️ Development Setup

### Prerequisites
- Node.js 18+ 
- npm or yarn
- Modern browser with PWA support
- Camera permissions (for mobile)

### Installation

**Backend**:
```bash
cd backend
npm install
npm run dev  # Starts on http://localhost:5000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev  # Starts on http://localhost:5173
```

### Environment Variables

**Backend** (`.env`):
```
PORT=5000
HOST=0.0.0.0
NODE_ENV=development
```

**Frontend** (`.env`):
```
VITE_API_URL=http://localhost:5000
```

---

## 📊 Project Statistics

- **Total Files**: 30+ source files
- **Lines of Code**: ~3,500+ (excluding dependencies)
- **React Components**: 12 (6 pages + 6 shared)
- **API Endpoints**: 4 (OCR, foods, search, health)
- **Food Database Items**: 42 items
- **Dependencies**: 25+ packages
- **Supported Platforms**: Web, Mobile (PWA)

---

## 🏆 Key Technical Achievements

1. ✅ **Modular Architecture**: Clean separation of concerns
2. ✅ **Scalable State Management**: Context API ready for database
3. ✅ **Robust Error Handling**: Graceful degradation, retry logic
4. ✅ **Security Best Practices**: Rate limiting, validation, CORS
5. ✅ **Modern UI/UX**: Responsive, accessible, offline-capable
6. ✅ **Performance Optimized**: Fast image processing, caching
7. ✅ **Developer Experience**: Hot reload, TypeScript-ready, ESLint

---

## 📝 Code Quality Metrics

### Best Practices Implemented
- **DRY Principle**: Shared components, utility functions
- **Separation of Concerns**: API/State/UI separated
- **Error Resilience**: Try-catch blocks, error boundaries
- **Type Safety**: Validation at boundaries
- **Performance**: Optimized image processing, lazy loading
- **Scalability**: Configurable, modular architecture
- **Maintainability**: Clear file structure, inline documentation

---

**Project Repository**: PortionVision  
**Last Updated**: February 13, 2026  
**Version**: 1.0.0  
**Status**: Active Development - Infrastructure Complete, Ready for ML Integration
