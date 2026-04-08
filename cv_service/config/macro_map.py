"""
Food nutrition lookup table (per 1 gram).

Maps food names (lowercase) to nutritional values per gram:
{
    "calories": kcal/g,
    "protein":  g/g,
    "carbs":    g/g,
    "fat":      g/g
}

Nutrients are approximate averages for cooked Indian mess food.
"""

MACRO_MAP = {
    # ── Grains / Carbs (per 1g) ──
    "rice":             {"calories": 1.30, "protein": 0.027, "carbs": 0.28, "fat": 0.003},
    "sada rice":        {"calories": 1.30, "protein": 0.027, "carbs": 0.28, "fat": 0.003},
    "steam rice":       {"calories": 1.30, "protein": 0.027, "carbs": 0.28, "fat": 0.003},
    "jeera rice":       {"calories": 1.40, "protein": 0.027, "carbs": 0.28, "fat": 0.02},
    "fried rice":       {"calories": 1.65, "protein": 0.04,  "carbs": 0.26, "fat": 0.06},
    "biryani":          {"calories": 1.60, "protein": 0.08,  "carbs": 0.22, "fat": 0.05},
    "pulao":            {"calories": 1.40, "protein": 0.03,  "carbs": 0.25, "fat": 0.04},
    "khichdi":          {"calories": 1.10, "protein": 0.04,  "carbs": 0.20, "fat": 0.02},
    "chapati":          {"calories": 2.60, "protein": 0.08,  "carbs": 0.50, "fat": 0.03},
    "roti":             {"calories": 2.60, "protein": 0.08,  "carbs": 0.50, "fat": 0.03},
    "naan":             {"calories": 2.80, "protein": 0.09,  "carbs": 0.50, "fat": 0.05},
    "paratha":          {"calories": 3.20, "protein": 0.07,  "carbs": 0.45, "fat": 0.15},
    "poha":             {"calories": 1.80, "protein": 0.035, "carbs": 0.35, "fat": 0.04},
    "upma":             {"calories": 1.70, "protein": 0.04,  "carbs": 0.30, "fat": 0.05},
    "idli":             {"calories": 1.40, "protein": 0.03,  "carbs": 0.30, "fat": 0.005},
    "dosa":             {"calories": 1.70, "protein": 0.03,  "carbs": 0.30, "fat": 0.05},
    "oats":             {"calories": 0.70, "protein": 0.03,  "carbs": 0.12, "fat": 0.015},
    "bread":            {"calories": 2.60, "protein": 0.08,  "carbs": 0.50, "fat": 0.03},

    # ── Dals / Lentils ──
    "dal":              {"calories": 0.85, "protein": 0.055, "carbs": 0.12, "fat": 0.02},
    "dal palak":        {"calories": 0.85, "protein": 0.050, "carbs": 0.11, "fat": 0.02},
    "dal amritsari":    {"calories": 0.90, "protein": 0.06,  "carbs": 0.12, "fat": 0.03},
    "dal fry":          {"calories": 1.10, "protein": 0.05,  "carbs": 0.12, "fat": 0.05},
    "dal tadka":        {"calories": 1.00, "protein": 0.05,  "carbs": 0.12, "fat": 0.04},
    "dal makhani":      {"calories": 1.40, "protein": 0.05,  "carbs": 0.13, "fat": 0.09},
    "sambar":           {"calories": 0.65, "protein": 0.03,  "carbs": 0.10, "fat": 0.02},
    "rasam":            {"calories": 0.40, "protein": 0.01,  "carbs": 0.08, "fat": 0.01},
    "rajma":            {"calories": 1.20, "protein": 0.07,  "carbs": 0.18, "fat": 0.03},
    "chole":            {"calories": 1.35, "protein": 0.06,  "carbs": 0.20, "fat": 0.04},
    "chana":            {"calories": 1.30, "protein": 0.06,  "carbs": 0.18, "fat": 0.04},

    # ── Curries / Protein ──
    "chicken curry":    {"calories": 1.40, "protein": 0.15, "carbs": 0.04, "fat": 0.08},
    "chicken":          {"calories": 1.80, "protein": 0.20, "carbs": 0.02, "fat": 0.10},
    "egg curry":        {"calories": 1.20, "protein": 0.07, "carbs": 0.03, "fat": 0.09},
    "egg":              {"calories": 1.55, "protein": 0.13, "carbs": 0.01, "fat": 0.11},
    "fish curry":       {"calories": 1.10, "protein": 0.14, "carbs": 0.03, "fat": 0.05},
    "mutton":           {"calories": 2.50, "protein": 0.18, "carbs": 0.02, "fat": 0.20},
    "paneer":           {"calories": 2.65, "protein": 0.18, "carbs": 0.03, "fat": 0.20},
    "paneer do pyaza":  {"calories": 2.20, "protein": 0.12, "carbs": 0.06, "fat": 0.16},
    "paneer butter masala": {"calories": 2.50, "protein": 0.10, "carbs": 0.08, "fat": 0.20},
    "kofta":            {"calories": 2.10, "protein": 0.06, "carbs": 0.15, "fat": 0.15},

    # ── Sabzis / Sides ──
    "sabji":            {"calories": 0.90, "protein": 0.03, "carbs": 0.10, "fat": 0.05},
    "sabzi":            {"calories": 0.90, "protein": 0.03, "carbs": 0.10, "fat": 0.05},
    "aloo":             {"calories": 1.10, "protein": 0.02, "carbs": 0.20, "fat": 0.04},
    "aloo capsicum":    {"calories": 1.00, "protein": 0.02, "carbs": 0.15, "fat": 0.05},
    "aloo gobi":        {"calories": 0.95, "protein": 0.03, "carbs": 0.12, "fat": 0.05},
    "dal vada curry":   {"calories": 1.30, "protein": 0.06, "carbs": 0.15, "fat": 0.06},
    "gobi":             {"calories": 0.60, "protein": 0.03, "carbs": 0.08, "fat": 0.03},
    "bhindi":           {"calories": 0.90, "protein": 0.03, "carbs": 0.08, "fat": 0.06},
    "baingan":          {"calories": 0.80, "protein": 0.02, "carbs": 0.08, "fat": 0.05},
    "mixed veg":        {"calories": 0.90, "protein": 0.03, "carbs": 0.10, "fat": 0.05},
    "poriyal":          {"calories": 0.80, "protein": 0.03, "carbs": 0.07, "fat": 0.05},
    "bhaji":            {"calories": 1.20, "protein": 0.04, "carbs": 0.15, "fat": 0.07},

    # ── Accompaniments / Condiments ──
    "raita":            {"calories": 0.60, "protein": 0.03,  "carbs": 0.05, "fat": 0.03},
    "curd":             {"calories": 0.65, "protein": 0.035, "carbs": 0.05, "fat": 0.04},
    "salad":            {"calories": 0.25, "protein": 0.01,  "carbs": 0.05, "fat": 0.0},
    "pickle":           {"calories": 1.20, "protein": 0.01,  "carbs": 0.10, "fat": 0.10},
    "chutney":          {"calories": 1.00, "protein": 0.02,  "carbs": 0.15, "fat": 0.04},
    "papad":            {"calories": 3.50, "protein": 0.20,  "carbs": 0.55, "fat": 0.05},

    # ── Sweets ──
    "halwa":            {"calories": 3.20, "protein": 0.04, "carbs": 0.45, "fat": 0.15},
    "gulab jamun":      {"calories": 3.00, "protein": 0.04, "carbs": 0.50, "fat": 0.10},
    "kheer":            {"calories": 1.00, "protein": 0.03, "carbs": 0.15, "fat": 0.03},
    "laddu":            {"calories": 4.50, "protein": 0.06, "carbs": 0.55, "fat": 0.25},
    "barfi":            {"calories": 3.80, "protein": 0.08, "carbs": 0.45, "fat": 0.20},
}

DEFAULT_MACROS = {"calories": 1.0, "protein": 0.03, "carbs": 0.15, "fat": 0.03}


def get_macros(food_name: str) -> dict:
    """
    Lookup macros for a food item per gram.
    Tries exact match first, then substring match, then returns default.
    """
    key = food_name.strip().lower()

    # Exact match
    if key in MACRO_MAP:
        return MACRO_MAP[key]

    # Substring match
    for name, macros in MACRO_MAP.items():
        if name in key or key in name:
            return macros

    return DEFAULT_MACROS
