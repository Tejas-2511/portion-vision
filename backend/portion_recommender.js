const fs = require("fs");
const path = require("path");

// load the food database
let FOOD_DB = [];
try {
  FOOD_DB = JSON.parse(
    fs.readFileSync(
      path.join(__dirname, "data", "foodDatabase.json"),
      "utf8"
    )
  );
} catch (err) {
  console.error("Error reading food database:", err);
}

function defaultNutrition(name) {
  const n = name.toLowerCase();
  if (n.includes("rice")) return { calories: 130, protein: 2.7, carbs: 28, fat: 0.3 };
  if (n.includes("egg")) return { calories: 155, protein: 13, carbs: 1.1, fat: 11 };
  if (n.includes("dal")) return { calories: 116, protein: 9, carbs: 20, fat: 0.4 };
  if (n.includes("bread")) return { calories: 265, protein: 9, carbs: 50, fat: 3.2 };
  if (n.includes("butter")) return { calories: 720, protein: 1, carbs: 1, fat: 81 };
  if (n.includes("veg")) return { calories: 50, protein: 3, carbs: 10, fat: 1 };
  return { calories: 100, protein: 3, carbs: 15, fat: 3 };
}

function getFood(name) {
  return FOOD_DB.find(f => f.name.toLowerCase() === name.toLowerCase());
}

function estimateDailyCalories(user) {
  const weight = user.weight_kg || 70;
  const height = user.height_cm || 170;
  const age = user.age || 25;
  const sex = user.sex || "male";

  const bmr =
    sex.toLowerCase() === "female"
      ? 10 * weight + 6.25 * height - 5 * age - 161
      : 10 * weight + 6.25 * height - 5 * age + 5;

  const activity = {
    sedentary: 1.2,
    light: 1.375,
    moderate: 1.55,
    active: 1.725
  }[user.activity_level] || 1.55;

  let tdee = Math.round(bmr * activity);
  if (user.goal === "lose") tdee -= 300;
  if (user.goal === "gain") tdee += 300;
  return Math.max(1200, Math.min(4500, tdee));
}

function recommendPortion({ foodName, user, mealType }) {
  const entry = getFood(foodName);
  let food = null;

  if (entry) {
    food = {
      ...entry,
      ...defaultNutrition(entry.name),
      calories: entry.calories || defaultNutrition(entry.name).calories,
    };
  } else {
    const fallback = defaultNutrition(foodName);
    food = {
      name: foodName,
      calories: fallback.calories,
      protein: fallback.protein,
      carbs: fallback.carbs,
      fat: fallback.fat
    };
  }

  const daily = estimateDailyCalories(user || {});
  const mealFrac = { breakfast: 0.25, lunch: 0.35, dinner: 0.30, snack: 0.1 }[
    (mealType || "lunch").toLowerCase()
  ] || 0.33;

  const target = daily * mealFrac;

  const grams = Math.round((target / food.calories) * 100);
  return {
    food: food.name,
    grams,
    calories_per_100g: food.calories,
    estimated_portion_calories: Math.round((grams * food.calories) / 100),
    user_daily_calories: daily
  };
}

module.exports = { recommendPortion };
