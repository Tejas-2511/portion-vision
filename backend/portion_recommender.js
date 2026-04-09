const Database = require("./utils/db");
const { normalizeFoodName } = require("./utils/normalize");
const { fuzzyMatchFood } = require("./utils/fuzzyMatch");

/**
 * Loads food data and builds an index for O(1) lookups.
 * @returns {Promise<{FOOD_DB: Array, FOOD_INDEX: Map}>}
 */
async function loadFoodData() {
    const foods = await Database.getFoods();
    const index = new Map();
    foods.forEach(item => {
        if (item && item.name) {
            index.set(normalizeFoodName(item.name), item);
        }
    });
    return { FOOD_DB: foods, FOOD_INDEX: index };
}

/**
 * Find food in DB with O(1) check followed by fuzzy match
 */
async function findFood(name, foodData = null) {
    const { FOOD_DB, FOOD_INDEX } = foodData || await loadFoodData();
    const normalized = normalizeFoodName(name);
    let match = FOOD_INDEX.get(normalized);
    if (match) return match;

    // Safety: Don't fuzzy match very short strings (like "Dal" matching "Jam")
    if (normalized.length <= 3) return null;

    return fuzzyMatchFood(normalized, FOOD_DB, 2);
}

function getFallbackDetails(name) {
    const item = _getRawFallback(name);

    // Assign protein level based on content
    if (item.protein >= 15) item.protein_level = 'high';
    else if (item.protein >= 8) item.protein_level = 'medium';
    else item.protein_level = 'low';

    // Upgrade category if protein is high
    if (item.protein >= 10 && item.category === 'side') {
        item.category = 'protein_main';
    }
    return item;
}

function _getRawFallback(name) {
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
    if (n === "dal" || n.startsWith("dal ") || n.endsWith(" dal") || n.includes(" dal ") || n.includes("sambar") || n.includes("rajma") || n.includes("chole") || n.includes("chana"))
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
    if (n.includes("bun") || n.includes("pav") || n.includes("bread"))
        return { category: "carb_base", meal_role: "single", unit_type: "piece", serving_size: 60, serving_unit: "g", calories: 180, protein: 5, carbs: 35, fat: 8, fiber: 1, dish_type: "bun", meal_types: ["breakfast", "snack"], tags: ["veg"], veg: true };
    if (n.includes("sweet") || n.includes("halwa") || n.includes("jamun") || n.includes("laddu") || n.includes("kheer") || n.includes("barfi") || n.includes("mithai") || n.includes("payasam") || n.includes("pudding"))
        return { category: "dessert", meal_role: "single", unit_type: "piece", serving_size: 50, serving_unit: "g", calories: 200, protein: 2, carbs: 30, fat: 8, fiber: 0, dish_type: "sweet", meal_types: ["lunch", "dinner", "snack"], tags: ["sweet", "veg"], veg: true };
    if (n.includes("fruit") || n.includes("banana") || n.includes("apple") || n.includes("orange"))
        return { category: "snack", meal_role: "single", unit_type: "piece", serving_size: 1, serving_unit: "piece", calories: 80, protein: 1, carbs: 20, fat: 0, fiber: 3, dish_type: "fruit", meal_types: ["breakfast", "snack"], tags: ["veg"], veg: true };
    if (n.includes("pickle") || n.includes("chutney") || n.includes("achar") || n.includes("sauce"))
        return { category: "condiment", meal_role: "single", unit_type: "tbsp", serving_size: 15, serving_unit: "g", calories: 30, protein: 0.5, carbs: 4, fat: 1, fiber: 1, dish_type: "condiment", meal_types: ["lunch", "dinner", "breakfast"], tags: ["veg"], veg: true };

    // ── Condiments - tag garlic/onion items so Jain filter works ──
    if (n.includes("garlic chutney") || n.includes("lasun"))
        return { category: "condiment", meal_role: "single", unit_type: "tsp", serving_size: 10, serving_unit: "g", calories: 30, protein: 1, carbs: 4, fat: 1, fiber: 0, dish_type: "condiment", tags: ["garlic", "veg"], veg: true };
    if (n.includes("papad"))
        return { category: "condiment", meal_role: "single", unit_type: "piece", serving_size: 15, serving_unit: "g", calories: 40, protein: 1, carbs: 5, fat: 2, fiber: 1, dish_type: "condiment", tags: ["veg"], veg: true };

    // Default generic side
    return { category: "side", meal_role: "single", unit_type: "bowl", serving_size: 100, serving_unit: "g", calories: 150, protein: 3, carbs: 20, fat: 5, fiber: 2, dish_type: "sabji", tags: ["veg"], veg: true };
}

