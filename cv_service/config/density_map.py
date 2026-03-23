"""
Food density lookup table.

Maps food names (lowercase) to density in g/ml (≈ g/cm³).
Used for: mass_g = volume_ml × density.

Densities are approximate averages for cooked Indian mess food.
"""

FOOD_DENSITIES = {
    # ── Grains / Carbs ──
    "rice":             1.10,   # cooked white rice, moderately packed
    "steam rice":       1.08,
    "jeera rice":       1.05,
    "fried rice":       0.95,
    "biryani":          1.00,
    "pulao":            1.00,
    "khichdi":          1.10,
    "chapati":          0.85,   # flat bread, solid
    "roti":             0.85,
    "naan":             0.80,
    "paratha":          0.90,
    "poha":             0.65,
    "upma":             0.85,
    "idli":             0.95,
    "dosa":             0.55,   # thin, less dense
    "oats":             0.80,
    "bread":            0.35,

    # ── Dals / Lentils ──
    "dal":              1.05,
    "dal amritsari":    1.05,
    "dal fry":          1.05,
    "dal tadka":        1.05,
    "dal makhani":      1.08,
    "sambar":           1.02,
    "rasam":            1.00,
    "rajma":            1.10,
    "chole":            1.08,
    "chana":            1.08,

    # ── Curries / Protein ──
    "chicken curry":    1.05,
    "chicken":          1.05,
    "egg curry":        1.02,
    "egg":              1.03,
    "fish curry":       1.05,
    "mutton":           1.06,
    "paneer":           1.03,
    "paneer do pyaza":  1.03,
    "paneer butter masala": 1.02,
    "kofta":            1.00,

    # ── Sabzis / Sides ──
    "sabji":            0.90,
    "sabzi":            0.90,
    "aloo":             1.00,
    "aloo gobi":        0.92,
    "gobi":             0.85,
    "bhindi":           0.80,
    "baingan":          0.85,
    "mixed veg":        0.90,
    "poriyal":          0.85,
    "bhaji":            0.80,

    # ── Accompaniments / Condiments ──
    "raita":            1.02,
    "curd":             1.03,
    "salad":            0.60,
    "pickle":           1.10,
    "chutney":          1.05,
    "tomato chutney":   1.05,
    "papad":            0.30,   # very light, crispy

    # ── Sweets ──
    "halwa":            1.10,
    "gulab jamun":      1.15,
    "kheer":            1.05,
    "laddu":            1.05,
    "barfi":            1.10,

    # ── Beverages ──
    "milk":             1.03,
    "lassi":            1.04,
    "chaas":            1.01,
}

# Fallback density when food name is not found
DEFAULT_DENSITY = 1.0  # g/ml (approximately water density)


def get_density(food_name: str) -> float:
    """
    Lookup density for a food item.
    Tries exact match first, then substring match, then returns default.
    """
    key = food_name.strip().lower()

    # Exact match
    if key in FOOD_DENSITIES:
        return FOOD_DENSITIES[key]

    # Substring match — e.g. "chicken biryani" matches "biryani"
    for name, density in FOOD_DENSITIES.items():
        if name in key or key in name:
            return density

    return DEFAULT_DENSITY
