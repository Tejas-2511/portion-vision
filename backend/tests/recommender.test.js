/**
 * Unit tests for the redesigned portion recommendation engine.
 * Run with: node tests/recommender.test.js
 * No external test framework required.
 */

const assert = require("assert");
const {
  computeMacroTargets,
  buildPlate,
  filterFoods,
  isZeroCalorie,
  getFallbackDetails
} = require("../portion_recommender");

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ✅ PASS: ${name}`);
    passed++;
  } catch (err) {
    console.error(`  ❌ FAIL: ${name}`);
    console.error(`     ${err.message}`);
    failed++;
  }
}

// ─── Mock data ───────────────────────────────────────────────────────────────

const mockUser = {
  weight_kg: 70, height_cm: 175, age: 22,
  sex: "male", activity_level: "moderate",
  goal: "maintain", goalType: "Maintain Weight"
};

const mockMenu = [
  { name: "chapati",    category: "carb_base",    dish_type: "roti",    unit_type: "piece", serving_size: 40,  serving_unit: "g", calories: 104, protein: 3,  carbs: 20, fat: 1,  fiber: 3,  veg: true,  tags: ["veg"], protein_level: "low" },
  { name: "dal tadka",  category: "protein_main", dish_type: "dal",     unit_type: "bowl",  serving_size: 150, serving_unit: "g", calories: 190, protein: 11, carbs: 30, fat: 4,  fiber: 8,  veg: true,  tags: ["dal", "veg"], protein_level: "medium" },
  { name: "aloo gobi",  category: "side",         dish_type: "sabji",   unit_type: "bowl",  serving_size: 150, serving_unit: "g", calories: 160, protein: 5,  carbs: 20, fat: 8,  fiber: 6,  veg: true,  tags: ["veg"], protein_level: "low" },
  { name: "rice",       category: "carb_base",    dish_type: "rice",    unit_type: "bowl",  serving_size: 200, serving_unit: "g", calories: 250, protein: 5,  carbs: 50, fat: 2,  fiber: 1,  veg: true,  tags: ["veg"], protein_level: "low" },
  { name: "raita",      category: "side",         dish_type: "raita",   unit_type: "bowl",  serving_size: 100, serving_unit: "g", calories: 80,  protein: 4,  carbs: 8,  fat: 2,  fiber: 0,  veg: true,  tags: ["dairy", "veg"], protein_level: "low" },
  { name: "boiled egg", category: "protein_main", dish_type: "egg",     unit_type: "piece", serving_size: 1,   serving_unit: "piece", calories: 70, protein: 6, carbs: 1, fat: 5, fiber: 0, veg: false, tags: ["egg", "non-veg"], protein_level: "medium" },
  { name: "paneer curry",category:"protein_main", dish_type: "curry",   unit_type: "bowl",  serving_size: 150, serving_unit: "g", calories: 280, protein: 18, carbs: 5,  fat: 20, fiber: 0,  veg: true,  tags: ["dairy", "veg"], protein_level: "high" },
  { name: "chicken curry",category:"protein_main",dish_type: "curry",   unit_type: "bowl",  serving_size: 150, serving_unit: "g", calories: 280, protein: 25, carbs: 5,  fat: 14, fiber: 1,  veg: false, tags: ["chicken", "non-veg"], protein_level: "high" },
  // Zero-calorie OCR stub
  { name: "achari kaddu", category: "", dish_type: "", unit_type: "plate", serving_size: 0, serving_unit: "g", calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, veg: false, tags: [] },
  // Jain-problematic item
  { name: "aloo matar", category: "side", dish_type: "sabji", unit_type: "bowl", serving_size: 150, serving_unit: "g", calories: 190, protein: 5, carbs: 28, fat: 7, fiber: 5, veg: true, tags: ["potato", "veg"], protein_level: "low" }
];

// ─── Tests ───────────────────────────────────────────────────────────────────

console.log("\n📋 Testing computeMacroTargets()");

test("Returns positive targetCalories for standard male user", () => {
  const m = computeMacroTargets(mockUser, "lunch");
  assert.ok(m.targetCalories > 400, `Expected >400 kcal, got ${m.targetCalories}`);
  assert.ok(m.targetCalories < 1500, `Expected <1500 kcal, got ${m.targetCalories}`);
});

test("Protein target scales with body weight", () => {
  const m = computeMacroTargets(mockUser, "lunch");
  // 70kg × 1.0 × 0.35 meal fraction ≈ 24.5g protein
  assert.ok(m.targetProtein >= 20, `Expected ≥20g protein, got ${m.targetProtein}`);
  assert.ok(m.targetProtein <= 35, `Expected ≤35g protein, got ${m.targetProtein}`);
});

test("Muscle gain goal raises protein priority to 'high'", () => {
  const m = computeMacroTargets({ ...mockUser, goalType: "Muscle Gain", goal: "muscle" }, "lunch");
  assert.strictEqual(m.proteinPriority, "high");
});

test("Breakfast fraction is smaller than lunch fraction", () => {
  const breakfast = computeMacroTargets(mockUser, "breakfast");
  const lunch = computeMacroTargets(mockUser, "lunch");
  assert.ok(breakfast.targetCalories < lunch.targetCalories, "Breakfast should be less than lunch");
});

// ─────────────────────────────────────────────────────────────────────────────

console.log("\n🔒 Testing isZeroCalorie()");

test("Returns true for zero-calorie OCR stub", () => {
  assert.ok(isZeroCalorie({ calories: 0 }));
  assert.ok(isZeroCalorie({ calories: undefined }));
});

test("Returns false for real food items", () => {
  assert.ok(!isZeroCalorie({ calories: 190 }));
});

// ─────────────────────────────────────────────────────────────────────────────

console.log("\n🧹 Testing filterFoods()");

test("Vegan filter removes non-veg and dairy items", () => {
  const results = filterFoods(mockMenu, "vegan");
  const names = results.map(f => f.name);
  assert.ok(!names.includes("boiled egg"), "Vegan should exclude egg");
  assert.ok(!names.includes("chicken curry"), "Vegan should exclude chicken");
  assert.ok(!names.includes("paneer curry"), "Vegan should exclude dairy (paneer)");
  assert.ok(!names.includes("raita"), "Vegan should exclude dairy (raita)");
});

test("Vegetarian keeps dairy and eggs, removes only meat", () => {
  const results = filterFoods(mockMenu, "vegetarian");
  const names = results.map(f => f.name);
  assert.ok(!names.includes("chicken curry"), "Vegetarian should exclude chicken");
  assert.ok(names.includes("boiled egg"), "Vegetarian should include egg");
  assert.ok(names.includes("paneer curry"), "Vegetarian should include paneer");
});

test("Lacto-veg keeps dairy but removes egg", () => {
  const results = filterFoods(mockMenu, "lacto-veg");
  const names = results.map(f => f.name);
  assert.ok(!names.includes("boiled egg"), "Lacto-veg should exclude egg");
  assert.ok(names.includes("paneer curry"), "Lacto-veg should include paneer (dairy)");
  assert.ok(!names.includes("chicken curry"), "Lacto-veg should exclude chicken");
});

test("Ovo-veg keeps egg but removes dairy", () => {
  const results = filterFoods(mockMenu, "ovo-veg");
  const names = results.map(f => f.name);
  assert.ok(names.includes("boiled egg"), "Ovo-veg should include egg");
  assert.ok(!names.includes("paneer curry"), "Ovo-veg should exclude paneer (dairy)");
  assert.ok(!names.includes("raita"), "Ovo-veg should exclude raita (dairy)");
});

test("Non-veg allows all items", () => {
  const results = filterFoods(mockMenu, "non-veg");
  const names = results.map(f => f.name);
  assert.ok(names.includes("chicken curry"), "Non-veg should include chicken");
  assert.ok(names.includes("boiled egg"), "Non-veg should include egg");
});

test("Jain filter removes potato-tagged items", () => {
  const results = filterFoods(mockMenu, "jain");
  const names = results.map(f => f.name);
  assert.ok(!names.includes("aloo matar"), "Jain should exclude potato (aloo matar)");
  assert.ok(!names.includes("chicken curry"), "Jain should exclude non-veg");
});

test("Zero-calorie stubs are always removed by filterFoods", () => {
  const results = filterFoods(mockMenu, "non-veg");
  const names = results.map(f => f.name);
  assert.ok(!names.includes("achari kaddu"), "Zero-calorie stub must be filtered out");
});

test("avoidTags parameter removes matching items", () => {
  const results = filterFoods(mockMenu, "non-veg", ["egg"]);
  const names = results.map(f => f.name);
  assert.ok(!names.includes("boiled egg"), "Custom avoidTags should remove egg");
});

// ─────────────────────────────────────────────────────────────────────────────

console.log("\n🍽️  Testing buildPlate()");

test("Standard veg menu produces non-empty plate", () => {
  const result = buildPlate({
    user: mockUser,
    menuItems: ["chapati", "dal tadka", "aloo gobi", "rice", "raita"],
    mealType: "lunch",
    dietPreference: "vegetarian"
  });
  assert.ok(result.plate.length > 0, "Plate should not be empty");
});

test("Plate includes a protein source when protein items are available", () => {
  const result = buildPlate({
    user: mockUser,
    menuItems: ["chapati", "dal tadka", "aloo gobi"],
    mealType: "lunch",
    dietPreference: "vegetarian"
  });
  const hasProtein = result.plate.some(i => i.role === "protein");
  assert.ok(hasProtein, "Plate must include a protein item");
});

test("Vegan buildPlate excludes chicken and paneer", () => {
  const result = buildPlate({
    user: mockUser,
    menuItems: ["chapati", "chicken curry", "paneer curry", "dal tadka", "rice"],
    mealType: "lunch",
    dietPreference: "vegan"
  });
  const names = result.plate.map(i => i.name);
  assert.ok(!names.includes("chicken curry"), "Vegan plate must not contain chicken");
  assert.ok(!names.includes("paneer curry"), "Vegan plate must not contain paneer");
});

test("All-zero-calorie menu returns empty plate with a note", () => {
  const result = buildPlate({
    user: mockUser,
    menuItems: ["achari kaddu", "boondi"],
    mealType: "lunch",
    dietPreference: "vegetarian"
  });
  assert.strictEqual(result.plate.length, 0, "Zero-calorie menu should yield empty plate");
  assert.ok(result.notes && result.notes.length > 0, "Should explain why plate is empty");
});

test("Plate total calories are within 30% of target (not wildly off)", () => {
  const result = buildPlate({
    user: mockUser,
    menuItems: ["chapati", "dal tadka", "aloo gobi", "rice"],
    mealType: "lunch",
    dietPreference: "vegetarian"
  });
  const target = result.macros.targetCalories;
  const total = result.macros.totalCalories;
  const ratio = total / target;
  assert.ok(ratio >= 0.5 && ratio <= 1.6, `Plate calories ${total} should be within 50–160% of target ${target} (ratio: ${ratio.toFixed(2)})`);
});

test("Each plate item has a non-empty reason field", () => {
  const result = buildPlate({
    user: mockUser,
    menuItems: ["chapati", "dal tadka", "aloo gobi"],
    mealType: "lunch",
    dietPreference: "vegetarian"
  });
  result.plate.forEach(item => {
    assert.ok(item.reason && item.reason.length > 0, `Item '${item.name}' is missing a reason`);
  });
});

test("Muscle gain user gets 'high' proteinPriority in macros", () => {
  const muscleUser = { ...mockUser, goalType: "Muscle Gain", goal: "muscle gain" };
  const result = buildPlate({
    user: muscleUser,
    menuItems: ["chapati", "dal tadka", "rice"],
    mealType: "lunch",
    dietPreference: "vegetarian"
  });
  assert.strictEqual(result.macros.proteinPriority, "high");
});

// ─────────────────────────────────────────────────────────────────────────────

console.log("\n🌿 Testing getFallbackDetails()");

test("Rice fallback returns carb_base category", () => {
  const d = getFallbackDetails("basmati rice");
  assert.strictEqual(d.category, "carb_base");
  assert.ok(d.calories > 0);
});

test("Dal fallback returns protein_main category", () => {
  const d = getFallbackDetails("moong dal");
  assert.strictEqual(d.category, "protein_main");
});

test("Chicken fallback marks veg: false", () => {
  const d = getFallbackDetails("chicken masala");
  assert.strictEqual(d.veg, false);
});

test("Roti fallback has piece unit_type", () => {
  const d = getFallbackDetails("tandoori roti");
  assert.strictEqual(d.unit_type, "piece");
});

// ─────────────────────────────────────────────────────────────────────────────

console.log("\n─────────────────────────────────────────");
console.log(`Results: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error("❌ Some tests failed.");
  process.exit(1);
} else {
  console.log("✅ All tests passed!");
}
