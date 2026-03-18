const fs = require("fs");
const path = require("path");

// ==========================================
// 1. Data & Helpers
// ==========================================

const { normalizeFoodName } = require("./utils/normalize");
const { fuzzyMatchFood } = require("./utils/fuzzyMatch");

// Load food database & Create Index
let FOOD_DB = [];
let FOOD_INDEX = new Map(); // O(1) Lookup

try {
  const dbPath = path.join(__dirname, "data", "foodDatabase.json");
  if (fs.existsSync(dbPath)) {
    const rawDB = JSON.parse(fs.readFileSync(dbPath, "utf8"));
    FOOD_DB = rawDB.map(item => {
      if (item.nutrition) {
        return {
          ...item,
          veg: item.diet === "veg",
          dish_type: item.dishType,
          serving_size: item.serving?.size,
          serving_unit: item.serving?.unit,
          unit_type: item.serving?.unitType,
          calories: item.nutrition.calories,
          protein: item.nutrition.protein,
          carbs: item.nutrition.carbs,
          fat: item.nutrition.fat,
          fiber: item.nutrition.fiber,
          protein_level: item.proteinLevel,
          meal_role: item.mealRole
        };
      }
      return item;
    });

    // Build Index
    FOOD_DB.forEach(item => {
      if (item.name) {
        FOOD_INDEX.set(normalizeFoodName(item.name), item);
      }
    });
  }
} catch (err) {
  console.error("Error reading food database:", err);
}

// Helper to find food in DB (Normalized O(1) + Fuzzy)
function findFood(name) {
  const normalized = normalizeFoodName(name);
  let match = FOOD_INDEX.get(normalized);
  if (match) return match;

  return fuzzyMatchFood(normalized, FOOD_DB, 2);
}

