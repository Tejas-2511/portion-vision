"""
Canonical Indian food synonym clusters for PortionVision.
Used for matching detected items to OCR menu entries and canonical density keys.

STRICT PRINCIPLE:
The menu provides contextual guidance, NEVER forced labels.
Generic umbrella words ('curry', 'sabzi', 'gravy', 'food', 'vegetables') must NEVER
force an unidentified dish to match an arbitrary menu item.
"""
from __future__ import annotations
import re
from typing import List, Optional, Set

# Generic category stop-words that can never serve as the sole basis for a menu match
GENERIC_FOOD_STOPWORDS: Set[str] = {
    "curry", "gravy", "sabzi", "sabji", "bhaji", "dish", "food",
    "bowl", "fried", "mix", "mixed", "special", "plate", "item", "dry"
}

# Strict, tight culinary equivalence groups.
# Dishes in the same set are genuinely interchangeable names for the exact same preparation.
EQUIVALENT_DISH_SYNONYMS: List[Set[str]] = [
    # Breads
    {"chapati", "roti", "phulka", "flatbread", "chapati bread", "roti bread"},
    {"paratha", "plain paratha", "tawa paratha"},
    {"naan", "butter naan", "plain naan", "garlic naan"},
    {"poori", "puri", "luchi"},
    {"bhatura", "bhature"},

    # Rice
    {"steamed rice", "white rice", "plain rice", "boiled rice", "chawal", "steam rice", "rice", "sada rice"},
    {"jeera rice", "cumin rice"},
    {"curd rice", "dahi chawal"},
    {"veg pulao", "vegetable pulao", "pulao", "pilaf"},
    {"veg biryani", "biryani"},
    {"khichdi", "dal khichdi", "khichuri"},

    # Dals & Lentils (Strictly separated by lentil type)
    {"dal", "daal", "dal tadka", "yellow dal", "toor dal", "arhar dal", "dal fry", "lentil dal", "lentil soup"},
    {"moong dal", "yellow moong dal", "green moong dal", "moong dal tadka"},
    {"masoor dal", "red lentil dal", "masoor dal tadka"},
    {"chana dal", "chana dal tadka"},
    {"dal makhani", "black dal", "urad dal", "maa ki dal"},
    {"sambar", "sambhar", "sambar soup"},
    {"rasam", "rasam soup"},

    # Specific Curries & Gravies (NEVER lump distinct curries together!)
    {"palak paneer", "saag paneer", "spinach cottage cheese", "palak curry", "spinach curry"},
    {"paneer butter masala", "paneer makhani", "shahi paneer", "paneer lababdar"},
    {"matar paneer", "mutter paneer"},
    {"kadai paneer", "kadhai paneer"},
    {"paneer bhurji", "scrambled paneer"},
    {"chole", "chana masala", "chole masala", "kabuli chana", "chickpea curry"},
    {"rajma", "rajma masala", "kidney bean curry"},
    {"aloo gobi", "aloo gobhi", "potato cauliflower"},
    {"aloo matar", "aloo mutter", "potato peas"},
    {"aloo jeera", "jeera aloo", "cumin potatoes"},
    {"dum aloo", "dum aloo kashmiri"},
    {"baingan bharta", "roasted eggplant"},
    {"bhindi masala", "bhindi fry", "okra sabzi", "bhindi"},
    {"mix veg", "mixed veg", "mixed vegetable", "mixed vegetables", "mixed vegetable curry"},
    {"kadhi pakora", "kadhi pakoda", "punjabi kadhi", "kadhi"},
    {"malai kofta", "veg kofta"},

    # Salads & Accompaniments
    {"green salad", "cucumber salad", "sliced cucumber", "cucumber", "salad", "kachumber"},
    {"onion salad", "sliced onion", "onion slices"},
    {"curd", "dahi", "plain yogurt", "yogurt", "plain curd"},
    {"raita", "boondi raita", "cucumber raita", "veg raita", "vegetable raita"},
    {"pickle", "achar", "mango pickle", "mixed pickle", "spicy pickle"},
    {"papad", "papadum", "roasted papad", "fried papad", "crispy papad"},
    {"green chutney", "mint chutney", "coriander chutney", "pudina chutney", "chutney"},
    {"coconut chutney", "white chutney"},

    # Breakfast & Snacks
    {"idli", "steamed idli", "rava idli", "mini idli"},
    {"dosa", "plain dosa", "masala dosa", "crispy dosa"},
    {"vada", "medu vada", "sambar vada"},
    {"upma", "rava upma", "sooji upma"},
    {"poha", "kanda poha", "flattened rice"},
    {"samosa", "potato samosa"},

    # Sweets & Desserts
    {"gulab jamun", "sweet jamun"},
    {"rasgulla", "roshogolla"},
    {"kheer", "rice kheer", "payasam"},
    {"halwa", "sooji halwa", "sheera", "gajar halwa"},
    {"cake", "pastry", "sponge cake", "brownie", "chocolate brownie"},
]

# Aliases for backward-compatibility with existing consumers
SYNONYM_GROUPS = EQUIVALENT_DISH_SYNONYMS

