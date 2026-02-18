# PortionVision Technical Documentation

## Overview
PortionVision is a smart nutrition assistant designed for hostel students. It helps users make balanced meal choices from their daily mess menu and analyze their actual plate portions using computer vision.

## System Architecture

### Frontend (React + Vite)
-   ** Framework**: React 18 with Vite for fast HMR.
-   ** Styling**: Tailwind CSS for responsive and modern UI.
-   ** State Management**: Context API (`AppContext`) for global state (User Profile, Today's Menu).
-   ** PWA**: Configured as a Progressive Web App for mobile installation.

### Backend (Node.js + Express)
-   ** Server**: Express.js REST API.
-   ** Database**: JSON-based file storage (`/data` folder) for simplicity and portability.
-   ** OCR Engine**: Tesseract.js for extracting text from menu images.
-   ** Recommendation Engine**: Custom rule-based logic for generating balanced meal plates.

## Key Features & Logic

### 1. Menu Digitization (OCR)
-   **Process**: User uploads a photo of the mess menu -> Backend uses `sharp` to pre-process (grayscale, threshold) -> `tesseract.js` extracts text.
-   **Cleaning**: Raw text is cleaned to remove noise and filter for valid food items.
-   **Storage**: Menu items are saved to `menu.json` and new unique items are added to `foodDatabase.json`.

### 2. Balanced Plate Recommendation Engine
Unlike simple calorie counters, PortionVision generates a complete "Balanced Plate" recommendation based on the user's goal (Lose/Gain/Maintain) and meal type (Breakfast/Lunch/Dinner).

**Logic Flow (`portion_recommender.js`):**
1.  **Input**: User Profile (Height, Weight, Age, Gender, Goal) + Available Menu Items.
2.  **Calorie Calculation**: Mifflin-St Jeor Equation estimates TDEE (Total Daily Energy Expenditure).
3.  **Classification**: Menu items are categorized into roles:
    -   `Carb`: Rice, Roti, Poha, etc.
    -   `Protein`: Dal, Paneer, Chicken, Egg, etc.
    -   `Veg`: Sabji, Salad, Fruit.
    -   `Addon`: Curd, Milk, etc.
    -   `Limit`: Sweets, Fried items.
4.  **Selection Rules**:
    -   **Breakfast**: Prioritizes lighter mains (Poha/Upma) + Proteins/Addons.
    -   **Lunch/Dinner**: Selects 1 Carb + 1 Protein + 1 Veg + 1 Addon.
    -   **Portion Sizing**: Calculates realistic units (bowls/pieces) to match target calories.
5.  **Output**: Structured JSON with specific quantities and reasoning.

### 3. Portion Analysis (Computer Vision)
-   **Goal**: Compare the user's actual plate photo against the recommended portion.
-   **Current State**: Placeholder implementation (Mock UI). Future scope includes using TensorFlow.js or a Python service for ensuring compliance.

## API Endpoints

### `/ocr` (POST)
-   **Input**: Image file (`multipart/form-data`).
-   **Output**: Extracted menu items (JSON).

### `/api/recommend` (POST)
-   **Input**: User Profile, Meal Type.
-   **Output**: `{ recommendedPlate: [...], summary: {...} }`

### `/api/foods` (GET)
-   **Output**: List of all known foods in `foodDatabase.json`.

## Folder Structure
```
portion-vision/
├── backend/
│   ├── data/               # JSON storage (menu.json, foodDatabase.json)
│   ├── uploads/            # Temp image storage
│   ├── server.js           # Express app entry point
│   └── portion_recommender.js # Core logic
├── frontend/
│   ├── src/
│   │   ├── components/     # Reusable UI (RecommendationCard, etc.)
│   │   ├── pages/          # Screens (Home, MenuUpload, Analysis)
│   │   └── services/       # API integration
│   └── public/             # PWA assets
```

## Setup Instructions
1.  **Backend**: `cd backend && npm install && npm run dev`
2.  **Frontend**: `cd frontend && npm install && npm run dev`
3.  **Access**: Open `http://localhost:5173` (or network IP for mobile).