// Fallback logic if food not in DB — also used for OCR enrichment
function getFallbackDetails(name) {
  const n = name.toLowerCase();

  // ── One-pot mixed meals ──
  if (n.includes("biryani") || n.includes("pulao") || n.includes("fried rice") || n.includes("khichdi"))
    return { category: "carb_base", meal_role: "mixed", unit_type: "bowl", serving_size: 250, serving_unit: "g", calories: 300, protein: 10, carbs: 45, fat: 8, fiber: 3, dish_type: "biryani", meal_types: ["lunch", "dinner"], tags: [], veg: !n.includes("chicken") && !n.includes("mutton") && !n.includes("egg") };

  // ── Breakfast-specific items ──
  if (n.includes("poha") || n.includes("avalakki"))
    return { category: "carb_base", meal_role: "single", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 200, protein: 4, carbs: 35, fat: 5, fiber: 2, dish_type: "poha", meal_types: ["breakfast", "snack"], tags: ["veg"], veg: true };
  if (n.includes("upma"))
    return { category: "carb_base", meal_role: "single", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 190, protein: 5, carbs: 30, fat: 6, fiber: 2, dish_type: "upma", meal_types: ["breakfast", "snack"], tags: ["veg"], veg: true };
  if (n.includes("idli") || n.includes("dosa"))
    return { category: "carb_base", meal_role: "single", unit_type: "piece", serving_size: 40, serving_unit: "g", calories: 90, protein: 3, carbs: 18, fat: 1, fiber: 1, dish_type: "idli", meal_types: ["breakfast", "snack"], tags: ["veg"], veg: true };
  if (n.includes("oats") || n.includes("porridge"))
    return { category: "carb_base", meal_role: "single", unit_type: "bowl", serving_size: 200, serving_unit: "g", calories: 180, protein: 6, carbs: 32, fat: 4, fiber: 4, dish_type: "oats", meal_types: ["breakfast"], tags: ["veg"], veg: true };
  if (n.includes("sandwich") || n.includes("toast"))
    return { category: "carb_base", meal_role: "single", unit_type: "piece", serving_size: 80, serving_unit: "g", calories: 150, protein: 6, carbs: 22, fat: 5, fiber: 2, dish_type: "sandwich", meal_types: ["breakfast", "snack"], tags: ["veg"], veg: true };

  // ── Carbs ──
  if (n.includes("rice"))
    return { category: "carb_base", meal_role: "single", unit_type: "bowl", serving_size: 200, serving_unit: "g", calories: 250, protein: 5, carbs: 50, fat: 2, fiber: 1, dish_type: "rice", meal_types: ["lunch", "dinner"], tags: ["veg"], veg: true };
  if (n.includes("roti") || n.includes("chapati") || n.includes("naan") || n.includes("paratha") || n.includes("bread"))
    return { category: "carb_base", meal_role: "single", unit_type: "piece", serving_size: 40, serving_unit: "g", calories: 104, protein: 3, carbs: 20, fat: 1, fiber: 3, dish_type: "roti", meal_types: ["breakfast", "lunch", "dinner"], tags: ["veg"], veg: true };

  // ── Proteins ──
  if (n.includes("chicken"))
    return { category: "protein_main", meal_role: "single", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 280, protein: 25, carbs: 5, fat: 14, fiber: 1, protein_level: "high", dish_type: "curry", meal_types: ["lunch", "dinner"], tags: ["chicken", "non-veg"], veg: false };
  if (n.includes("egg"))
    return { category: "protein_main", meal_role: "single", unit_type: "piece", serving_size: 1, serving_unit: "piece", calories: 70, protein: 6, carbs: 1, fat: 5, fiber: 0, protein_level: "medium", dish_type: "egg", meal_types: ["breakfast", "lunch", "dinner"], tags: ["egg"], veg: false };
  if (n.includes("fish") || n.includes("prawn") || n.includes("mutton"))
    return { category: "protein_main", meal_role: "single", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 250, protein: 22, carbs: 3, fat: 14, fiber: 0, protein_level: "high", dish_type: "curry", meal_types: ["lunch", "dinner"], tags: ["non-veg"], veg: false };
  if (n.includes("paneer"))
    return { category: "protein_main", meal_role: "single", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 280, protein: 18, carbs: 5, fat: 20, fiber: 0, protein_level: "high", dish_type: "curry", meal_types: ["lunch", "dinner"], tags: ["dairy", "veg"], veg: true };
  if (n.includes("dal") || n.includes("sambar") || n.includes("rajma") || n.includes("chole") || n.includes("chana"))
    return { category: "protein_main", meal_role: "single", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 190, protein: 11, carbs: 30, fat: 4, fiber: 8, protein_level: "medium", dish_type: "dal", meal_types: ["lunch", "dinner"], tags: ["veg"], veg: true };
  if (n.includes("milk") || n.includes("lassi") || n.includes("chaas"))
    return { category: "beverage", meal_role: "single", unit_type: "glass", serving_size: 250, serving_unit: "ml", calories: 120, protein: 6, carbs: 12, fat: 4, fiber: 0, dish_type: "drink", meal_types: ["breakfast", "snack"], tags: ["dairy", "veg"], veg: true };

  // ── Sides ──
  if (n.includes("kofta") || n.includes("curry") || n.includes("masala") || n.includes("sabji") || n.includes("sabzi") || n.includes("fry") || n.includes("poriyal") || n.includes("bhaji") || n.includes("bhurji") || n.includes("tamatar") || n.includes("aloo") || n.includes("gobi") || n.includes("sev"))
    return { category: "side", meal_role: "single", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 140, protein: 4, carbs: 14, fat: 7, fiber: 4, dish_type: "sabji", meal_types: ["lunch", "dinner"], tags: ["veg"], veg: true };
  if (n.includes("salad"))
    return { category: "side", meal_role: "single", unit_type: "bowl", serving_size: 100, serving_unit: "g", calories: 60, protein: 2, carbs: 8, fat: 2, fiber: 4, dish_type: "salad", meal_types: ["breakfast", "lunch", "dinner", "snack"], tags: ["veg"], veg: true };
  if (n.includes("raita") || n.includes("curd") || n.includes("yogurt"))
    return { category: "side", meal_role: "single", unit_type: "bowl", serving_size: 100, serving_unit: "g", calories: 80, protein: 4, carbs: 8, fat: 2, fiber: 0, dish_type: "raita", meal_types: ["lunch", "dinner"], tags: ["dairy", "veg"], veg: true };

  // ── Desserts & Snacks ──
  if (n.includes("sweet") || n.includes("halwa") || n.includes("jamun") || n.includes("laddu") || n.includes("kheer") || n.includes("barfi") || n.includes("mithai"))
    return { category: "dessert", meal_role: "single", unit_type: "piece", serving_size: 50, serving_unit: "g", calories: 200, protein: 2, carbs: 30, fat: 8, fiber: 0, dish_type: "sweet", meal_types: ["lunch", "dinner", "snack"], tags: ["sweet", "veg"], veg: true };
  if (n.includes("fruit") || n.includes("banana") || n.includes("apple") || n.includes("orange"))
    return { category: "side", meal_role: "single", unit_type: "piece", serving_size: 120, serving_unit: "g", calories: 80, protein: 1, carbs: 18, fat: 0, fiber: 3, dish_type: "fruit", meal_types: ["breakfast", "snack"], tags: ["veg"], veg: true };

  // ── Condiments — tag garlic/onion items so Jain filter works ──
  if (n.includes("garlic chutney") || n.includes("lasun"))
    return { category: "condiment", meal_role: "single", unit_type: "tsp", serving_size: 10, serving_unit: "g", calories: 30, protein: 1, carbs: 4, fat: 1, fiber: 0, dish_type: "condiment", tags: ["garlic", "veg"], veg: true };
  if (n.includes("papad") || n.includes("pickle") || n.includes("chutney") || n.includes("sauce") || n.includes("achaar"))
    return { category: "condiment", meal_role: "single", unit_type: "tsp", serving_size: 10, serving_unit: "g", calories: 40, protein: 1, carbs: 5, fat: 2, fiber: 1, dish_type: "condiment", tags: ["veg"], veg: true };

  // Default generic side
  return { category: "side", meal_role: "single", unit_type: "serving", serving_size: 100, serving_unit: "g", calories: 150, protein: 3, carbs: 20, fat: 5, fiber: 2, dish_type: "generic", tags: ["veg"], veg: true };
}

