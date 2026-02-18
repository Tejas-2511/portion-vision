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
  if (n.includes("rice") || n.includes("pulao") || n.includes("biryani"))
    return { dish_type: "rice", unit_type: "bowl", serving_size: 200, calories: 250 };
  if (n.includes("roti") || n.includes("chapati") || n.includes("naan") || n.includes("paratha"))
    return { dish_type: "roti", unit_type: "piece", serving_size: 50, calories: 100 };
  if (n.includes("dal") || n.includes("sambar") || n.includes("rasam"))
    return { dish_type: "dal", unit_type: "bowl", serving_size: 150, calories: 150 };
  if (n.includes("curry") || n.includes("paneer") || n.includes("chicken") || n.includes("egg"))
    return { dish_type: "curry", unit_type: "bowl", serving_size: 150, calories: 200 };
  if (n.includes("sabji") || n.includes("fry") || n.includes("poriyal") || n.includes("bhaji"))
    return { dish_type: "sabji", unit_type: "bowl", serving_size: 150, calories: 120 };
  if (n.includes("salad") || n.includes("raita") || n.includes("curd"))
    return { dish_type: "side", unit_type: "bowl", serving_size: 100, calories: 80 };
  if (n.includes("sweet") || n.includes("halwa") || n.includes("jamun") || n.includes("laddu"))
    return { dish_type: "sweet", unit_type: "piece", serving_size: 50, calories: 200 };

  // Default generic
  return { dish_type: "other", unit_type: "serving", serving_size: 100, calories: 150 };
}

// ==========================================
// 2. Core Logic: Classify & Select
// ==========================================

function classifyItem(foodName) {
  let dbItem = findFood(foodName);
  let details = dbItem ? { ...dbItem } : { name: foodName, ...getFallbackDetails(foodName) };

  // Determine Role based on dish_type
  let role = "other";
  const type = (details.dish_type || "").toLowerCase();

  const CarbTypes = ["rice", "roti", "bread", "poha", "upma", "paratha", "idli", "dosa", "sandwich"];
  const ProteinTypes = ["dal", "rajma", "chole", "paneer", "egg", "chicken", "soy", "fish", "mutton", "curry"];
  const VegTypes = ["sabji", "salad", "fruit", "vegetable", "saag"];
  const AddonTypes = ["curd", "milk", "buttermilk", "raita", "beverage", "drink", "pickel", "chutney", "sauce", "soup"];
  const LimitTypes = ["sweet", "fried", "dessert", "snack", "junk"];

  if (CarbTypes.includes(type)) role = "carb";
  else if (ProteinTypes.includes(type)) role = "protein";
  else if (VegTypes.includes(type)) role = "veg";
  else if (AddonTypes.includes(type)) role = "addon";
  else if (LimitTypes.includes(type)) role = "limit";

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
  const goal = (user.goal || user.goalType || "maintain").toLowerCase();

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

  if (goal.includes("lose")) tdee -= 400;
  if (goal.includes("gain")) tdee += 300;

  return Math.round(Math.max(1200, Math.min(4000, tdee)));
}

// ==========================================
// 4. Recommendation Engine
// ==========================================

