"""
update_nutrition.py

Updates nutritional data for ALL items in foodDatabase.json.

Strategy:
  1. Check a built-in curated lookup table of accurate Indian food nutrition values.
  2. If not found there, query the Open Food Facts API (free, no key required).
  3. Update calories, protein, carbs, fat, fiber, serving_size, serving_unit,
     protein_level, dish_type, category, and veg for every item.

Nutrition values are per-serving (as stored in the database), NOT per 100g,
unless the item already has a serving_size; in that case we honour it.

Run from the project root:
    python tools/update_nutrition.py
"""

import json
import os
import re
import time

import requests

DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "backend", "data", "foodDatabase.json"
)

# ---------------------------------------------------------------------------
# Curated Indian Food Nutrition Database
# Values represent per-typical-serving nutritional content.
# Sources: ICMR-NIN Nutritive Value of Indian Foods, IFCT 2017,
#          CalorieKing, NutritionValue.org, and standard culinary estimates.
# Fields: (calories, protein_g, carbs_g, fat_g, fiber_g,
#          serving_size, serving_unit, dish_type, category, veg)
# ---------------------------------------------------------------------------
CURATED = {
    # name                    cal  pro  carb  fat  fib  ss   su        dish_type         category        veg
    "achari kaddu":          (140,  3,   16,   7,  3,  150, "g",    "sabji",          "side",         True),
    "aloo bonda":            (180,  4,   22,   9,  3,   80, "g",    "snack",          "side",         True),
    "aloo gobi":             (160,  5,   20,   8,  6,  150, "g",    "sabji",          "side",         True),
    "aloo jeera":            (180,  3,   25,   8,  3,  150, "g",    "sabji",          "side",         True),
    "aloo matar":            (190,  5,   28,   7,  5,  150, "g",    "sabji",          "side",         True),
    "aloo palak":            (170,  5,   22,   7,  6,  150, "g",    "sabji",          "side",         True),
    "aloo papdi chaat":      (250,  5,   35,  10,  3,  150, "g",    "snack",          "side",         True),
    "aloo paratha":          (280,  6,   35,  12,  4,   80, "g",    "roti",           "carb_base",    True),
    "aloo sem phali":        (160,  4,   20,   7,  5,  150, "g",    "sabji",          "side",         True),
    "apple":                 ( 80,  0,   21,   0,  4,   1,  "piece","snack",          "snack",        True),
    "baingan bharta":        (140,  3,   15,   8,  6,  150, "g",    "sabji",          "side",         True),
    "banana":                (105,  1,   27,   0,  3,   1,  "piece","snack",          "snack",        True),
    "banana cake":           (250,  4,   40,   9,  2,   1,  "piece","sweet",          "dessert",      True),
    "beans poriyal":         (130,  3,   15,   7,  6,  150, "g",    "sabji",          "side",         True),
    "besan laddu":           (180,  4,   22,  10,  1,   30, "g",    "sweet",          "dessert",      True),
    "bhaji":                 (150,  3,   20,   7,  4,  150, "g",    "sabji",          "side",         True),
    "bhindi masala":         (150,  4,   12,  10,  5,  150, "g",    "sabji",          "side",         True),
    "biresra kadhi":         (210,  7,   18,  13,  1,  150, "g",    "main",           "curry",        True),
    "biscuit":               ( 50,  1,    7,   2,  0,   10, "g",    "snack",          "snack",        True),
    "black chana":           (180, 10,   30,   3,  9,  150, "g",    "sabji",          "side",         True),
    "black chana masala":    (220, 12,   30,   7,  9,  150, "g",    "curry",          "protein_main", True),
    "black masoor dal":      (190, 11,   32,   3,  8,  150, "g",    "dal",            "protein_main", True),
    "boiled egg":            ( 70,  6,    1,   5,  0,    1, "piece","egg",            "protein_main", False),
    "boondi":                (380,  7,   50,  17,  2,   50, "g",    "snack",          "snack",        True),
    "bread":                 ( 70,  3,   13,   1,  1,   30, "g",    "roti",           "carb_base",    True),
    "bread omelette":        (280, 12,   25,  14,  2,  150, "g",    "egg",            "protein_main", False),
    "butter":                ( 72,  0,    0,   8,  0,   10, "g",    "other",          "other",        True),
    "butter milk":           ( 40,  2,    4,   2,  0,  150, "ml",   "drink",          "beverage",     True),
    "butter naan":           (320,  8,   46,  12,  2,  100, "g",    "roti",           "carb_base",    True),
    "cabbage carrot":        (120,  2,   15,   6,  5,  150, "g",    "sabji",          "side",         True),
    "cabbage matar":         (130,  4,   18,   6,  5,  150, "g",    "sabji",          "side",         True),
    "cabbage poriyal":       (120,  3,   14,   7,  5,  150, "g",    "sabji",          "side",         True),
    "carrot beans poriyal":  (140,  3,   18,   7,  6,  150, "g",    "sabji",          "side",         True),
    "carrot capsicum":       (130,  2,   16,   7,  4,  150, "g",    "sabji",          "side",         True),
    "chaap makhani":         (280, 15,   20,  16,  3,  150, "g",    "curry",          "protein_main", True),
    "chaap masala":          (220, 15,   18,  12,  4,  150, "g",    "curry",          "protein_main", True),
    "chana dal":             (190, 10,   30,   4,  7,  150, "g",    "dal",            "protein_main", True),
    "chana dal burfi":       (180,  4,   25,   8,  1,   40, "g",    "sweet",          "dessert",      True),
    "chana masala":          (220, 10,   32,   8,  8,  150, "g",    "curry",          "protein_main", True),
    "chapati":               (104,  3,   20,   1,  3,   40, "g",    "roti",           "carb_base",    True),
    "chicken biryani":       (350, 18,   42,  10,  2,  300, "g",    "rice",           "carb_base",    False),
    "chicken chettinad":     (270, 22,    8,  17,  2,  200, "g",    "curry",          "protein_main", False),
    "chicken curry":         (240, 20,    8,  15,  2,  200, "g",    "curry",          "protein_main", False),
    "chilka moong dal":      (160,  9,   27,   3,  6,  150, "g",    "dal",            "protein_main", True),
    "chilli chicken":        (210, 18,   12,  11,  2,  150, "g",    "curry",          "protein_main", False),
    "chilli paneer":         (250, 13,   15,  16,  2,  150, "g",    "curry",          "protein_main", True),
    "chitranna":             (220,  4,   40,   7,  2,  150, "g",    "rice",           "carb_base",    True),
    "chocolate brownie":     (320,  4,   42,  16,  2,   60, "g",    "sweet",          "dessert",      True),
    "chole masala":          (220, 10,   32,   8,  8,  150, "g",    "curry",          "protein_main", True),
    "coconut burfi":         (370,  5,   52,  16,  2,   40, "g",    "sweet",          "dessert",      True),
    "coconut chutney":       (120,  2,    6,  10,  3,   30, "g",    "condiment",      "other",        True),
    "coffee":                ( 10,  0,    2,   0,  0,  150, "ml",   "drink",          "beverage",     True),
    "corn capsicum":         (160,  4,   26,   6,  4,  150, "g",    "sabji",          "side",         True),
    "corn pulao":            (230,  5,   43,   5,  4,  200, "g",    "rice",           "carb_base",    True),
    "cornflakes":            (150,  3,   33,   1,  1,   40, "g",    "snack",          "snack",        True),
    "curd":                  ( 60,  4,    4,   3,  0,  100, "g",    "drink",          "beverage",     True),
    "curd rice":             (185,  5,   33,   4,  1,  200, "g",    "rice",           "carb_base",    True),
    "dal amritsari":         (200, 10,   30,   6,  7,  150, "g",    "dal",            "protein_main", True),
    "dal dakshani":          (185,  9,   28,   5,  6,  150, "g",    "dal",            "protein_main", True),
    "dal fry":               (190, 10,   28,   6,  6,  150, "g",    "dal",            "protein_main", True),
    "dal makhani":           (220, 10,   28,   8,  7,  150, "g",    "dal",            "protein_main", True),
    "dal pakoda":            (160,  6,   20,   7,  3,  100, "g",    "snack",          "side",         True),
    "dal panchratan":        (195, 11,   30,   5,  7,  150, "g",    "dal",            "protein_main", True),
    "dal vada curry":        (230,  9,   28,  10,  5,  150, "g",    "dal",            "protein_main", True),
    "dhokla":                (140,  5,   23,   3,  2,  100, "g",    "snack",          "side",         True),
    "dum aloo":              (200,  4,   25,  10,  4,  150, "g",    "curry",          "side",         True),
    "dum aloo kashmiri":     (220,  5,   28,  11,  4,  150, "g",    "curry",          "side",         True),
    "egg bhurji":            (180, 12,    4,  14,  1,  120, "g",    "egg",            "protein_main", False),
    "egg curry":             (200, 13,    8,  14,  2,  150, "g",    "curry",          "protein_main", False),
    "egg keema masala":      (250, 18,    8,  17,  2,  150, "g",    "curry",          "protein_main", False),
    "egg methi keema masala":(240, 17,    9,  16,  3,  150, "g",    "curry",          "protein_main", False),
    "fish curry":            (230, 20,    7,  14,  2,  200, "g",    "curry",          "protein_main", False),
    "flavored milk":         (120,  5,   18,   3,  0,  200, "ml",   "drink",          "beverage",     True),
    "fried rice":            (250,  5,   42,   8,  2,  200, "g",    "rice",           "carb_base",    True),
    "fruit custard":         (180,  4,   30,   5,  2,  150, "g",    "sweet",          "dessert",      True),
    "fryum":                 (370,  4,   65,  10,  1,   30, "g",    "snack",          "snack",        True),
    "gajar matar":           (140,  4,   20,   6,  5,  150, "g",    "sabji",          "side",         True),
    "garlic khichdi":        (210,  7,   36,   5,  4,  200, "g",    "rice",           "carb_base",    True),
    "garlic naan":           (310,  8,   45,  11,  2,  100, "g",    "roti",           "carb_base",    True),
    "ghee rice":             (270,  4,   45,   9,  1,  150, "g",    "rice",           "carb_base",    True),
    "gobhi masala":          (150,  5,   16,   8,  5,  150, "g",    "sabji",          "side",         True),
    "grapes":                ( 60,  1,   16,   0,  1,  100, "g",    "snack",          "snack",        True),
    "green chilli fry":      ( 80,  2,    8,   5,  3,   50, "g",    "condiment",      "other",        True),
    "green chutney":         ( 45,  2,    5,   2,  2,   20, "g",    "condiment",      "other",        True),
    "green moong dal":       (170, 10,   28,   3,  7,  150, "g",    "dal",            "protein_main", True),
    "green moong dal khichdi":(200,  9,   35,   4,  5,  200, "g",   "rice",           "carb_base",    True),
    "green moong dal tadka": (175, 10,   29,   4,  7,  150, "g",    "dal",            "protein_main", True),
    "green peas pulao":      (230,  6,   40,   6,  5,  200, "g",    "rice",           "carb_base",    True),
    "green salad":           ( 40,  2,    7,   1,  3,  150, "g",    "salad",          "side",         True),
    "guijiya":               (250,  4,   32,  12,  2,   60, "g",    "sweet",          "dessert",      True),
    "gujiya":                (250,  4,   32,  12,  2,   60, "g",    "sweet",          "dessert",      True),
    "gulab jamun":           (175,  2,   28,   6,  0,   50, "g",    "sweet",          "dessert",      True),
    "gutta curry":           (160,  5,   14,  10,  4,  150, "g",    "curry",          "side",         True),
    "hot milk":              (120,  6,    9,   7,  0,  200, "ml",   "drink",          "beverage",     True),
    "ice tea":               ( 80,  0,   20,   0,  0,  200, "ml",   "drink",          "beverage",     True),
    "idli":                  ( 65,  2,   13,   0,  1,   40, "g",    "snack",          "carb_base",    True),
    "jal jeera":             ( 20,  0,    5,   0,  0,  200, "ml",   "drink",          "beverage",     True),
    "jalebi":                (278,  1,   56,   5,  0,   60, "g",    "sweet",          "dessert",      True),
    "jam":                   ( 50,  0,   13,   0,  0,   15, "g",    "condiment",      "other",        True),
    "jeera pulao":           (230,  5,   40,   7,  2,  200, "g",    "rice",           "carb_base",    True),
    "jeera rice":            (200,  4,   38,   4,  1,  150, "g",    "rice",           "carb_base",    True),
    "kachori":               (200,  4,   25,   9,  2,   60, "g",    "snack",          "side",         True),
    "kadhai paneer":         (290, 14,   18,  19,  3,  150, "g",    "curry",          "protein_main", True),
    "kadhai veg":            (160,  5,   18,   9,  5,  150, "g",    "curry",          "side",         True),
    "kadhi pakoda":          (200,  7,   22,  10,  3,  150, "g",    "main",           "curry",        True),
    "kaju katli":            (130,  4,   18,   7,  1,   30, "g",    "sweet",          "dessert",      True),
    "karela fry":            (100,  3,    9,   6,  4,  100, "g",    "sabji",          "side",         True),
    "kesar phirni":          (180,  4,   30,   5,  0,  150, "g",    "sweet",          "dessert",      True),
    "kesari bhat":           (250,  3,   40,  10,  1,  150, "g",    "sweet",          "dessert",      True),
    "kesariya thandai":      (180,  5,   28,   6,  0,  200, "ml",   "drink",          "beverage",     True),
    "khichdi":               (205,  8,   36,   4,  4,  200, "g",    "rice",           "carb_base",    True),
    "kulcha":                (295,  8,   44,  10,  2,  100, "g",    "roti",           "carb_base",    True),
    "lahsuni dal":           (195, 10,   30,   5,  6,  150, "g",    "dal",            "protein_main", True),
    "langarwali dal":        (210, 12,   30,   6,  8,  150, "g",    "dal",            "protein_main", True),
    "lassi":                 (180,  6,   25,   6,  0,  250, "ml",   "drink",          "beverage",     True),
    "lauki chana":           (160,  7,   22,   5,  5,  150, "g",    "sabji",          "side",         True),
    "lauki kofta curry":     (200,  6,   20,  11,  4,  150, "g",    "curry",          "side",         True),
    "lauki sabzi":           (100,  2,   12,   5,  3,  150, "g",    "sabji",          "side",         True),
    "lemon rice":            (215,  4,   40,   6,  2,  150, "g",    "rice",           "carb_base",    True),
    "lemon water":           (  5,  0,    1,   0,  0,  200, "ml",   "drink",          "beverage",     True),
    "lobia dal":             (185, 10,   30,   3,  7,  150, "g",    "dal",            "protein_main", True),
    "lobiya masala":         (190, 10,   30,   5,  7,  150, "g",    "curry",          "protein_main", True),
    "luchi":                 (170,  4,   24,   7,  1,   60, "g",    "roti",           "carb_base",    True),
    "macaroni":              (200,  6,   36,   4,  2,  150, "g",    "snack",          "carb_base",    True),
    "maggi":                 (290,  7,   43,  10,  2,  140, "g",    "snack",          "carb_base",    True),
    "malai kofta":           (310, 10,   24,  20,  3,  150, "g",    "curry",          "protein_main", True),
    "mango":                 ( 80,  1,   20,   0,  2,  100, "g",    "snack",          "snack",        True),
    "mangoda":               (250,  7,   32,  11,  4,  100, "g",    "snack",          "side",         True),
    "masala bhat":           (245,  6,   42,   7,  3,  200, "g",    "rice",           "carb_base",    True),
    "masala chai":           ( 60,  2,    8,   2,  0,  150, "ml",   "drink",          "beverage",     True),
    "masala dosa":           (206,  5,   35,   7,  3,  150, "g",    "snack",          "carb_base",    True),
    "masoor dal":            (175, 10,   28,   3,  8,  150, "g",    "dal",            "protein_main", True),
    "masoor dal tadka":      (180, 10,   28,   4,  8,  150, "g",    "dal",            "protein_main", True),
    "matar paneer":          (260, 12,   22,  14,  4,  150, "g",    "curry",          "protein_main", True),
    "medu vada":             (190,  6,   22,  10,  2,   80, "g",    "snack",          "side",         True),
    "methi dal":             (185, 10,   28,   5,  7,  150, "g",    "dal",            "protein_main", True),
    "methi matar chaman":    (240, 12,   18,  15,  5,  150, "g",    "curry",          "protein_main", True),
    "mix bhajiya":           (200,  5,   24,  10,  3,  100, "g",    "snack",          "side",         True),
    "mix dal":               (195, 11,   30,   5,  7,  150, "g",    "dal",            "protein_main", True),
    "mix veg":               (160,  5,   18,   9,  5,  150, "g",    "curry",          "side",         True),
    "moong dal halwa":       (320,  7,   42,  14,  2,  100, "g",    "sweet",          "dessert",      True),
    "moong dal khichdi":     (205,  9,   35,   4,  5,  200, "g",    "rice",           "carb_base",    True),
    "moong dal tadka":       (175, 10,   28,   4,  6,  150, "g",    "dal",            "protein_main", True),
    "moti chur ke laddu":    (150,  2,   22,   6,  1,   30, "g",    "sweet",          "dessert",      True),
    "murgh hydrabadi":       (280, 22,   12,  17,  2,  200, "g",    "curry",          "protein_main", False),
    "murgh saag wala":       (250, 20,   10,  16,  3,  200, "g",    "curry",          "protein_main", False),
    "mutton curry":          (300, 22,    8,  21,  2,  200, "g",    "curry",          "protein_main", False),
    "mysore bonda":          (190,  5,   24,   9,  2,   80, "g",    "snack",          "side",         True),
    "naan":                  (290,  8,   44,  10,  2,  100, "g",    "roti",           "carb_base",    True),
    "namkeen":               (450,  8,   60,  20,  3,   50, "g",    "snack",          "snack",        True),
    "onion pulao":           (225,  5,   38,   7,  3,  200, "g",    "rice",           "carb_base",    True),
    "orange":                ( 62,  1,   15,   0,  3,  130, "g",    "snack",          "snack",        True),
    "palak chana dal":       (195, 12,   28,   5,  8,  150, "g",    "dal",            "protein_main", True),
    "palak poori":           (180,  5,   26,   7,  4,   60, "g",    "roti",           "carb_base",    True),
    "paneer chat pata":      (260, 13,   14,  17,  2,  150, "g",    "snack",          "side",         True),
    "paneer do payza":       (290, 14,   16,  20,  3,  150, "g",    "curry",          "protein_main", True),
    "paneer handi":          (285, 14,   17,  19,  3,  150, "g",    "curry",          "protein_main", True),
    "pani poori":            (180,  4,   28,   6,  3,   6,  "piece","snack",          "side",         True),
    "papad":                 ( 40,  2,    7,   1,  1,   10, "g",    "snack",          "other",        True),
    "papad mangodi":         ( 55,  3,    7,   2,  1,   15, "g",    "snack",          "other",        True),
    "papaya":                ( 55,  1,   14,   0,  3,  100, "g",    "snack",          "snack",        True),
    "patiyala murgh":        (270, 20,   12,  17,  2,  200, "g",    "curry",          "protein_main", False),
    "pav":                   (130,  4,   24,   2,  1,   50, "g",    "roti",           "carb_base",    True),
    "pav bhaji":             (310,  8,   46,  12,  6,  200, "g",    "snack",          "carb_base",    True),
    "peanut chutney":        (160,  6,    8,  12,  2,   30, "g",    "condiment",      "other",        True),
    "phirni":                (175,  4,   28,   5,  0,  150, "g",    "sweet",          "dessert",      True),
    "pickle":                ( 30,  0,    4,   2,  1,   10, "g",    "condiment",      "other",        True),
    "pineapple halwa":       (200,  2,   35,   7,  2,  100, "g",    "sweet",          "dessert",      True),
    "plain dosa":            (133,  3,   26,   3,  2,   80, "g",    "snack",          "carb_base",    True),
    "poha":                  (158,  3,   32,   3,  2,  150, "g",    "snack",          "carb_base",    True),
    "pomegranate":           ( 83,  2,   19,   1,  4,  100, "g",    "snack",          "snack",        True),
    "poori":                 (170,  4,   24,   7,  2,   50, "g",    "roti",           "carb_base",    True),
    "potato chips":          (150,  2,   16,   9,  1,   30, "g",    "snack",          "snack",        True),
    "pumpkin sabzi":         (110,  3,   14,   5,  3,  150, "g",    "sabji",          "side",         True),
    "rabdi boondi":          (280,  6,   40,  11,  1,  150, "g",    "sweet",          "dessert",      True),
    "raita":                 ( 75,  4,    7,   3,  1,  100, "g",    "condiment",      "side",         True),
    "rajasthani kadhi":      (205,  7,   20,  12,  2,  150, "g",    "main",           "curry",        True),
    "rajma masala":          (220, 12,   35,   5, 10,  150, "g",    "curry",          "protein_main", True),
    "rasam":                 ( 45,  2,    7,   1,  2,  150, "ml",   "drink",          "beverage",     True),
    "rasgulla":              (115,  2,   22,   3,  0,   50, "g",    "sweet",          "dessert",      True),
    "rava upma":             (185,  5,   30,   7,  3,  150, "g",    "snack",          "carb_base",    True),
    "rice kheer":            (205,  5,   34,   6,  0,  150, "g",    "sweet",          "dessert",      True),
    "sakkara pongal":        (210,  5,   36,   7,  2,  150, "g",    "sweet",          "dessert",      True),
    "sambar":                ( 70,  3,   12,   2,  4,  150, "ml",   "main",           "curry",        True),
    "sambar rice":           (220,  7,   40,   4,  4,  200, "g",    "rice",           "carb_base",    True),
    "samosa":                (250,  5,   30,  13,  3,   80, "g",    "snack",          "side",         True),
    "scrambled egg":         (160, 11,    2,  12,  0,  100, "g",    "egg",            "protein_main", False),
    "sem fhali":             (140,  5,   18,   6,  6,  150, "g",    "sabji",          "side",         True),
    "semiya payasam":        (190,  4,   32,   6,  1,  150, "g",    "sweet",          "dessert",      True),
    "semiya upma":           (175,  4,   30,   5,  2,  150, "g",    "snack",          "carb_base",    True),
    "set dosa":              (150,  4,   28,   4,  2,  100, "g",    "snack",          "carb_base",    True),
    "sev tamatar":           (180,  5,   22,   9,  3,  150, "g",    "snack",          "side",         True),
    "sev tomato":            (180,  5,   22,   9,  3,  150, "g",    "snack",          "side",         True),
    "sewai kheer":           (195,  5,   32,   6,  1,  150, "g",    "sweet",          "dessert",      True),
    "shakar para":           (410,  5,   60,  16,  2,   50, "g",    "sweet",          "dessert",      True),
    "sheera":                (240,  3,   40,   9,  1,  100, "g",    "sweet",          "dessert",      True),
    "sindhi dal":            (195, 10,   30,   5,  7,  150, "g",    "dal",            "protein_main", True),
    "smoked dal":            (200, 10,   30,   6,  7,  150, "g",    "dal",            "protein_main", True),
    "soya masala":           (230, 18,   20,  10,  5,  150, "g",    "curry",          "protein_main", True),
    "soyabean masala":       (230, 18,   20,  10,  5,  150, "g",    "curry",          "protein_main", True),
    "steam rice":            (206,  4,   45,   0,  1,  150, "g",    "rice",           "carb_base",    True),
    "subzi miloni":          (155,  5,   18,   8,  5,  150, "g",    "sabji",          "side",         True),
    "sweet bun":             (250,  5,   42,   8,  1,   70, "g",    "snack",          "snack",        True),
    "sweet corn soup":       ( 80,  3,   14,   2,  2,  200, "ml",   "drink",          "beverage",     True),
    "sweet daliya":          (195,  5,   35,   5,  4,  150, "g",    "sweet",          "dessert",      True),
    "tamarind rice":         (215,  4,   40,   6,  3,  150, "g",    "rice",           "carb_base",    True),
    "tandoori roti":         (120,  4,   22,   2,  3,   50, "g",    "roti",           "carb_base",    True),
    "tea":                   ( 35,  1,    4,   2,  0,  150, "ml",   "drink",          "beverage",     True),
    "tinda masala":          (110,  3,   12,   6,  3,  150, "g",    "sabji",          "side",         True),
    "tomato chutney":        ( 50,  1,    8,   2,  2,   30, "g",    "condiment",      "other",        True),
    "tomato dal fry":        (185, 10,   27,   5,  7,  150, "g",    "dal",            "protein_main", True),
    "tomato pappu":          (175,  9,   27,   4,  6,  150, "g",    "dal",            "protein_main", True),
    "tomato rice":           (210,  4,   38,   6,  3,  150, "g",    "rice",           "carb_base",    True),
    "tomato soup":           ( 75,  2,   12,   2,  2,  200, "ml",   "drink",          "beverage",     True),
    "vada pav":              (300,  7,   42,  12,  3,  150, "g",    "snack",          "carb_base",    True),
    "veg biryani":           (270,  7,   42,   9,  4,  300, "g",    "rice",           "carb_base",    True),
    "veg hariyali":          (175,  7,   18,  10,  5,  150, "g",    "curry",          "side",         True),
    "veg kofta curry":       (230,  8,   22,  14,  4,  150, "g",    "curry",          "side",         True),
    "veg kolhapuri":         (185,  6,   18,  11,  5,  150, "g",    "curry",          "side",         True),
    "veg pongal":            (210,  7,   36,   6,  4,  200, "g",    "rice",           "carb_base",    True),
    "veg puff":              (270,  5,   34,  13,  2,   80, "g",    "snack",          "side",         True),
    "veg pulao":             (230,  6,   40,   7,  4,  200, "g",    "rice",           "carb_base",    True),
    "veg upma":              (185,  5,   30,   7,  3,  150, "g",    "snack",          "carb_base",    True),
    "vegetable chettinad":   (175,  5,   18,  10,  5,  150, "g",    "curry",          "side",         True),
    "vegetable kolhapuri":   (185,  6,   18,  11,  5,  150, "g",    "curry",          "side",         True),
    "vegetable pulao":       (230,  6,   40,   7,  4,  200, "g",    "rice",           "carb_base",    True),
    "watermelon":            ( 46,  1,   12,   0,  1,  100, "g",    "snack",          "snack",        True),
    "white matar curry":     (190,  8,   28,   7,  7,  150, "g",    "curry",          "protein_main", True),
}


