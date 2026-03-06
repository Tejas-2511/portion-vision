const fs = require("fs");
const path = require("path");

// ==========================================
// 1. Data & Helpers
// ==========================================

// Load food database
const { normalizeFoodName } = require("./utils/normalize");
const { fuzzyMatchFood } = require("./utils/fuzzyMatch");

// Load food database & Create Index
let FOOD_DB = [];
let FOOD_INDEX = new Map(); // O(1) Lookup

try {
  const dbPath = path.join(__dirname, "data", "foodDatabase.json");
  if (fs.existsSync(dbPath)) {
    FOOD_DB = JSON.parse(fs.readFileSync(dbPath, "utf8"));

    // Build Index
    FOOD_DB.forEach(item => {
      if (item.name) {
        FOOD_INDEX.set(normalizeFoodName(item.name), item);
      }
    });
    // console.log(`✅ Indexed ${FOOD_INDEX.size} unique food items.`);
  }
} catch (err) {
  console.error("Error reading food database:", err);
}

// Helper to find food in DB (Normalized O(1) + Fuzzy)
function findFood(name) {
  const normalized = normalizeFoodName(name);
  let match = FOOD_INDEX.get(normalized);
  if (match) return match;

  // Fallback to fuzzy match
  return fuzzyMatchFood(normalized, FOOD_DB);
}

// Fallback logic if food not in DB
function getFallbackDetails(name) {
  const n = name.toLowerCase();

  if (n.includes("biryani") || n.includes("pulao") || n.includes("fried rice") || n.includes("khichdi"))
    return { category: "carb_base", meal_role: "mixed", unit_type: "bowl", serving_size: 250, calories: 300, protein: 10, dish_type: "biryani", tags: [] };

  if (n.includes("rice"))
    return { category: "carb_base", unit_type: "bowl", serving_size: 200, calories: 250, protein: 5, dish_type: "rice", tags: [] };
  if (n.includes("roti") || n.includes("chapati") || n.includes("naan") || n.includes("paratha") || n.includes("bread"))
    return { category: "carb_base", unit_type: "piece", serving_size: 50, calories: 100, protein: 3, dish_type: "roti", tags: [] };

  if (n.includes("chicken") || n.includes("egg") || n.includes("fish") || n.includes("paneer"))
    return { category: "protein_main", unit_type: "bowl", serving_size: 150, calories: 220, protein: 15, protein_level: "high", dish_type: "curry", tags: [] };

  if (n.includes("dal") || n.includes("sambar") || n.includes("rajma") || n.includes("chole"))
    return { category: "protein_main", unit_type: "bowl", serving_size: 150, calories: 180, protein: 10, protein_level: "medium", dish_type: "dal", tags: [] };

  if (n.includes("sabji") || n.includes("fry") || n.includes("poriyal") || n.includes("bhaji"))
    return { category: "side", unit_type: "bowl", serving_size: 150, calories: 140, protein: 3, dish_type: "sabji", tags: [] };

  if (n.includes("salad") || n.includes("raita") || n.includes("curd"))
    return { category: "side", unit_type: "bowl", serving_size: 100, calories: 80, protein: 2, dish_type: "salad", tags: [] };

  if (n.includes("sweet") || n.includes("halwa") || n.includes("jamun") || n.includes("laddu"))
    return { category: "dessert", unit_type: "piece", serving_size: 50, calories: 200, protein: 2, dish_type: "sweet", tags: [] };

  // Default generic
  return { category: "side", unit_type: "serving", serving_size: 100, calories: 150, protein: 2, dish_type: "generic", tags: [] };
}

// ==========================================
// 2. Core Logic: Classify & Select
// ==========================================