// Guard: skip foods that have no calorie data (OCR stubs)
function isZeroCalorie(food) {
  return !food.calories || food.calories === 0;
}

// ==========================================
// 2. Diet Filtering
// ==========================================

// Diet preference definitions:
// "vegan"       - no animal products (no dairy, no egg, no meat)
// "jain"        - veg + no root vegetables (onion, garlic, potato, carrot, beet, etc.)
// "lacto-veg"   - veg + dairy OK, no egg/meat
// "ovo-veg"     - veg + egg OK, no meat/dairy
// "vegetarian"  - veg + dairy + egg OK
// "non-veg"     - all food allowed
const JAIN_AVOID_TAGS = ["potato", "onion", "garlic", "carrot", "beet", "radish", "turnip", "ginger"];
// Jain also avoids these name-level keywords (belt-and-suspenders for fallback items)
const JAIN_AVOID_NAMES = ["garlic", "onion", "potato", "aloo", "lasun", "pyaaz"];

function normalizeDiet(diet) {
  if (!diet) return "non-veg";
  const d = diet.toLowerCase().replace(/[-\s]/g, "");
  if (d.includes("jain")) return "jain";
  if (d.includes("vegan")) return "vegan";
  if (d.includes("lacto")) return "lacto-veg";
  if (d.includes("ovo")) return "ovo-veg";
  if (d.includes("nonveg") || d === "nonvegetarian") return "non-veg"; // must check before "vegetarian"
  if (d.includes("vegetarian") || d === "veg") return "vegetarian";
  return "non-veg";
}

// Returns true if the food contains actual meat (chicken, fish, mutton, seafood etc.)
// Used to distinguish meat from other animal products (egg, dairy) for diet filtering.
const MEAT_TAGS = ["chicken", "mutton", "fish", "prawn", "beef", "pork", "seafood"];

function isMeat(food) {
  const tags = (food.tags || []).map(t => t.toLowerCase());
  return MEAT_TAGS.some(t => tags.includes(t));
}
function isEgg(food) {
  return (food.tags || []).map(t => t.toLowerCase()).includes("egg");
}
function isDairy(food) {
  return (food.tags || []).map(t => t.toLowerCase()).some(t => ["dairy", "milk", "ghee", "butter"].includes(t));
}

function filterFoods(foods, dietPreference, avoidTags = []) {
  const diet = normalizeDiet(dietPreference);
  const allAvoidTags = [...avoidTags];
  if (diet === "jain") allAvoidTags.push(...JAIN_AVOID_TAGS);

  return foods.filter(food => {
    if (isZeroCalorie(food)) return false; // Never recommend zero-calorie stubs

    const tags = (food.tags || []).map(t => t.toLowerCase());

    if (diet === "vegan") {
      // No meat, no egg, no dairy
      if (isMeat(food) || isEgg(food) || isDairy(food)) return false;
      if (food.veg === false) return false;
    }
    else if (diet === "jain") {
      // Jain: no meat, no eggs — additional root vegetable tags applied via avoidTags below
      if (isMeat(food) || isEgg(food)) return false;
      if (food.veg === false) return false;
    }
    else if (diet === "lacto-veg") {
      // No meat, no egg; dairy OK
      if (isMeat(food) || isEgg(food)) return false;
      if (food.veg === false && !isDairy(food)) return false;
    }
    else if (diet === "ovo-veg") {
      // No meat, no dairy; egg OK
      if (isMeat(food)) return false;
      if (isDairy(food)) return false;
      if (food.veg === false && !isEgg(food)) return false;
    }
    else if (diet === "vegetarian") {
      // No meat; egg and dairy OK
      if (isMeat(food)) return false;
      // Allow items that are veg:false but are eggs or dairy (eggs, paneer, raita, etc.)
      if (food.veg === false && !isEgg(food) && !isDairy(food)) return false;
    }
    // "non-veg" — no restriction at all

    // Apply extra avoid-tags (allergies, jain root veg additions, etc.)
    if (allAvoidTags.length > 0) {
      const hasAvoidTag = allAvoidTags.some(tag => tags.includes(tag.toLowerCase()));
      if (hasAvoidTag) return false;
    }

    // Jain name-level guard: catch fallback items that lack tags
    if (diet === "jain") {
      const lowerName = (food.name || "").toLowerCase();
      if (JAIN_AVOID_NAMES.some(kw => lowerName.includes(kw))) return false;
    }

    return true;
  });
}

