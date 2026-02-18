const fs = require("fs");
const path = require("path");

// ==========================================
// 1. Data & Helpers
// ==========================================

// Load food database
let FOOD_DB = [];
try {
  const dbPath = path.join(__dirname, "data", "foodDatabase.json");
  if (fs.existsSync(dbPath)) {
    FOOD_DB = JSON.parse(fs.readFileSync(dbPath, "utf8"));
  }
} catch (err) {
  console.error("Error reading food database:", err);
}

// Helper to find food in DB (case-insensitive)
function findFood(name) {
  return FOOD_DB.find(f => f.name.toLowerCase() === name.toLowerCase());
}

// Fallback logic if food not in DB
function getFallbackDetails(name) {
  const n = name.toLowerCase();

  if (n.includes("biryani") || n.includes("pulao") || n.includes("fried rice") || n.includes("khichdi"))
    return { category: "carb_base", meal_role: "mixed", unit_type: "bowl", serving_size: 250, calories: 300 };

  if (n.includes("rice"))
    return { category: "carb_base", unit_type: "bowl", serving_size: 200, calories: 250 };
  if (n.includes("roti") || n.includes("chapati") || n.includes("naan") || n.includes("paratha") || n.includes("bread"))
    return { category: "carb_base", unit_type: "piece", serving_size: 50, calories: 100 };

  if (n.includes("chicken") || n.includes("egg") || n.includes("fish") || n.includes("paneer"))
    return { category: "protein_main", unit_type: "bowl", serving_size: 150, calories: 220 };

  if (n.includes("dal") || n.includes("sambar") || n.includes("rajma") || n.includes("chole"))
    return { category: "protein_main", unit_type: "bowl", serving_size: 150, calories: 180 };

  if (n.includes("sabji") || n.includes("fry") || n.includes("poriyal") || n.includes("bhaji"))
    return { category: "side", unit_type: "bowl", serving_size: 150, calories: 140 };

  if (n.includes("salad") || n.includes("raita") || n.includes("curd"))
    return { category: "side", unit_type: "bowl", serving_size: 100, calories: 80 };

  if (n.includes("sweet") || n.includes("halwa") || n.includes("jamun") || n.includes("laddu"))
    return { category: "dessert", unit_type: "piece", serving_size: 50, calories: 200 };

  // Default generic
  return { category: "other", unit_type: "serving", serving_size: 100, calories: 150 };
}

// ==========================================
// 2. Core Logic: Classify & Select
// ==========================================

function classifyItem(foodName) {
  let dbItem = findFood(foodName);
  let details = dbItem ? { ...dbItem } : { name: foodName, ...getFallbackDetails(foodName) };

  // Determine Role based on category (TRUST THE DB)
  let role = "other";

  // 1. Check for Mixed Meals first
  if (details.meal_role === "mixed") {
    role = "mixed";
  }
  // 2. Category Mapping
  else {
    // Logic adjustment for Low Protein "mains" -> Side (e.g. Veg Hariyali with 5g protein)
    if (details.category === "protein_main" && details.protein_level === "low") {
      role = "side"; // Downgrade to side
    }
    // Force Sweet/Dessert to Limit
    else if (details.category === "dessert" || (details.tags && details.tags.includes("sweet"))) {
      role = "limit";
    }
    else {
      switch (details.category) {
        case "carb_base": role = "carb"; break;
        case "protein_main": role = "protein"; break;
        case "side": role = "veg"; break; // side = veg usually
        case "snack": role = "snack"; break;
        case "beverage": role = "addon"; break;
        case "condiment": role = "addon"; break;
        case "dessert": role = "limit"; break;
        default: role = "other";
      }
    }
  }

  // 3. Special Override: Detect hidden proteins via tags even if category isn't perfect
  // Example: "egg curry" might be missing category but has "egg" tag
  if (role !== "protein" && role !== "mixed") {
    const tags = (details.tags || []).map(t => t.toLowerCase());
    if (tags.includes("egg") || tags.includes("chicken") || tags.includes("paneer") || tags.includes("fish")) {
      // If calorie density suggests main dish (>150), treat as protein
      if ((details.calories || 0) > 100) role = "protein";
    }
  }

  // 4. Special Override: Snacks as Mains (fallback handled in main logic)
  // Just ensure we don't treat small additives as snaks

  return { ...details, role };
}

