# PortionVision Technical Documentation

## Overview
PortionVision is a smart nutrition assistant that helps users balance their meals. It digitizes mess menus using OCR, generates personalized plate recommendations based on the user's metabolic profile, and allows users to track their actual intake via photo capture.

## System Architecture

### Frontend (React + Vite)
-   **Core**: React 19, Vite 6.
-   **Styling**: Tailwind CSS v3 with a custom Emerald/Slate theme.
-   **State Management**: `AppContext` (Context API) handles:
    -   `userProfile`: Stored permanently in **localStorage** (Client-side only).
    -   `todaysMenu`: Stores the daily menu items and OCR text.
-   **PWA**: `vite-plugin-pwa` configured for offline capability and mobile installation (manifest, service worker).
-   **Routing**: `react-router-dom` v7.

### Backend (Node.js + Express)
-   **API**: Express.js REST API.
-   **Proxies**: Frontend development server proxies `/api` and `/ocr` to Backend port 5000.
-   **Data Storage**: JSON flat-file database in `/backend/data/`.
    -   `menu.json`: Current active menu.
    -   `foodDatabase.json`: Knowledge base of food items and their nutritional values.
-   **Image Processing**: 
    -   `multer` for uploads.
    -   `sharp` for image pre-processing (grayscale, thresholding).
    -   `tesseract.js` for OCR.

## Core Logic & Algorithms

### 1. Menu OCR Pipeline (`/ocr`)
1.  **Input**: Image from Camera or Gallery.
2.  **Processing**: Image is resized (width 1200px), converted to grayscale, and thresholded to maximize text contrast.
3.  **Extraction**: Tesseract.js recognizes text.
4.  **Parsing (`cleanMenuItems`)**:
    -   Splits text by newlines and delimiters (`,`, `/`, `&`).
    -   Filters noise, numbers, and common headers.
    -   Deduplicates items and updates `menu.json`.

### 2. Recommendation Engine (`portion_recommender.js`)
Generates specific quantity recommendations to create a balanced plate.

#### A. Calorie Estimation
-   **BMR Calculation**: Uses **Mifflin-St Jeor Equation** based on weight, height, age, and gender.
-   **TDEE Adjustment**: Multiplies BMR by Activity Level (1.2 - 1.725).
-   **Goal Adjustment**: 
    -   Lose Weight: -400 to -500 kcal.
    -   Gain Muscle: +300 to +400 kcal.

#### B. Food Classification
Items from the menu are matched against `foodDatabase.json` or classified via keywords:
-   **Carb**: Rice, Roti, Bread, Poha.
-   **Protein**: Dal, Chicken, Paneer, Egg.
-   **Veg**: Sabji, Salad.
-   **Mixed**: Biryani, Khichdi (treated as complete meals).

#### C. Plate Composition Rules
1.  **Meal Fraction**: Allocates daily calories (Breakfast 25%, Lunch 35%, Dinner 30%).
2.  **Selection Priority**:
    -   If a **Mixed Meal** (e.g., Biryani) is available, it is prioritized.
    -   Otherwise, builds a **Standard Plate**: 1 Carb + 1 Protein + 1 Veg + 1 Addon.
3.  **Quantification**: Converts target calories into user-friendly units (bowls, pieces).

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/menu` | Get the current digitized menu. |
| `POST` | `/ocr` | Upload image for menu extraction. |
| `POST` | `/api/recommend` | Get portion recommendations. Body: `{ userProfile, mealType, menuItems }`. |
| `GET` | `/api/foods` | Get all foods in the database. |
| `GET` | `/api/foods/search` | Search foods by name (`?q=query`). |

## Setup Instructions

1.  **Backend**:
    ```bash
    cd backend
    npm install
    npm run dev
    ```
    Runs on `http://localhost:5000`.

2.  **Frontend**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```
    Runs on `http://localhost:5173`. Access via Network IP (e.g., `192.168.x.x:5173`) for mobile testing.

## Folder Structure
```
portion-vision/
├── backend/
│   ├── data/               # JSON Database
│   ├── uploads/            # Temp storage
│   ├── server.js           # API Entry Point
│   └── portion_recommender.js # Logic
├── frontend/
│   ├── src/
│   │   ├── components/     # UI Components
│   │   ├── contexts/       # Global State (AppContext)
│   │   ├── pages/          # Screens
│   │   └── services/       # API Definitions
│   ├── vite.config.js      # PWA & Proxy Config
│   └── tailwind.config.js  # Styling Config
```