// ==========================================
// 3. Calorie & Macro Target Estimation
// ==========================================

function estimateDailyCalories(user) {
  const weight = parseFloat(user.weight_kg || user.weight) || 70;
  const height = parseFloat(user.height_cm || user.height) || 170;
  const age = parseInt(user.age) || 25;
  const sex = (user.sex || user.gender || "male").toLowerCase();
  const activityLevel = (user.activity_level || user.activityLevel || "moderate").toLowerCase();
  const goal = (user.goalType || user.goal || "maintain").toLowerCase();

  // Mifflin-St Jeor Equation
  const bmr = sex === "female"
    ? 10 * weight + 6.25 * height - 5 * age - 161
    : 10 * weight + 6.25 * height - 5 * age + 5;

  const activityMultipliers = {
    sedentary: 1.2,
    lightly: 1.375,
    light: 1.375,
    moderately: 1.55,
    moderate: 1.55,
    very: 1.725,
    active: 1.725
  };

  // Match the first meaningful word of the activity level
  const actKey = activityLevel.split(" ")[0];
  let tdee = bmr * (activityMultipliers[actKey] || 1.55);

  if (goal.includes("lose") || goal.includes("fat")) tdee -= 400;
  if (goal.includes("gain") || goal.includes("muscle")) tdee += 300;

  return Math.round(Math.max(1200, Math.min(4000, tdee)));
}

function computeMacroTargets(user, mealType) {
  const weight = parseFloat(user.weight_kg || user.weight) || 70;
  const goal = (user.goalType || user.goal || "maintain").toLowerCase();
  const dailyCalories = estimateDailyCalories(user);

  const mealFractions = {
    breakfast: 0.25,
    lunch: 0.35,
    dinner: 0.30,
    snack: 0.10
  };
  const mealFrac = mealFractions[(mealType || "lunch").toLowerCase()] || 0.33;
  const targetCalories = dailyCalories * mealFrac;

  // Protein factor by goal (g per kg body weight per day)
  let proteinFactor = 1.0; // maintain
  if (goal.includes("muscle") || goal.includes("gain")) proteinFactor = 2.0;
  else if (goal.includes("fat") || goal.includes("lose")) proteinFactor = 1.6;
  const dailyProtein = weight * proteinFactor;
  const targetProtein = dailyProtein * mealFrac;

  // Macro split: 45% carbs, 25% protein calories, 30% fat (standard balanced)
  const targetCarbsKcal = targetCalories * 0.45;
  const maxFatKcal = targetCalories * 0.35;

  return {
    dailyCalories,
    targetCalories: Math.round(targetCalories),
    targetProtein: Math.round(targetProtein),
    targetCarbs_g: Math.round(targetCarbsKcal / 4),
    maxFat_g: Math.round(maxFatKcal / 9),
    mealFrac,
    proteinPriority: proteinFactor >= 1.6 ? "high" : "medium"
  };
}

/**
 * Determines how many servings of a food item to recommend,
 * targeting a calorie or protein goal while staying within caps.
 * Returns integer or half-integer quantities depending on unit_type.
 * @param {object} food - The food item object
 * @param {number} targetCalPerItem - Max calories allowed for this item
 * @param {number} maxServings - Hard cap on quantity
 * @param {number} [maxFatPerItem=Infinity] - Hard cap on fat (g) for this item
 */
function calcServings(food, targetCalPerItem, maxServings = 4, maxFatPerItem = Infinity) {
  if (!food.calories || food.calories <= 0) return 1;
  const isDiscrete = ["piece", "roti", "paratha"].includes((food.unit_type || "").toLowerCase());

  // Base raw scale on calories
  let raw = targetCalPerItem / food.calories;

  // Constrain scale by fat limit if food has fat
  if (food.fat > 0 && (raw * food.fat) > maxFatPerItem) {
    raw = maxFatPerItem / food.fat;
  }

  if (isDiscrete) {
    return Math.max(1, Math.min(maxServings, Math.round(raw)));
  }
  // Allow 0.5 increments for bowls
  const snapped = Math.round(raw * 2) / 2;
  return Math.max(0.5, Math.min(maxServings, snapped));
}

function scaleItem(food, qty) {
  const cal = Math.round((food.calories || 0) * qty);
  const prot = Math.round((food.protein || 0) * qty * 10) / 10;
  const carbs = Math.round((food.carbs || 0) * qty * 10) / 10;
  const fat = Math.round((food.fat || 0) * qty * 10) / 10;
  const fiber = Math.round((food.fiber || 0) * qty * 10) / 10;
  const grams = Math.round((food.serving_size || 100) * qty);
  return { ...food, quantity: qty, estimatedCalories: cal, protein: prot, carbs, fat, fiber, grams };
}