// Guard: skip foods that have no calorie data (OCR stubs)
function isZeroCalorie(food) {
    return !food || !food.calories || food.calories === 0;
}

// ==========================================
// 2. Diet Filtering
// ==========================================

const JAIN_AVOID_TAGS = ["potato", "onion", "garlic", "carrot", "beet", "radish", "turnip", "ginger"];
const JAIN_AVOID_NAMES = ["garlic", "onion", "potato", "aloo", "lasun", "pyaaz"];

function normalizeDiet(diet) {
    if (!diet) return "non-veg";
    const d = diet.toLowerCase().replace(/[-\s]/g, "");
    if (d.includes("jain")) return "jain";
    if (d.includes("vegan")) return "vegan";
    if (d.includes("lacto")) return "lacto-veg";
    if (d.includes("ovo")) return "ovo-veg";
    if (d.includes("nonveg") || d === "nonvegetarian") return "non-veg";
    if (d.includes("vegetarian") || d === "veg") return "vegetarian";
    return "non-veg";
}

const MEAT_TAGS = ["chicken", "mutton", "fish", "prawn", "beef", "pork", "seafood"];

function isMeat(food) {
    if (!food || !food.tags) return false;
    const tags = (food.tags || []).map(t => t.toLowerCase());
    return MEAT_TAGS.some(t => tags.includes(t));
}
function isEgg(food) {
    if (!food || !food.tags) return false;
    return (food.tags || []).map(t => t.toLowerCase()).includes("egg");
}
function isDairy(food) {
    if (!food || !food.tags) return false;
    return (food.tags || []).map(t => t.toLowerCase()).some(t => ["dairy", "milk", "ghee", "butter"].includes(t));
}