function classifyItem(foodName) {
  let dbItem = findFood(foodName);

  // dbItem.name might be the matched food (e.g. "roti"), but the menu item was "rotii".
  // We want to return the database details, but preserve the menu item's original name
  // so the frontend recommendation displays what was on the menu.

  let details = dbItem ? { ...dbItem, name: foodName } : { name: foodName, ...getFallbackDetails(foodName) };

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

  // 4. Special Override: Papad/Fryums/Pickle -> Limit/Addon
  if (foodName.toLowerCase().includes("papad") || foodName.toLowerCase().includes("fryum") || foodName.toLowerCase().includes("pickle")) {
    role = "addon"; // Or limit, but addon fits plate side logic better
  }

  // 5. Green Chilli Fry -> Addon (Not Veg Side)
  if (foodName.toLowerCase().includes("chilli fry")) {
    role = "addon";
  }

  // 6. Condiments -> Addon
  if (details.category === "condiment") {
    role = "addon";
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

  if (goal.includes("lose") || goal.includes("fat")) tdee -= 400; // Deficit
  if (goal.includes("gain") || goal.includes("muscle")) tdee += 300; // Surplus

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

  let proteinPriority = "medium";
  if (user.goal && (user.goal.includes("gain") || user.goal.includes("muscle"))) proteinPriority = "high";

  // If there's a menu provided, filter FOOD_DB to only those items
  const safeMenu = Array.isArray(menuItems) ? menuItems : [];
  let availableFoods = FOOD_DB;

  if (safeMenu.length > 0) {
    availableFoods = safeMenu.map(name => {
      let dbItem = findFood(name);
      return dbItem ? { ...dbItem, name } : { name, ...getFallbackDetails(name) };
    });
  }

  // Generate combos using the new engine
  const combos = generateCombinations(availableFoods, targetCalories);
  let bestMeal = selectBestMeal(combos, targetCalories, proteinPriority);

  // If the strict combo fails because the menu is too small, fallback to creating a basic plate
  if (!bestMeal) {
    // We could write a small fallback here, but for now just take the best partial if any
    if (combos.length > 0) {
      bestMeal = combos.sort((a, b) => b.totalProtein - a.totalProtein)[0];
    }
  }

  if (!bestMeal) {
    return {
      mealType: type,
      recommendedPlate: [],
      optionalItems: [],
      avoidOrLimit: [],
      summary: {
        dailyCalories,
        targetMealCalories: Math.round(targetCalories),
        totalPlateCalories: 0,
        plateLogic: `Could not build a balanced meal with the available items.`,
        notes: "Try adding more variety."
      }
    };
  }

  // Map to the frontend structure
  const recommendedPlate = bestMeal.items.map(item => {
    // Map category to role for icons
    let role = "other";
    if (item.category === "carb_base") role = "carb";
    else if (item.category === "protein_main") role = "protein";
    else if (item.category === "side") role = "veg";

    return {
      item: item.name,
      dish_type: item.dish_type,
      role: role,
      recommendedQuantity: item.quantity,
      unit: item.unit_type || "serving",
      serving_size: item.serving_size,
      totalGrams: item.grams,
      estimatedCalories: item.calories,
      protein: item.protein,
      reason: role === 'protein' ? "Muscle Repair & Satiety" : role === 'carb' ? "Sustained Energy" : "Fiber & Vitamins",
      icon: getIconForRole(role)
    };
  });

  // Extract optional addons from available foods that weren't selected
  const selectedNames = bestMeal.items.map(i => i.name);
  const addons = availableFoods.filter(f => f.category === "condiment" || (f.tags && (f.tags.includes("pickle") || f.tags.includes("chutney") || f.tags.includes("papad"))));
  const bevs = availableFoods.filter(f => f.category === "beverage" && !selectedNames.includes(f.name));
  const sweets = availableFoods.filter(f => f.category === "dessert" && !selectedNames.includes(f.name));

  const optionalItems = [...addons.slice(0, 2), ...bevs.slice(0, 1), ...sweets.slice(0, 1)].map(opt => ({
    item: opt.name,
    calories: opt.calories || 0,
    note: "Consume in moderation",
    limit: opt.serving_size ? `~${opt.serving_size}${opt.serving_unit}` : "1 portion"
  }));

  return {
    mealType: type,
    recommendedPlate: recommendedPlate,
    optionalItems: optionalItems,
    avoidOrLimit: [],
    summary: {
      dailyCalories: dailyCalories,
      targetMealCalories: Math.round(targetCalories),
      totalPlateCalories: Math.round(bestMeal.totalCalories),
      totalPlateProtein: Math.round(bestMeal.totalProtein),
      plateLogic: `Balanced plate tailored for ${Math.round(targetCalories)} kcal.`,
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

// ==========================================
// NEW: Complete Rule-Based Meal Recommendation Engine
// ==========================================

function filterFoods(foods, targetDiet, avoidTags) {
  return foods.filter(food => {
    // 1. Filter veg = true if diet is veg
    if (targetDiet === "veg" && food.veg === false) return false;

    // 2. Remove foods that contain any avoidTags
    if (avoidTags && avoidTags.length > 0 && food.tags) {
      const lowerTags = food.tags.map(t => t.toLowerCase());
      const hasAvoidTag = avoidTags.some(tag => lowerTags.includes(tag.toLowerCase()));
      if (hasAvoidTag) return false;
    }

    return true;
  });
}

function generateCombinations(filteredFoods, targetCalories) {
  const rotis = filteredFoods.filter(f => f.category === "carb_base" && f.dish_type === "roti");
  const rices = filteredFoods.filter(f => f.category === "carb_base" && (f.dish_type === "rice" || f.dish_type === "biryani"));
  const otherCarbs = filteredFoods.filter(f => f.category === "carb_base" && f.dish_type !== "roti" && f.dish_type !== "rice" && f.dish_type !== "biryani");

  const proteins = filteredFoods.filter(f => f.category === "protein_main");
  const sides = filteredFoods.filter(f => f.category === "side" || f.dish_type === "sabji");

  const addons = filteredFoods.filter(f => f.category === "condiment" || (f.tags && (f.tags.includes("pickle") || f.tags.includes("chutney") || f.tags.includes("papad"))));
  const bevs = filteredFoods.filter(f => f.category === "beverage");
  const sweets = filteredFoods.filter(f => f.category === "dessert");

  const getScaledItem = (item, qty) => ({
    ...item,
    quantity: qty,
    grams: Math.round((item.serving_size || 100) * qty),
    calories: Math.round(item.calories * qty),
    protein: Math.round(item.protein * qty * 10) / 10
  });

  const combos = [];
  const MAX_CALORIES = targetCalories * 1.35;

  const addCombo = (items) => {
    let totalCals = 0; let totalProt = 0;
    items.forEach(i => { totalCals += i.calories; totalProt += i.protein; });
    if (totalCals > MAX_CALORIES) return;

    combos.push({ items: [...items], totalCalories: totalCals, totalProtein: Math.round(totalProt * 10) / 10 });
  };

  const topRotis = rotis.length > 0 ? rotis.slice(0, 3) : [null];
  const topRices = rices.length > 0 ? rices.slice(0, 3) : [null];
  const topProts = proteins.length > 0 ? proteins.slice(0, 3) : [null];
  const topSides = sides.length > 0 ? sides.slice(0, 3) : [null];

  topRotis.forEach(roti => {
    const rotiQtys = roti ? [1, 2, 3] : [0];
    rotiQtys.forEach(rotiQty => {
      topRices.forEach(rice => {
        const riceQtys = rice ? [0.5, 1] : [0];
        riceQtys.forEach(riceQty => {
          topProts.forEach(p => {
            topSides.forEach(s => {
              const items = [];
              if (roti) items.push(getScaledItem(roti, rotiQty));
              if (rice) items.push(getScaledItem(rice, riceQty));
              if (p) items.push(getScaledItem(p, 1));
              if (s) items.push(getScaledItem(s, 1));
              if (items.length > 0) addCombo(items);
            });
          });
        });
      });
    });
  });

  const allCarbs = [...rotis, ...rices, ...otherCarbs].slice(0, 5);
  const loopCarbs = allCarbs.length > 0 ? allCarbs : [null];
  const loopProts = proteins.length > 0 ? proteins.slice(0, 4) : [null];
  const loopSides = sides.length > 0 ? sides.slice(0, 4) : [null];

  loopCarbs.forEach(c => {
    const cQtys = c ? [1, 2, 3] : [0];
    cQtys.forEach(cQty => {
      loopProts.forEach(p => {
        const pQtys = p ? [1, 1.5, 2] : [0];
        pQtys.forEach(pQty => {
          loopSides.forEach(s => {
            const items = [];
            if (c) items.push(getScaledItem(c, cQty));
            if (p) items.push(getScaledItem(p, pQty));
            if (s) items.push(getScaledItem(s, 1));
            if (items.length > 0) addCombo(items);
          });
        });
      });
    });
  });

  return combos;
}

function scoreMeal(combo, targetCalories, proteinPriority) {
  let score = 0;

  // 1. Protein Priority Scoring
  combo.items.forEach(item => {
    if (proteinPriority === "high") {
      if (item.protein_level === "high") score += 5;
      else if (item.protein_level === "medium") score += 3;
    } else if (proteinPriority === "medium") {
      if (item.protein_level === "medium") score += 3;
      else if (item.protein_level === "high") score += 2;
    }
  });

  // 2. Full Thali Bonus (Roti + Rice + Protein + Veg)
  const hasRoti = combo.items.some(i => i.dish_type === "roti");
  const hasRice = combo.items.some(i => i.dish_type === "rice");
  const hasDal = combo.items.some(i => i.dish_type === "dal" || i.category === "protein_main");
  const hasSabji = combo.items.some(i => i.category === "side");

  if (hasRoti && hasRice) score += 5;
  if (hasDal && hasSabji) score += 5;

  score += combo.items.length * 2; // Variety bonus

  // 3. Calorie Balance Scoring
  const calorieDiff = Math.abs(combo.totalCalories - targetCalories);
  score -= (calorieDiff / targetCalories) * 15;

  if (combo.totalCalories > targetCalories * 1.1) {
    score -= 10;
  }

  return score;
}

function selectBestMeal(combos, targetCalories, proteinPriority) {
  let bestMeal = null;
  let bestScore = -Infinity;

  const minTarget = targetCalories * 0.9;
  const maxTarget = targetCalories * 1.1;

  for (const combo of combos) {
    // strict ±10% bounding
    if (combo.totalCalories >= minTarget && combo.totalCalories <= maxTarget) {
      const currentScore = scoreMeal(combo, targetCalories, proteinPriority);
      if (currentScore > bestScore) {
        bestScore = currentScore;
        bestMeal = combo;
      }
    }
  }

  // Fallback: If no meal hits ±10%, return the best scoring overall meal anyway
  if (!bestMeal && combos.length > 0) {
    for (const combo of combos) {
      const currentScore = scoreMeal(combo, targetCalories, proteinPriority);
      if (currentScore > bestScore) {
        bestScore = currentScore;
        bestMeal = combo;
      }
    }
  }

  return bestMeal;
}

// Validation middleware
const validateRecommendRequest = (req, res, next) => {
  const { targetCalories, proteinPriority, diet, mealType } = req.body;
  if (!targetCalories || typeof targetCalories !== "number") {
    return res.status(400).json({ error: "targetCalories must be a valid number" });
  }
  if (!["low", "medium", "high"].includes(proteinPriority)) {
    return res.status(400).json({ error: 'proteinPriority must be "low", "medium", or "high"' });
  }
  if (!["veg", "non-veg"].includes(diet)) {
    return res.status(400).json({ error: 'diet must be "veg" or "non-veg"' });
  }
  if (!["breakfast", "lunch", "dinner"].includes(mealType)) {
    return res.status(400).json({ error: 'mealType must be "breakfast", "lunch", or "dinner"' });
  }
  next();
};

// Express endpoint logic
const recommendEngineHandler = (req, res) => {
  const { targetCalories, proteinPriority, diet, avoidTags, mealType } = req.body;

  // Clean tags
  const tagsToAvoid = Array.isArray(avoidTags) ? avoidTags : [];

  // Filter & Generate
  const filtered = filterFoods(FOOD_DB, diet, tagsToAvoid);
  const combos = generateCombinations(filtered, targetCalories);
  const bestMeal = selectBestMeal(combos, targetCalories, proteinPriority);

  if (!bestMeal) {
    return res.status(404).json({ error: "No valid meal combination found" });
  }

  // Capitalize items for display
  const capitalize = s => s.charAt(0).toUpperCase() + s.slice(1);
  const mealName = bestMeal.items.map(i => capitalize(i.name)).join(" + ");

  const addons = filtered.filter(f => f.category === "condiment" || (f.tags && (f.tags.includes("pickle") || f.tags.includes("chutney") || f.tags.includes("papad"))));
  const bevs = filtered.filter(f => f.category === "beverage");
  const sweets = filtered.filter(f => f.category === "dessert");

  const response = {
    mealName,
    totalCalories: bestMeal.totalCalories,
    totalProtein: bestMeal.totalProtein,
    items: bestMeal.items.map(i => ({
      name: i.name,
      category: i.category,
      calories: i.calories,
      protein: i.protein,
      grams: i.grams,
      quantity: i.quantity,
      serving_size: i.serving_size,
      serving_unit: i.serving_unit,
      unit_type: i.unit_type
    })),
    optionalAddons: {
      sides: addons.slice(0, 3).map(i => ({ name: i.name, calories: i.calories, grams: i.serving_size, unit: i.serving_unit })),
      beverages: bevs.slice(0, 3).map(i => ({ name: i.name, calories: i.calories, grams: i.serving_size, unit: i.serving_unit })),
      sweets: sweets.slice(0, 3).map(i => ({ name: i.name, calories: i.calories, grams: i.serving_size, unit: i.serving_unit }))
    }
  };

  res.json(response);
};

module.exports = {
  recommendPlate, estimateDailyCalories, classifyItem,
  // New Engine Functions
  filterFoods, generateCombinations, scoreMeal, selectBestMeal,
  validateRecommendRequest, recommendEngineHandler
};