function buildPlate({ user, menuItems, mealType, dietPreference, avoidTags }) {
  const macros = computeMacroTargets(user, mealType);
  const { targetCalories, targetProtein, targetCarbs_g, maxFat_g } = macros;
  const mt = (mealType || "lunch").toLowerCase();

  // 1. Resolve each menu item to its full food record
  const resolved = (menuItems || []).map(name => {
    const dbItem = findFood(name);
    return dbItem ? { ...dbItem, name } : { name, ...getFallbackDetails(name) };
  });

  // 2. Filter for diet + remove zero-calorie stubs
  const filtered = filterFoods(resolved, dietPreference || "non-veg", avoidTags || []);

  if (filtered.length === 0) {
    return {
      plate: [],
      optionals: [],
      macros,
      notes: "No suitable items found for your dietary preference on today's menu."
    };
  }

  // Partition into roles
  // mealRole: "mixed" = complete one-pot meal (biryani, khichdi); "single" = individual component
  const mixed    = filtered.filter(f => f.meal_role === "mixed");
  const proteins = filtered.filter(f => f.category === "protein_main");
  const carbsRoti  = filtered.filter(f => f.category === "carb_base" && f.dish_type === "roti");
  const carbsRice  = filtered.filter(f => f.category === "carb_base" && (f.dish_type === "rice" || f.dish_type === "biryani"));
  const carbsBreakfast = filtered.filter(f => f.category === "carb_base" && ["poha", "upma", "idli", "oats", "sandwich"].includes(f.dish_type || ""));
  const carbsOther = filtered.filter(f => f.category === "carb_base" && !["roti", "rice", "biryani", "poha", "upma", "idli", "oats", "sandwich"].includes(f.dish_type || ""));
  const allCarbs = [...carbsRoti, ...carbsRice, ...carbsBreakfast, ...carbsOther];
  // Salads always go on the plate — separate them from regular sides
  const salads   = filtered.filter(f => f.category === "side" && f.dish_type === "salad");
  const sides    = filtered.filter(f => f.category === "side" && f.dish_type !== "salad");
  const condiments = filtered.filter(f => f.category === "condiment" || f.dish_type === "condiment" || f.name.toLowerCase().includes("papad") || f.name.toLowerCase().includes("pickle") || f.name.toLowerCase().includes("chutney"));
  const beverages  = filtered.filter(f => f.category === "beverage");
  const desserts   = filtered.filter(f => f.category === "dessert");

  const plate = [];
  let caloriesUsed = 0;

  // ── Phase 0a: Snack fast-path — light, simple, no full meal logic ──
  if (mt === "snack") {
    // For snacks just pick 1-2 suitable items within calorie budget
    const snackCandidates = [...carbsBreakfast, ...carbsRoti, ...carbsOther, ...proteins, ...sides]
      .filter(f => f.calories && f.calories <= targetCalories);
    snackCandidates.sort((a, b) => (b.protein || 0) - (a.protein || 0));
    let snackBudget = targetCalories;
    for (const candidate of snackCandidates.slice(0, 2)) {
      if (snackBudget < 40) break;
      const qty = calcServings(candidate, snackBudget, 2);
      const item = scaleItem(candidate, qty);
      plate.push({ ...item, role: candidate.category === "protein_main" ? "protein" : "carb", reason: "Light snack" });
      snackBudget -= item.estimatedCalories;
    }
    if (salads.length > 0) plate.push({ ...scaleItem(salads[0], 1), role: "veg", reason: "Fresh & light" });
    return buildResponse(plate, condiments, beverages, desserts, macros);
  }

  // ── Phase 0b: Mixed meal fast-path (biryani, khichdi etc. — mealRole:"mixed") ──
  if (mixed.length > 0) {
    // Pick the highest-protein mixed item
    const best = [...mixed].sort((a, b) => (b.protein || 0) - (a.protein || 0))[0];
    const qty = calcServings(best, targetCalories, 3);
    const item = scaleItem(best, qty);
    caloriesUsed += item.estimatedCalories;
    plate.push({ ...item, role: "mixed", reason: "Complete balanced meal" });

    // Optionally add a side if calories allow
    if (sides.length > 0 && caloriesUsed < targetCalories * 0.95) {
      const side = [...sides].sort((a, b) => (b.fiber || 0) - (a.fiber || 0))[0];
      plate.push({ ...scaleItem(side, 1), role: "veg", reason: "Fiber & vitamins" });
    }

    // Always add salad(s) if present
    salads.forEach(salad => {
      plate.push({ ...scaleItem(salad, 1), role: "veg", reason: "Fresh greens & micronutrients" });
    });

    return buildResponse(plate, condiments, beverages, desserts, macros);
  }

  // ── Phase 0c: Breakfast fast-path — lighter carbs first, protein optional ──
  if (mt === "breakfast") {
    // Prefer breakfast-specific carbs (poha, upma, idli, oats, sandwich)
    const bfCarbs = carbsBreakfast.length > 0 ? carbsBreakfast : [...carbsRoti, ...carbsOther];
    if (bfCarbs.length > 0) {
      const bfItem = bfCarbs[0];
      const qty = calcServings(bfItem, targetCalories * 0.55, 2);
      const item = scaleItem(bfItem, qty);
      caloriesUsed += item.estimatedCalories;
      plate.push({ ...item, role: "carb", reason: "Breakfast energy" });
    }
    // Add a protein if budget allows and protein source available
    if (proteins.length > 0 && caloriesUsed < targetCalories * 0.80) {
      const pfood = [...proteins].sort((a, b) => (b.protein || 0) - (a.protein || 0))[0];
      const pqty = calcServings(pfood, targetCalories * 0.35, 1.5);
      const pitem = scaleItem(pfood, pqty);
      caloriesUsed += pitem.estimatedCalories;
      plate.push({ ...pitem, role: "protein", reason: "Morning protein" });
    }
    // Salads & beverages
    if (beverages.length > 0) plate.push({ ...scaleItem(beverages[0], 1), role: "addon", reason: "Hydration" });
    salads.forEach(salad => plate.push({ ...scaleItem(salad, 1), role: "veg", reason: "Fresh greens" }));
    return buildResponse(plate, condiments, beverages, desserts, macros);
  }

  // ── Phase 1: High-Fiber Vegetables (Strict Enforcement) ──
  // Always reserve calories for a vegetable to ensure a balanced diet
  let reservedVegCalories = 0;
  let primarySide = null;

  if (sides.length > 0) {
    // Pick the highest-fiber side
    primarySide = sides.sort((a, b) => (b.fiber || 0) - (a.fiber || 0))[0];

    // We strictly reserve the exact baseline calories needed for 1 serving (up to 150 kcal limit so it doesn't starve protein)
    reservedVegCalories = Math.min(primarySide.calories || 100, 150);
  }

  // ── Phase 2: Protein ──
  // Sort by protein-per-calorie efficiency DESC
  const sortedProteins = proteins
    .filter(f => f.calories > 0)
    .sort((a, b) => (b.protein / b.calories) - (a.protein / a.calories));

  let proteinCalBudget = (targetCalories - reservedVegCalories) * 0.40; // up to 40% of remaining for protein
  const fatPerProteinItem = maxFat_g * 0.50; // Don't let a single protein item eat more than 50% of meal's fat
  let proteinAccum = 0;

  if (sortedProteins.length > 0) {
    const primary = sortedProteins[0];
    // How many servings to hit 50% of meal protein target from this single source
    const servingsForProtein = targetProtein * 0.50 / (primary.protein || 1);
    const servingsForCal = proteinCalBudget / primary.calories;
    const qty = calcServings(
      primary,
      Math.min(servingsForProtein, servingsForCal) * primary.calories,
      1.5, // Force variety by capping primary protein to 1.5 bowls
      fatPerProteinItem
    );
    const item = scaleItem(primary, qty);
    caloriesUsed += item.estimatedCalories;
    proteinAccum += item.protein;
    plate.push({ ...item, role: "protein", reason: "Muscle repair & satiety" });

    // If still under protein target and second protein source available
    if (proteinAccum < targetProtein * 0.6 && sortedProteins.length > 1) {
      const secondary = sortedProteins[1];
      const remaining = Math.min(proteinCalBudget - item.estimatedCalories, (targetCalories - reservedVegCalories) * 0.15);
      if (remaining > 50) {
        const qty2 = calcServings(secondary, remaining, 1, fatPerProteinItem); // Cap secondary to 1 bowl
        const item2 = scaleItem(secondary, qty2);
        caloriesUsed += item2.estimatedCalories;
        proteinAccum += item2.protein;
        plate.push({ ...item2, role: "protein", reason: "Additional protein boost" });
      }
    }
  }

  // ── Phase 3: Carbohydrates ──
  let calRemaining = targetCalories - caloriesUsed - reservedVegCalories;
  const carbTarget = Math.max(calRemaining, 0);
  const fatForCarbs = maxFat_g * 0.30;

  if (allCarbs.length > 0 && carbTarget > 50) {
    let carbSource = null;
    let addSecondaryCarb = false;
    let primaryTarget = carbTarget;

    if (carbsRoti.length > 0 && carbsRice.length > 0) {
      if (carbTarget > 300) {
        // High calorie needs -> split between roti and rice
        addSecondaryCarb = true;
        carbSource = carbsRoti[0];
        primaryTarget = carbTarget * 0.4;
      } else {
        carbSource = carbTarget < 350 ? carbsRoti[0] : carbsRice[0];
      }
    } else if (carbsRoti.length > 0) {
      carbSource = carbsRoti[0];
    } else if (carbsRice.length > 0) {
      carbSource = carbsRice[0];
    } else {
      carbSource = carbsOther[0];
    }

    const maxPrimary = carbSource.dish_type === "roti" ? 3 : 1.5; // Cap rotis at 3, rice at 1.5
    const qty = calcServings(carbSource, primaryTarget, maxPrimary, fatForCarbs);
    const item = scaleItem(carbSource, qty);
    caloriesUsed += item.estimatedCalories;
    plate.push({ ...item, role: "carb", reason: "Sustained energy & fuel" });

    if (addSecondaryCarb) {
      const remainingCarbTarget = carbTarget - item.estimatedCalories;
      if (remainingCarbTarget > 50) {
        const qty2 = calcServings(carbsRice[0], remainingCarbTarget, 1.5, fatForCarbs);
        const item2 = scaleItem(carbsRice[0], qty2);
        caloriesUsed += item2.estimatedCalories;
        plate.push({ ...item2, role: "carb", reason: "Variety & energy" });
      }
    }
  }

  // ── Phase 4: Finalize Reserved Vegetable Side ──
  if (primarySide) {
    // We already reserved calories, but let's see if there are even MORE calories remaining to allow a larger side portion
    const actualRemaining = targetCalories - caloriesUsed;
    const finalVegBudget = Math.max(reservedVegCalories, actualRemaining); // Use whatever is larger

    // Calculate servings without fat bottleneck for vegetables (usually low fat anyway)
    const qty = calcServings(primarySide, Math.min(finalVegBudget * 0.60, primarySide.calories * 1.5), 2);
    const item = scaleItem(primarySide, Math.max(1, qty)); // Guarantee at least 1 serving
    caloriesUsed += item.estimatedCalories;
    plate.push({ ...item, role: "veg", reason: "Required fiber, vitamins & minerals" });
  }

  // ── Phase 4: Validate & adjust ──
  // If over budget by >10%, trim 1 unit off the carb item
  if (caloriesUsed > targetCalories * 1.12) {
    const carbIdx = plate.findIndex(p => p.role === "carb");
    if (carbIdx >= 0 && plate[carbIdx].quantity > 0.5) {
      const f = plate[carbIdx];
      const isDiscrete = ["piece", "roti", "paratha"].includes((f.unit_type || "").toLowerCase());
      const reduction = isDiscrete ? 1 : 0.5;
      const newQty = Math.max(0.5, f.quantity - reduction);
      const updated = scaleItem(f, newQty);
      caloriesUsed = caloriesUsed - f.estimatedCalories + updated.estimatedCalories;
      plate[carbIdx] = { ...updated, role: "carb", reason: f.reason };
    }
  }

  // If well under budget (<80%), try to add a second side or bump carb
  if (caloriesUsed < targetCalories * 0.80 && sides.length > 1) {
    const alreadyUsedSide = plate.find(p => p.role === "veg");
    const extraSide = sides.find(s => s.name !== (alreadyUsedSide ? alreadyUsedSide.name : ""));
    if (extraSide) {
      const item = scaleItem(extraSide, 1);
      caloriesUsed += item.estimatedCalories;
      plate.push({ ...item, role: "veg", reason: "Fiber & variety" });
    }
  }

  // Always add salads to the plate — they're low calorie and always beneficial
  salads.forEach(salad => {
    plate.push({ ...scaleItem(salad, 1), role: "veg", reason: "Fresh greens & micronutrients" });
  });

  return buildResponse(plate, condiments, beverages, desserts, macros);
}