def determine_protein_level(protein_g: float) -> str:
    if protein_g < 5:
        return "low"
    elif protein_g < 15:
        return "medium"
    return "high"


def load_database():
    with open(DATABASE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_database(data):
    with open(DATABASE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def query_open_food_facts(name: str) -> dict | None:
    """
    Fallback: try Open Food Facts search API (free, no key).
    Returns a dict with nutrition keys or None if not found.
    """
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 3,
        "fields": "product_name,nutriments",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        products = resp.json().get("products", [])
        for product in products:
            nm = product.get("nutriments", {})
            cal = nm.get("energy-kcal_100g") or nm.get("energy-kcal")
            if cal and float(cal) > 0:
                return {
                    "calories":  round(float(cal)),
                    "protein":   round(float(nm.get("proteins_100g",  0)), 1),
                    "carbs":     round(float(nm.get("carbohydrates_100g", 0)), 1),
                    "fat":       round(float(nm.get("fat_100g",  0)), 1),
                    "fiber":     round(float(nm.get("fiber_100g", 0)), 1),
                }
    except Exception as e:
        print(f"    Open Food Facts error: {e}")
    return None


def apply_nutrition(item: dict, cal, pro, carb, fat, fib, ss, su, dt, cat, veg) -> None:
    """Write all nutrition fields onto the item dict in-place."""
    item["calories"]     = int(cal)
    item["protein"]      = round(float(pro), 1)
    item["carbs"]        = round(float(carb), 1)
    item["fat"]          = round(float(fat), 1)
    item["fiber"]        = round(float(fib), 1)
    item["serving_size"] = int(ss)
    item["serving_unit"] = su
    item["protein_level"]= determine_protein_level(float(pro))
    if dt:
        item["dish_type"] = dt
    if cat:
        item["category"] = cat
    item["veg"] = veg


def main():
    print("=" * 60)
    print("  Portion Vision - Nutrition Updater")
    print("=" * 60)

    db = load_database()
    total    = len(db)
    updated  = 0
    api_hit  = 0
    skipped  = 0

    for i, item in enumerate(db):
        name = item.get("name", "").strip().lower()
        if not name:
            skipped += 1
            continue

        print(f"\n[{i+1}/{total}] {name}")

        # --- Primary source: curated lookup ---
        if name in CURATED:
            cal, pro, carb, fat, fib, ss, su, dt, cat, veg = CURATED[name]
            apply_nutrition(item, cal, pro, carb, fat, fib, ss, su, dt, cat, veg)
            updated += 1
            print(f"    ✓ curated  | {cal} kcal | P:{pro}g C:{carb}g F:{fat}g")

        # --- Fallback: Open Food Facts API ---
        else:
            print(f"    Not in curated table - querying Open Food Facts ...")
            data = query_open_food_facts(name)
            time.sleep(0.5)   # polite delay

            if data:
                # For API results we don't know the exact serving, default 100g
                existing_ss = item.get("serving_size") or 100
                existing_su = item.get("serving_unit") or "g"
                apply_nutrition(
                    item,
                    data["calories"], data["protein"], data["carbs"],
                    data["fat"],      data["fiber"],
                    existing_ss, existing_su,
                    item.get("dish_type", ""), item.get("category", ""),
                    item.get("veg", True),
                )
                api_hit += 1
                updated += 1
                print(f"    ✓ API      | {data['calories']} kcal | P:{data['protein']}g C:{data['carbs']}g F:{data['fat']}g")
            else:
                skipped += 1
                print(f"    ✗ No data found - keeping existing values.")

    # Save once at the end
    save_database(db)
    print("\n" + "=" * 60)
    print(f"  Done! Updated: {updated} ({api_hit} via API) | Skipped: {skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()