function recommendPlate({ user, menuItems, mealType }) {
  const dailyCalories = estimateDailyCalories(user);

  // Calorie distribution for this meal
  const mealFrac = {
    breakfast: 0.25,
    lunch: 0.35,
    dinner: 0.30,
    snack: 0.10
  }[(mealType || "lunch").toLowerCase()] || 0.33;

  const targetCalories = dailyCalories * mealFrac;
  const safeMenu = Array.isArray(menuItems) ? menuItems : [];

  // 1. Classify all available items
  const classifiedItems = safeMenu.map(classifyItem);

  // 2. Filter available roles
  const carbs = classifiedItems.filter(i => i.role === "carb");
  const proteins = classifiedItems.filter(i => i.role === "protein");
  const vegs = classifiedItems.filter(i => i.role === "veg");
  const addons = classifiedItems.filter(i => i.role === "addon");
  const limits = classifiedItems.filter(i => i.role === "limit");

  let plate = [];
  let currentCalories = 0;
  let summaryNotes = [];

  // Helper to add item to plate
  const addToPlate = (item, quantity = 1, reason = "") => {
    if (!item) return;
    const estimatedCals = Math.round(item.calories * quantity);
    plate.push({
      item: item.name,
      dish_type: item.dish_type,
      role: item.role,
      recommendedQuantity: quantity,
      unit: item.unit_type || "serving",
      estimatedCalories: estimatedCals,
      reason: reason
    });
    currentCalories += estimatedCals;
  };

  // 3. Selection Logic based on Meal Type
  const type = (mealType || "lunch").toLowerCase();

  if (type === "breakfast") {
    // Priority: Light Carb + Protein/Addon
    // e.g. Poha/Upma/Paratha + Curd/Milk OR Bread + Egg

    // Pick main
    const main = carbs[0] || proteins[0] || limits[0]; // limits might contain "Idli" if misclassified, or sweet items
    if (main) {
      if (main.unit_type === "piece") addToPlate(main, 2, "Main breakfast item");
      else addToPlate(main, 1, "Light main dish");
    }

    // Pick side/beverage
    const side = addons[0] || proteins.find(p => p !== main) || vegs[0];
    if (side) addToPlate(side, 1, "Accompaniment");

  } else if (type === "snack") {
    // Priority: Light item only
    const snack = limits.find(i => i.dish_type === "snack") || carbs[0] || vegs[0];
    if (snack) addToPlate(snack, 1, "Light snack");

  } else {
    // LUNCH & DINNER: Full Balanced Plate

    // A. CARB (Select 1-2 types)
    // If Rice & Roti both exist, user might want both or one. 
    // Strategy: If "weight loss", prefer Roti. If "gain", both.
    const hasRice = carbs.find(c => c.dish_type === "rice");
    const hasRoti = carbs.find(c => c.dish_type === "roti");

    if (user.goal.includes("lose")) {
      // Prioritize Roti (fiber) over Rice, limit quantity
      if (hasRoti) addToPlate(hasRoti, 2, "Fiber-rich carb for weight loss");
      else if (hasRice) addToPlate(hasRice, 1, "Portion-controlled rice");
    } else {
      // Standard/Gain: Can have both
      if (hasRoti) addToPlate(hasRoti, 2, "Main staple");
      if (hasRice) addToPlate(hasRice, 1, hasRoti ? "Side portion" : "Main staple");
    }

    // B. PROTEIN (Dal/Paneer/Chicken/Egg) - Select 1 (Best available)
    // Priority: Non-Veg > Paneer > Dal > Others
    const mainProtein = proteins.find(p => ["chicken", "mutton", "fish", "egg", "paneer"].includes(p.dish_type))
      || proteins.find(p => p.dish_type === "dal")
      || proteins[0];

    if (mainProtein) {
      // If gain, double protein
      const qty = user.goal.includes("gain") ? 1.5 : 1;
      const unit = Number.isInteger(qty) ? "bowl" : "bowls";
      addToPlate(mainProtein, qty, "Essential protein source");
    }

    // C. VEG (Sabji/Salad) - Select 1 cooked veg + 1 raw if available
    const cookedVeg = vegs.find(v => v.dish_type === "sabji");
    const rawVeg = vegs.find(v => v.dish_type === "salad" || v.dish_type === "fruit");

    if (cookedVeg) addToPlate(cookedVeg, 1, "Fiber and micronutrients");
    if (rawVeg) addToPlate(rawVeg, 1, "Fresh Salad for volume");

    // D. ADDON - Curd/Raita/Buttermilk
    if (addons.length > 0) {
      addToPlate(addons[0], 1, "Probiotic/Digestion aid");
    }
  }

  // 4. Calorie Adjustment Logic (Simple Scaling)
  // If we are significantly over/under, adjust the carb portion
  const carbItem = plate.find(p => p.role === "carb");
  if (carbItem) {
    if (currentCalories < targetCalories * 0.7) {
      // Undereating: Increase carb
      carbItem.recommendedQuantity += (carbItem.unit === "piece" ? 1 : 0.5);
      carbItem.reason += " (Increased for energy)";
      currentCalories += (carbItem.estimatedCalories / carbItem.recommendedQuantity) * (carbItem.unit === "piece" ? 1 : 0.5);
    } else if (currentCalories > targetCalories * 1.2 && user.goal.includes("lose")) {
      // Overeating: Decrease carb
      if (carbItem.recommendedQuantity > 1) {
        carbItem.recommendedQuantity -= (carbItem.unit === "piece" ? 1 : 0.5);
        carbItem.reason += " (Reduced for calorie deficit)";
        currentCalories -= (carbItem.estimatedCalories / carbItem.recommendedQuantity) * (carbItem.unit === "piece" ? 1 : 0.5);
      }
    }
  }

  // 5. Construct Groups
  const optionalItems = limits.map(l => ({ item: l.name, reason: "High calorie/sugar - consume in moderation" }))
    .concat(addons.slice(1).map(a => ({ item: a.name, reason: "Optional extra" })));

  const avoidOrLimit = limits.map(l => ({ item: l.name, reason: "Limit frequency" }));

  return {
    mealType: type,
    recommendedPlate: plate,
    optionalItems: optionalItems.filter(o => !plate.find(p => p.item === o.item)), // Don't list if already on plate
    avoidOrLimit: avoidOrLimit,
    summary: {
      dailyCalories: dailyCalories,
      targetMealCalories: Math.round(targetCalories),
      totalPlateCalories: Math.round(currentCalories),
      plateLogic: `Balanced plate for ${type} aligned with ${user.goal} goal.`,
      notes: "Portions are estimates. Adjust according to hunger."
    }
  };
}

module.exports = { recommendPlate };