function buildResponse(plate, condiments, beverages, desserts, macros) {
  const totalCalories = Math.round(plate.reduce((sum, i) => sum + (i.estimatedCalories || 0), 0));
  const totalProtein = Math.round(plate.reduce((sum, i) => sum + (i.protein || 0), 0) * 10) / 10;
  const totalCarbs = Math.round(plate.reduce((sum, i) => sum + (i.carbs || 0), 0) * 10) / 10;
  const totalFat = Math.round(plate.reduce((sum, i) => sum + (i.fat || 0), 0) * 10) / 10;

  const optionals = [
    ...condiments.slice(0, 3).map(f => ({ item: f.name, calories: f.calories || 0, note: "Condiment — small amount", limit: `~${f.serving_size || 10}${f.serving_unit || "g"}` })),
    ...beverages.slice(0, 1).map(f => ({ item: f.name, calories: f.calories || 0, note: "Hydration", limit: `1 ${f.unit_type || "glass"}` })),
    ...desserts.slice(0, 1).map(f => ({ item: f.name, calories: f.calories || 0, note: "Treat — consume in moderation", limit: `~${f.serving_size || 50}${f.serving_unit || "g"}` }))
  ];

  return { plate, optionals, macros: { ...macros, totalCalories, totalProtein, totalCarbs, totalFat } };
}