// ==========================================
// 3. Calorie Estimation
// ==========================================

function estimateDailyCalories(user) {
  const weight = parseFloat(user.weight_kg || user.weight) || 70;
  const height = parseFloat(user.height_cm || user.height) || 170;
  const age = parseInt(user.age) || 25;
  const sex = (user.sex || user.gender || "male").toLowerCase();
  const activityLevel = (user.activity_level || user.activityLevel || "moderate").toLowerCase();
  const goal = (user.goalType || user.goal || "maintain").toLowerCase(); // Support both fields

  // Mifflin-St Jeor Equation
  const bmr = sex === "female"
    ? 10 * weight + 6.25 * height - 5 * age - 161
    : 10 * weight + 6.25 * height - 5 * age + 5;

  const activityMultipliers = {
    sedentary: 1.2,
    light: 1.375,
    moderate: 1.55,
    active: 1.725
  };

  let tdee = bmr * (activityMultipliers[activityLevel.split(" ")[0]] || 1.55);

  if (goal.includes("lose")) tdee -= 400; // Deficit
  if (goal.includes("gain")) tdee += 300; // Surplus

  return Math.round(Math.max(1200, Math.min(4000, tdee)));
}

// ==========================================
// 4. Recommendation Engine
// ==========================================

function recommendPlate({ user, menuItems, mealType }) {
  const dailyCalories = estimateDailyCalories(user);
  const type = (mealType || "lunch").toLowerCase();

  // Calorie distribution
  const mealFrac = {
    breakfast: 0.25,
    lunch: 0.35,
    dinner: 0.30,
    snack: 0.10
  }[type] || 0.33;

  const targetCalories = dailyCalories * mealFrac;
  const safeMenu = Array.isArray(menuItems) ? menuItems : [];

  // 1. Classify all available items
  const classifiedItems = safeMenu.map(classifyItem);

  // 2. Filter available roles
  const mixedMeals = classifiedItems.filter(i => i.role === "mixed");
  const carbs = classifiedItems.filter(i => i.role === "carb");
  const proteins = classifiedItems.filter(i => i.role === "protein");
  const vegs = classifiedItems.filter(i => i.role === "veg"); // Sides
  const snacks = classifiedItems.filter(i => i.role === "snack"); // Poha/Upma etc
  const addons = classifiedItems.filter(i => i.role === "addon"); // Curd/Bev
  const limits = classifiedItems.filter(i => i.role === "limit");

  let plate = [];
  let currentCalories = 0;

  // Helper to add item
  const addToPlate = (item, quantity = 1, reason = "") => {
    if (!item) return;
    const estimatedCals = Math.round(item.calories * quantity);
    plate.push({
      item: item.name,
      dish_type: item.dish_type,
      role: item.role, // "mixed", "carb", "protein" etc
      recommendedQuantity: quantity,
      unit: item.unit_type || "serving",
      serving_size: item.serving_size, // For reference
      estimatedCalories: estimatedCals,
      reason: reason,
      icon: getIconForRole(item.role)
    });
    currentCalories += estimatedCals;
  };

  // --- SELECTION LOGIC ---

  // A. Try Mixed Meal First (Biryani Priority)
  // If we have a mixed meal, we generally don't need a separate carb base.
  let mainSelected = false;

  if (mixedMeals.length > 0) {
    // Pick the best mixed meal (e.g. prioritize protein-rich ones if possible)
    // For now, simple pick first or random
    const bestMixed = mixedMeals[0];

    // Calculate quantity based on target calories
    // If target is 700 and biryani is 350, give 2 servings (or 1.5)
    let qty = Math.min(2.5, Math.max(1, Math.round((targetCalories * 0.7) / bestMixed.calories * 2) / 2));

    addToPlate(bestMixed, qty, "Complete balanced meal");
    mainSelected = true;
  }

  // B. If no Mixed Meal, Build Standard Plate (Carb + Protein)
  if (!mainSelected) {
    let selectedCarb = carbs[0]; // Simple selection sort
    // If NO standard carbs (roti/rice) exist (e.g. Breakfast), try Snack as Main (Poha)
    if (!selectedCarb && snacks.length > 0) {
      selectedCarb = snacks[0]; // Use Poha/Upma as the carb base
    }

    let selectedProtein = proteins.length > 0 ? proteins[0] : null;

    if (selectedCarb) {
      let carbCals = targetCalories * 0.5; // 50% calories from Carb
      // If protein is missing, carb takes more
      if (!selectedProtein) carbCals = targetCalories * 0.7;

      let qty = Math.round(carbCals / selectedCarb.calories);
      // Sanity check: Don't suggest 10 rotis. Cap based on unit.
      if (selectedCarb.unit_type === 'piece') qty = Math.min(4, Math.max(1, qty));
      if (selectedCarb.unit_type === 'bowl') qty = Math.min(2, Math.max(1, qty)); // 1-2 bowls of rice

      addToPlate(selectedCarb, qty, "Energy Source");
    }

    if (selectedProtein) {
      let protCals = targetCalories * 0.3; // 30% from Protein
      let qty = Math.round(protCals / selectedProtein.calories);
      if (selectedProtein.unit_type === 'bowl') qty = Math.min(2, Math.max(1, qty));
      else qty = Math.max(1, qty); // Default 1

      addToPlate(selectedProtein, qty, "Muscle Repair");
    } else {
      // No protein found... maybe advise milk/curd later
    }
  }

  // C. Add Accompaniments (Side/Veg)
  // Always good to have fiber
  if (vegs.length > 0) {
    // Pick one side
    const side = vegs[0];
    addToPlate(side, 1, "Fiber & Vitamins");
  }

  // D. Add Addons (Curd/Beverage)
  // If calorie budget allows or implies need
  const remainingBudget = targetCalories - currentCalories;
  if (targetCalories > currentCalories + 50 && addons.length > 0) {
    // Prefer Curd/Milk/Buttermilk for protein boost if main protein was weak
    const dairy = addons.find(a => ["curd", "milk", "buttermilk", "lassi"].some(k => a.name.includes(k)));
    if (dairy) {
      addToPlate(dairy, 1, "Probiotics/Calcium");
    } else {
      // Any other addon (Chutney etc - keep small)
      const condiment = addons[0];
      addToPlate(condiment, 1, "Flavor");
    }
  }

  // E. Limits (Dessert) - Only if surplus or goal is gain
  // For maintain/lose, suggest avoiding unless explicitly asked (not implemented yet)
  const optionalItems = limits.map(l => ({
    ...l,
    note: "Consume in moderation",
    limit: "1 portion max"
  }));

  // F. Identify items to avoid (if any weird stuff matches user allergies not handled here)
  const avoidOrLimit = [];

  return {
    mealType: type,
    recommendedPlate: plate,
    optionalItems: optionalItems,
    avoidOrLimit: avoidOrLimit,
    summary: {
      dailyCalories: dailyCalories,
      targetMealCalories: Math.round(targetCalories),
      totalPlateCalories: Math.round(currentCalories),
      plateLogic: `Balanced plate aligned with ${user.goal || "maintain"} goal.`,
      notes: "Portions are estimates."
    }
  };
}

function getIconForRole(role) {
  const map = {
    mixed: "🍲",
    carb: "🌾",
    protein: "💪",
    veg: "🥗",
    side: "🥗",
    snack: "🥣",
    addon: "🥛",
    limit: "🍰"
  };
  return map[role] || "🍽️";
}

module.exports = { recommendPlate, estimateDailyCalories, classifyItem };