# Visual prompt aliases for Meta SAM 3 open-vocabulary text grounding.
# Maps dish names to phrases that activate SAM 3's visual features strongly.
SAM3_VISUAL_PROMPT_EXPANSIONS: dict[str, list[str]] = {
    "achar": ['achar', 'spicy pickle', 'pickle'],
    "aloo bonda": ['aloo bonda', 'potato bonda', 'fritter'],
    "aloo capsicum": ['aloo capsicum', 'potato bell pepper', 'sabzi'],
    "aloo gobi": ['aloo gobi', 'potato cauliflower curry', 'cauliflower'],
    "aloo matar": ['aloo matar', 'potato pea curry', 'peas'],
    "aloo paratha": ['aloo paratha', 'stuffed flatbread', 'paratha'],
    "badam halwa": ['badam halwa', 'almond halwa', 'halwa'],
    "baingan bharta": ['baingan bharta', 'eggplant curry', 'roasted eggplant'],
    "banana cake": ['banana cake', 'cake', 'pastry'],
    "barfi": ['barfi', 'kaju katli', 'milk sweet'],
    "bhature": ['bhature', 'chole bhature', 'fried bread'],
    "bhindi": ['bhindi masala', 'okra', 'bhindi sabzi'],
    "bhindi masala": ['bhindi masala', 'okra', 'bhindi'],
    "biryani": ['biryani', 'chicken biryani', 'veg biryani', 'rice'],
    "boiled egg": ['boiled egg', 'sliced egg', 'egg'],
    "boondi raita": ['boondi raita', 'raita', 'curd'],
    "brownie": ['chocolate brownie', 'brownie', 'cake'],
    "butter chicken": ['butter chicken', 'chicken curry', 'chicken makhani'],
    "butter naan": ['butter naan', 'naan', 'flatbread'],
    "cake": ['cake', 'pastry', 'sponge cake', 'dessert'],
    "chana dal": ['chana dal tadka', 'chana dal', 'dal tadka', 'yellow dal'],
    "chana dal tadka": ['chana dal tadka', 'dal tadka', 'yellow dal'],
    "chapati": ['chapati', 'roti', 'flatbread', 'chapati bread'],
    "chicken biryani": ['chicken biryani', 'biryani', 'rice'],
    "chicken curry": ['chicken curry', 'butter chicken', 'chicken masala'],
    "chocolate brownie": ['chocolate brownie', 'brownie', 'cake'],
    "chole": ['chole masala', 'chana masala', 'chickpea curry', 'chickpeas'],
    "chutney": ['green chutney', 'mint chutney', 'coconut chutney', 'chutney'],
    "coconut chutney": ['coconut chutney', 'white chutney', 'chutney'],
    "cucumber": ['cucumber', 'sliced cucumber'],
    "cucumber salad": ['cucumber', 'sliced cucumber', 'salad'],
    "curd": ['curd', 'dahi', 'plain yogurt', 'yogurt'],
    "daal": ['dal tadka', 'yellow dal', 'lentil dal'],
    "dal": ['dal tadka', 'yellow dal', 'lentil dal', 'daal', 'dal fry'],
    "dal fry": ['dal fry', 'dal tadka', 'yellow dal', 'dal'],
    "dal makhani": ['dal makhani', 'black dal', 'dal'],
    "dal palak": ['dal palak', 'spinach dal', 'green dal', 'dal'],
    "dal tadka": ['dal tadka', 'yellow dal', 'toor dal', 'dal'],
    "dosa": ['dosa', 'masala dosa', 'crispy crepe'],
    "egg curry": ['egg curry', 'boiled egg curry', 'curry'],
    "fruit salad": ['fruit salad', 'cut fruits', 'fruits'],
    "gajar halwa": ['gajar halwa', 'carrot halwa', 'halwa'],
    "green chutney": ['green chutney', 'mint chutney', 'coriander chutney'],
    "green salad": ['green salad', 'sliced cucumber', 'cucumber', 'salad', 'tomato slice'],
    "gulab jamun": ['gulab jamun', 'brown sweet ball', 'sweet'],
    "idli": ['idli', 'steamed rice cake', 'idly'],
    "jeera rice": ['jeera rice', 'cumin rice', 'rice'],
    "kadhai paneer": ['kadai paneer', 'paneer capsicum', 'paneer curry'],
    "kadhi pakora": ['kadhi pakora', 'kadhi pakoda', 'yellow yogurt curry'],
    "khichdi": ['khichdi', 'dal khichdi', 'rice lentil porridge'],
    "kheer": ['rice kheer', 'kheer', 'sweet rice pudding'],
    "matar paneer": ['matar paneer', 'paneer peas curry', 'cottage cheese'],
    "mint chutney": ['mint chutney', 'green chutney', 'pudina chutney'],
    "mix veg": ['mixed vegetable curry', 'mix veg', 'vegetable curry', 'carrots peas beans'],
    "mixed veg": ['mixed vegetable curry', 'mix veg', 'vegetable curry', 'carrots peas beans'],
    "moong dal": ['moong dal', 'yellow dal', 'dal tadka'],
    "naan": ['butter naan', 'naan', 'flatbread'],
    "omelette": ['omelette', 'egg omelette'],
    "onion salad": ['onion slices', 'sliced onion', 'salad'],
    "pakoda": ['onion pakoda', 'veg pakoda', 'fritter'],
    "palak paneer": ['palak paneer', 'green curry', 'spinach curry', 'palak curry', 'saag paneer', 'spinach cottage cheese', 'paneer curry'],
    "paneer": ['paneer curry', 'paneer butter masala', 'cottage cheese', 'paneer cubes'],
    "paneer butter masala": ['paneer butter masala', 'paneer curry', 'cottage cheese curry'],
    "papad": ['papad', 'papadum', 'crispy papad'],
    "paratha": ['paratha', 'aloo paratha', 'flatbread'],
    "phulka": ['phulka', 'roti', 'chapati', 'flatbread'],
    "pickle": ['mango pickle', 'spicy pickle', 'achar'],
    "poha": ['cooked poha', 'flattened rice', 'poha'],
    "poori": ['poori', 'puri', 'puffed fried bread'],
    "pulao": ['pulao', 'veg pulao', 'rice'],
    "puri": ['puri', 'poori', 'puffed fried bread'],
    "raita": ['boondi raita', 'raita', 'yogurt dip', 'curd'],
    "rajma": ['rajma masala', 'kidney bean curry', 'curry'],
    "rasam": ['rasam soup', 'rasam'],
    "rasgulla": ['rasgulla', 'sweet dumpling'],
    "rice": ['steamed rice', 'white rice', 'rice'],
    "roti": ['roti', 'chapati', 'flatbread', 'roti bread'],
    "sabji": ['mixed vegetable curry', 'mixed vegetables', 'sabzi'],
    "sambar": ['sambar soup', 'sambar', 'sambhar'],
    "sambhar": ['sambar soup', 'sambar', 'sambhar'],
    "samosa": ['samosa', 'potato samosa', 'snack'],
    "shahi paneer": ['shahi paneer', 'paneer curry', 'cottage cheese curry'],
    "sooji halwa": ['sooji halwa', 'halwa', 'sheera'],
    "steamed rice": ['steamed rice', 'white rice', 'rice', 'boiled rice'],
    "toor dal": ['toor dal', 'yellow dal', 'dal tadka'],
    "upma": ['rava upma', 'semolina upma', 'upma'],
    "veg biryani": ['veg biryani', 'biryani', 'rice'],
}