// ==========================================
// 5. Public API: recommendPlate()
// ==========================================

function recommendPlate({ user, menuItems, mealType }) {
  const dietPreference = user.dietPreference || user.diet || "non-veg";
  const avoidTags = user.avoidTags || [];
  const mt = (mealType || "lunch").toLowerCase();

  const result = buildPlate({ user, menuItems, mealType, dietPreference, avoidTags });

  // Map to frontend-expected shape
  const recommendedPlate = result.plate.map(item => ({
    item: item.name,
    dish_type: item.dish_type,
    role: item.role,
    recommendedQuantity: item.quantity,
    unit: item.unit_type || "serving",
    serving_size: item.serving_size,
    totalGrams: item.grams,
    estimatedCalories: item.estimatedCalories,
    protein: item.protein,
    carbs: item.carbs,
    fat: item.fat,
    fiber: item.fiber,
    reason: item.reason,
    icon: getIconForRole(item.role)
  }));

  const macros = result.macros;

  // Meal-type contextual notes
  const mealLogicMap = {
    breakfast: `Light ${macros.targetCalories} kcal breakfast — gentle start to the day.`,
    lunch:     `Balanced ${macros.targetCalories} kcal lunch targeting ${macros.targetProtein}g protein.`,
    dinner:    `Light-to-moderate ${macros.targetCalories} kcal dinner — easy on digestion.`,
    snack:     `Quick ${macros.targetCalories} kcal snack — keep it light between meals.`,
  };
  const plateLogic = mealLogicMap[mt] || `${macros.targetCalories} kcal plate targeting ${macros.targetProtein}g protein.`;

  // Diet-specific guidance note
  const dietNoteMap = {
    jain:        "Jain-friendly: root vegetables & garlic excluded.",
    vegan:       "Vegan: all animal products excluded.",
    "lacto-veg": "Lacto-vegetarian: dairy included, no eggs or meat.",
    "ovo-veg":   "Ovo-vegetarian: eggs included, no dairy or meat.",
    vegetarian:  "Vegetarian: dairy & eggs OK, no meat.",
  };
  const normalizedDiet = normalizeDiet(dietPreference);
  const dietNote = dietNoteMap[normalizedDiet] || "";

  return {
    mealType: mt,
    dietPreference: normalizedDiet,
    recommendedPlate,
    optionalItems: result.optionals,
    avoidOrLimit: [],
    summary: {
      dailyCalories: macros.dailyCalories,
      targetMealCalories: macros.targetCalories,
      totalPlateCalories: macros.totalCalories,
      totalPlateProtein: macros.totalProtein,
      totalPlateCarbs: macros.totalCarbs,
      totalPlateFat: macros.totalFat,
      targetProtein: macros.targetProtein,
      plateLogic,
      dietNote,
      notes: result.notes || "Portions are estimates based on standard serving sizes."
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
// 6. Classify helper (unchanged — used by other parts)
// ==========================================

function classifyItem(foodName) {
  let dbItem = findFood(foodName);
  let details = dbItem ? { ...dbItem, name: foodName } : { name: foodName, ...getFallbackDetails(foodName) };

  let role = "other";
  if (details.meal_role === "mixed") {
    role = "mixed";
  } else {
    if (details.category === "protein_main" && details.protein_level === "low") {
      role = "side";
    } else if (details.category === "dessert" || (details.tags && details.tags.includes("sweet"))) {
      role = "limit";
    } else {
      switch (details.category) {
        case "carb_base": role = "carb"; break;
        case "protein_main": role = "protein"; break;
        case "side": role = "veg"; break;
        case "snack": role = "snack"; break;
        case "beverage": role = "addon"; break;
        case "condiment": role = "addon"; break;
        case "dessert": role = "limit"; break;
        default: role = "other";
      }
    }
  }

  if (role !== "protein" && role !== "mixed") {
    const tags = (details.tags || []).map(t => t.toLowerCase());
    if (tags.includes("egg") || tags.includes("chicken") || tags.includes("paneer") || tags.includes("fish")) {
      if ((details.calories || 0) > 100) role = "protein";
    }
  }
  if (foodName.toLowerCase().includes("papad") || foodName.toLowerCase().includes("pickle")) role = "addon";
  if (foodName.toLowerCase().includes("chilli fry")) role = "addon";
  if (details.category === "condiment") role = "addon";

  return { ...details, role };
}

module.exports = {
  recommendPlate,
  estimateDailyCalories,
  computeMacroTargets,
  classifyItem,
  filterFoods,
  buildPlate,
  getFallbackDetails,
  isZeroCalorie
};