function filterFoods(foods, dietPreference, avoidTags = []) {
    const diet = normalizeDiet(dietPreference);
    const allAvoidTags = [...avoidTags];
    if (diet === "jain") allAvoidTags.push(...JAIN_AVOID_TAGS);

    return foods.filter(food => {
        if (isZeroCalorie(food)) return false;

        const tags = (food.tags || []).map(t => t.toLowerCase());

        if (diet === "vegan") {
            if (isMeat(food) || isEgg(food) || isDairy(food)) return false;
            if (food.veg === false) return false;
        }
        else if (diet === "jain") {
            if (isMeat(food) || isEgg(food)) return false;
            if (food.veg === false) return false;
        }
        else if (diet === "lacto-veg") {
            if (isMeat(food) || isEgg(food)) return false;
            if (food.veg === false && !isDairy(food)) return false;
        }
        else if (diet === "ovo-veg") {
            if (isMeat(food)) return false;
            if (isDairy(food)) return false;
            if (food.veg === false && !isEgg(food)) return false;
        }
        else if (diet === "vegetarian") {
            if (isMeat(food)) return false;
            if (food.veg === false && !isEgg(food) && !isDairy(food)) return false;
        }

        if (allAvoidTags.length > 0) {
            const hasAvoidTag = allAvoidTags.some(tag => tags.includes(tag.toLowerCase()));
            if (hasAvoidTag) return false;
        }

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

    const actKey = activityLevel.split(" ")[0];
    let tdee = bmr * (activityMultipliers[actKey] || 1.55);

    if (goal.includes("lose") || goal.includes("fat")) tdee *= 0.8; // Proportional 20% deficit
    if (goal.includes("gain") || goal.includes("muscle")) tdee *= 1.15; // Proportional 15% surplus

    return Math.round(Math.max(1000, Math.min(5000, tdee)));
}

function computeMacroTargets(user, mealType) {
    const dailyCalories = estimateDailyCalories(user);

    const mealFractions = {
        breakfast: 0.25,
        lunch: 0.35,
        dinner: 0.30,
        snack: 0.10
    };
    const mealFrac = mealFractions[(mealType || "lunch").toLowerCase()] || 0.33;
    const targetCalories = dailyCalories * mealFrac;

    const pPct = (user.proteinPct || 25) / 100;
    const cPct = (user.carbsPct || 45) / 100;
    const fPct = (user.fatPct || 30) / 100;

    return {
        dailyCalories,
        targetCalories: Math.round(targetCalories),
        targetProtein: Math.round((targetCalories * pPct) / 4),
        targetCarbs_g: Math.round((targetCalories * cPct) / 4),
        maxFat_g: Math.round((targetCalories * fPct) / 9),
        mealFrac,
        pPct,
        cPct
    };
}

function calcServings(food, targetCalPerItem, maxServings = 4, maxFatPerItem = Infinity) {
    if (!food || !food.calories || food.calories <= 0) return 1;
    const unit = (food.unit_type || "").toLowerCase();
    const isDiscrete = ["piece", "roti", "paratha", "glass"].includes(unit);

    let raw = targetCalPerItem / food.calories;

    if (food.fat > 0 && (raw * food.fat) > maxFatPerItem) {
        raw = maxFatPerItem / food.fat;
    }

    if (isDiscrete) {
        return Math.max(1, Math.min(maxServings, Math.round(raw)));
    }
    const snapped = Math.round(raw * 2) / 2;
    return Math.max(0.5, Math.min(maxServings, snapped));
}

function scaleItem(food, qty) {
    return {
        ...food,
        quantity: qty,
        estimatedCalories: Math.round((food.calories || 0) * qty),
        protein: Math.round((food.protein || 0) * qty * 10) / 10,
        carbs: Math.round((food.carbs || 0) * qty * 10) / 10,
        fat: Math.round((food.fat || 0) * qty * 10) / 10,
        fiber: Math.round((food.fiber || 0) * qty * 10) / 10,
        grams: Math.round((food.serving_size || 100) * qty)
    };
}

async function buildPlate({ user, menuItems, mealType, dietPreference, avoidTags }) {
    const logicLogs = [];
    const logLogic = (msg) => {
        logicLogs.push(msg);
        console.log(`[REASONING] ${msg}`);
    };

    const foodData = await loadFoodData();
    const macros = computeMacroTargets(user, mealType);
    const { targetCalories, maxFat_g, pPct, cPct } = macros;
    const mt = (mealType || "lunch").toLowerCase();

    logLogic(`Targeting ${Math.round(targetCalories)} kcal for ${mt} (${user.goalType || 'maintenance'}).`);
    logLogic(`Macro split goal: ${user.proteinPct || 25}% Protein, ${user.carbsPct || 45}% Carbs, ${user.fatPct || 30}% Fat.`);

    const resolved = await Promise.all((menuItems || []).map(async name => {
        const dbItem = await findFood(name, foodData);
        const item = dbItem ? { ...dbItem, name } : { name, ...getFallbackDetails(name) };
        logLogic(`Resolved '${name}' to '${item.name}' (ID: ${item.id || 'fallback'}) - Category: ${item.category}`);
        return item;
    }));

    const filtered = filterFoods(resolved, dietPreference || "non-veg", avoidTags || []);
    if (filtered.length < resolved.length) {
        logLogic(`Filtered out ${resolved.length - filtered.length} items based on '${dietPreference}' diet.`);
    }

    if (filtered.length === 0) {
        return { plate: [], optionals: [], macros, notes: "No suitable items found for your dietary preference." };
    }

    const partitions = {
        mixed: filtered.filter(f => f.meal_role === "mixed"),
        proteins: filtered.filter(f => f.category === "protein_main"),
        carbs: filtered.filter(f => f.category === "carb_base"),
        salads: filtered.filter(f => f.category === "side" && f.dish_type === "salad"),
        sides: filtered.filter(f => f.category === "side" && f.dish_type !== "salad"),
        condiments: filtered.filter(f => f.category === "condiment"),
        beverages: filtered.filter(f => f.category === "beverage"),
        desserts: filtered.filter(f => f.category === "dessert")
    };

    logLogic(`Partitions count: Proteins: ${partitions.proteins.length}, Carbs: ${partitions.carbs.length}, Sides: ${partitions.sides.length}.`);

    let plate = [];
    let caloriesUsed = 0;

    // Fast-path: Snack
    if (mt === "snack") {
        const candidates = [...partitions.carbs, ...partitions.proteins, ...partitions.sides, ...partitions.beverages]
            .sort((a, b) => (b.protein || 0) - (a.protein || 0));

        const snackFractions = candidates.length > 0 ? 0.9 / candidates.length : 0.45;
        for (const can of candidates.slice(0, 2)) {
            const qty = calcServings(can, targetCalories * snackFractions, 3.0);
            if (qty > 0) {
                const item = scaleItem(can, qty);
                plate.push({ ...item, role: can.category === "beverage" ? "addon" : "snack", reason: "Quick energy." });
                caloriesUsed += item.estimatedCalories;
            }
        }
        return buildResponse({ plate, partitions, macros, mt });
    }

    // Fast-path: Mixed Meal
    if (partitions.mixed.length > 0) {
        const best = partitions.mixed.sort((a, b) => (b.protein || 0) - (a.protein || 0))[0];
        const qty = calcServings(best, targetCalories, 3.5);
        plate.push({ ...scaleItem(best, qty), role: "mixed", reason: "Complete nutritious meal." });
        partitions.salads.forEach(s => plate.push({ ...scaleItem(s, 1), role: "veg", reason: "Fresh fiber." }));
        return buildResponse({ plate, partitions, macros, mt });
    }

    // Phase 1: Veg Side (Fiber)
    let reservedVeg = 0;
    let mainSide = partitions.sides.sort((a, b) => (b.fiber || 0) - (a.fiber || 0))[0];
    if (mainSide) reservedVeg = Math.min(mainSide.calories * 2, Math.max(150, targetCalories * 0.2));

    // Phase 2: Protein
    const sortedProteins = partitions.proteins.sort((a, b) => (b.protein / (b.calories || 1)) - (a.protein / (a.calories || 1)));
    const pRatio = pPct / (pPct + cPct || 1);
    const proteinBudget = (targetCalories - reservedVeg) * pRatio;

    if (sortedProteins.length > 0) {
        // Variety: Use up to 2 protein items if available
        const p1 = sortedProteins[0];
        const p2 = sortedProteins[1]; // exists or undefined

        if (p2 && proteinBudget > 100) {
            logLogic(`Using multi-protein 'Thali' style split (60/40) between ${p1.name} and ${p2.name}.`);
            const qty1 = calcServings(p1, proteinBudget * 0.6, 2.5, maxFat_g);
            const qty2 = calcServings(p2, proteinBudget * 0.4, 2.5, maxFat_g);

            if (qty1 > 0) {
                const item1 = scaleItem(p1, qty1);
                plate.push({ ...item1, role: "protein", reason: "Primary protein source." });
                caloriesUsed += item1.estimatedCalories;
            }
            if (qty2 > 0) {
                const item2 = scaleItem(p2, qty2);
                plate.push({ ...item2, role: "protein", reason: "Secondary protein source." });
                caloriesUsed += item2.estimatedCalories;
            }
        } else {
            logLogic(`Using single protein source: ${p1.name}.`);
            const qty = calcServings(p1, proteinBudget, 3.5, maxFat_g);
            const item = scaleItem(p1, qty);
            plate.push({ ...item, role: "protein", reason: "Primary protein source." });
            caloriesUsed += item.estimatedCalories;
        }
    }

    // Phase 3: Carbs
    remaining = targetCalories - caloriesUsed - (plate.some(it => it.role === "veg") ? 0 : reservedVeg);
    if (partitions.carbs.length > 0 && remaining > 50) {
        const c1 = partitions.carbs[0];
        const c2 = partitions.carbs[1];

        if (c2 && remaining > 200) {
            logLogic(`Using multi-carb split (50/50) between ${c1.name} and ${c2.name}.`);
            const qty1 = calcServings(c1, remaining * 0.5, c1.dish_type === "roti" ? 4 : 3, maxFat_g);
            const qty2 = calcServings(c2, remaining * 0.5, c2.dish_type === "roti" ? 4 : 3, maxFat_g);

            if (qty1 > 0) {
                const item1 = scaleItem(c1, qty1);
                plate.push({ ...item1, role: "carb", reason: "Main carb source." });
                caloriesUsed += item1.estimatedCalories;
            }
            if (qty2 > 0) {
                const item2 = scaleItem(c2, qty2);
                plate.push({ ...item2, role: "carb", reason: "Secondary carb source." });
                caloriesUsed += item2.estimatedCalories;
            }
        } else {
            logLogic(`Using single carb source: ${c1.name}.`);
            const qty = calcServings(c1, Math.max(0, remaining), c1.dish_type === "roti" ? 4 : 3.5, maxFat_g);
            const item = scaleItem(c1, qty);
            plate.push({ ...item, role: "carb", reason: "Fuels your activity." });
            caloriesUsed += item.estimatedCalories;
        }
    }

    // Phase 4: Sides
    if (mainSide) {
        remaining = targetCalories - caloriesUsed;
        const qty = calcServings(mainSide, Math.max(50, remaining), 2.5);
        plate.push({ ...scaleItem(mainSide, qty), role: "veg", reason: "High fiber side." });
    }

    // Add Salads
    partitions.salads.forEach(s => {
        const item = scaleItem(s, 1);
        plate.push({ ...item, role: "veg", reason: "Light and crunchy." });
        caloriesUsed += item.estimatedCalories;
    });

    // Phase 5: Calorie Top-up (Close the gap to target)
    let gap = targetCalories - caloriesUsed;
    if (gap > targetCalories * 0.05) {
        logLogic(`Calorie gap of ${Math.round(gap)} kcal detected. Attempting to top-up portions.`);
        // Try to bump the most calorie dense main item (Carb or Protein)
        const filler = plate.find(it => it.role === "carb" || it.role === "protein");
        if (filler) {
            // Find how much more we need in servings, but don't overshoot by more than 50kcal
            let needed = gap / filler.calories;
            let extraQty = Math.round(needed * 2) / 2; // Snap to 0.5
            if (extraQty > 2) extraQty = 2; // Cap extra

            if (extraQty > 0) {
                logLogic(`Topping up ${filler.item || filler.name} by +${extraQty} servings.`);
                const index = plate.indexOf(filler);
                plate[index] = scaleItem(filler, filler.quantity + extraQty);
                caloriesUsed += (plate[index].estimatedCalories - filler.estimatedCalories);
            }
        }
    }

    logLogic(`Final plate generated with ${Math.round(caloriesUsed)} kcal.`);
    return buildResponse({ plate, partitions, macros, mt, logicLogs });
}

function buildResponse({ plate, partitions, macros, mt, logicLogs }) {
    const totals = {
        calories: Math.round(plate.reduce((s, i) => s + (i.estimatedCalories || 0), 0)),
        protein: Math.round(plate.reduce((s, i) => s + (i.protein || 0), 0) * 10) / 10,
        carbs: Math.round(plate.reduce((s, i) => s + (i.carbs || 0), 0) * 10) / 10,
        fat: Math.round(plate.reduce((s, i) => s + (i.fat || 0), 0) * 10) / 10
    };

    const usedNames = new Set(plate.map(p => p.name));
    const optionals = [
        ...partitions.condiments.filter(f => !usedNames.has(f.name)).slice(0, 2).map(f => ({ item: f.name, note: "Condiment", limit: "1 serving" })),
        ...partitions.beverages.filter(f => !usedNames.has(f.name)).slice(0, 1).map(f => ({ item: f.name, note: "Beverage", limit: "1 glass" })),
        ...partitions.desserts.filter(f => !usedNames.has(f.name)).slice(0, 1).map(f => ({ item: f.name, note: "Sweet Treat", limit: "Moderation" }))
    ];

    return { plate, optionals, macros: { ...macros, ...totals }, logicLogs };
}

async function recommendPlate({ user, menuItems, mealType }) {
    const mt = (mealType || "lunch").toLowerCase();
    const dietPreference = user.dietPreference || "non-veg";
    const avoidTags = user.avoidTags || [];

    const result = await buildPlate({ user, menuItems, mealType: mt, dietPreference, avoidTags });

    const recommendedPlate = result.plate.map(item => ({
        item: item.name,
        dish_type: item.dish_type,
        role: item.role,
        recommendedQuantity: item.quantity,
        unit: item.unit_type || "bowl",
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

    const dietNoteMap = {
        jain: "Jain-friendly: root vegetables excluded.",
        vegan: "Vegan: all animal products excluded.",
        "lacto-veg": "Lacto-vegetarian: dairy included, no eggs/meat.",
        "ovo-veg": "Ovo-vegetarian: eggs included, no dairy/meat.",
        vegetarian: "Vegetarian: dairy & eggs OK, no meat."
    };

    return {
        mealType: mt,
        dietPreference: normalizeDiet(dietPreference),
        recommendedPlate,
        optionalItems: result.optionals,
        summary: {
            dailyCalories: result.macros.dailyCalories,
            targetMealCalories: result.macros.targetCalories,
            totalPlateCalories: result.macros.calories,
            totalPlateProtein: result.macros.protein,
            totalPlateCarbs: result.macros.carbs,
            totalPlateFat: result.macros.fat,
            targetProtein: result.macros.targetProtein,
            dietNote: dietNoteMap[normalizeDiet(dietPreference)] || "",
            notes: result.notes || "Portions are estimates based on standard serving sizes.",
            logicLogs: result.logicLogs
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

module.exports = {
    recommendPlate,
    estimateDailyCalories,
    computeMacroTargets,
    getFallbackDetails,
    filterFoods
};