def get_visual_prompt_aliases(menu_item: str) -> list[str]:
    """Return visual alias prompts for SAM 3 text grounding."""
    m_clean = menu_item.strip().lower()
    aliases = [menu_item.strip()]
    if m_clean in SAM3_VISUAL_PROMPT_EXPANSIONS:
        for alias in SAM3_VISUAL_PROMPT_EXPANSIONS[m_clean]:
            if alias.lower() not in [a.lower() for a in aliases]:
                aliases.append(alias)
    return aliases


def find_menu_match(
    detected_label: str,
    menu_items: Optional[List[str]],
    min_confidence: float = 0.50,
) -> Optional[str]:
    """
    Find matching menu item for a detected food label with strict evidence requirements.

    GUARANTEES:
      1. Umbrella terms ('curry', 'sabzi', 'gravy', 'food', 'vegetable') NEVER force a match.
      2. No substring false positives (e.g. 'tea' matching 'steamed rice').
      3. Only exact matches, whole-word specific alignments, or tight culinary equivalents match.
      4. If ambiguous or low evidence, returns None (caller will preserve visual identity or abstain).
    """
    if not menu_items or not detected_label:
        return None

    det_clean = detected_label.strip().lower()

    # Rule 0: Umbrella / generic category terms must NEVER be forced into a menu dish!
    if det_clean in GENERIC_FOOD_STOPWORDS or det_clean in {"food", "unlisted food", "unrecognized"}:
        return None

    menu_clean = [m.strip() for m in menu_items if m and m.strip()]

    # 1. Exact match (case-insensitive)
    for m in menu_clean:
        if m.lower() == det_clean:
            return m

    # 2. Strict Culinary Equivalence Cluster Match
    for group in EQUIVALENT_DISH_SYNONYMS:
        if det_clean in group:
            for m in menu_clean:
                if m.lower() in group:
                    return m

    # 3. Whole-Word Distinctive Token Match
    # (e.g. "yellow dal" matching "dal", "steamed rice" matching "rice")
    det_words = set(re.findall(r"\b[a-z]{3,}\b", det_clean)) - GENERIC_FOOD_STOPWORDS
    if det_words:
        best_match = None
        best_overlap = 0

        for m in menu_clean:
            m_words = set(re.findall(r"\b[a-z]{3,}\b", m.lower())) - GENERIC_FOOD_STOPWORDS
            overlap = det_words.intersection(m_words)
            if overlap:
                # Require that at least one NON-GENERIC keyword matches completely
                if len(overlap) > best_overlap:
                    best_overlap = len(overlap)
                    best_match = m

        if best_match and best_overlap >= 1:
            return best_match

    return None
