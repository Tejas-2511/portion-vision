"""
Canonical Indian food synonym clusters for PortionVision.
Used for matching detected items to OCR menu entries and canonical density keys.
Expanded from backend/data/foodDatabase.json covering 460+ dishes.
"""
from typing import List, Optional

SYNONYM_GROUPS: list[set[str]] = [
    {'butter naan', 'bread toast', 'sev puri', 'garlic naan', 'pav', 'tandoori roti', 'chapati', 'methi thepla', 'veg paratha', 'bhel puri', 'bread butter', 'paneer paratha', 'palak poori', 'kulcha', 'bhature', 'chapati bread', 'bread jam', 'puri bhaji', 'phulka', 'puri', 'thepla', 'papad', 'poori', 'pani poori', 'luchi', 'naan', 'roti', 'veg kolhapuri', 'pani puri', 'rumali roti', 'bread', 'missi roti', 'aloo paratha', 'aloo poori', 'roti bread', 'gobi paratha', 'bhatura', 'masala puri', 'paratha', 'flatbread'},
    {'veg pulao', 'corn pulao', 'chole rice', 'masala bhat', 'boiled rice', 'fish curry rice', 'moti rice', 'vegetable pulao', 'biryani', 'tamarind rice', 'pilaf', 'rice kheer', 'veg pongal', 'bagara rice', 'methi rice', 'steamed rice', 'rice', 'green peas pulao', 'chicken fried rice', 'onion rice', 'lemon rice', 'bisi bele bath', 'veg biryani', 'masala rice', 'sabudana khichdi', 'ghee rice', 'jeera pulao', 'plain rice', 'egg biryani', 'curd rice', 'pongal', 'chawal', 'mutton biryani', 'veg fried rice', 'white rice', 'tomato rice', 'rajma chawal', 'pulihora', 'kadhi chawal', 'chitranna', 'jeera rice', 'steam rice', 'egg fried rice', 'chicken biryani', 'sada rice', 'coconut rice', 'khichdi', 'onion pulao', 'vangi bath', 'garlic khichdi', 'pulao', 'fried rice'},
    {'green moong dal', 'methi dal', 'green moong dal khichdi', 'dal khichdi', 'lobia dal', 'dal vada curry', 'sweet daliya', 'dal dakshani', 'rasam', 'palak chana dal', 'sambar rice', 'dal tadka', 'dal palak', 'lahsuni dal', 'moong dal tadka', 'masoor dal', 'sambar', 'yellow moong dal', 'dal', 'dal panchmail', 'chilka moong dal', 'langarwali dal', 'arhar dal', 'moong dal khichdi', 'dal makhani', 'daal', 'dal banjara', 'sindhi dal', 'daliya', 'chana dal', 'dal panchratan', 'dal amritsari', 'dal fry', 'dal pakoda', 'green moong dal tadka', 'khatti dal', 'mix dal tadka', 'tomato pappu', 'lentil dal', 'smoked dal', 'dal rice', 'lentil curry', 'toor dal tadka', 'moong dal cheela', 'lentils', 'moong dal halwa', 'red masoor dal tadka', 'mix dal', 'black urad dal', 'dal curry', 'sambar vada', 'sambhar', 'palak dal', 'black masoor dal', 'lauki chana dal', 'masoor dal tadka', 'yellow dal', 'tomato dal fry', 'lentil soup', 'lentil', 'chana dal tadka', 'chana dal sabzi', 'chana dal burfi'},
    {'aloo pyaaz', 'dum aloo kashmiri', 'egg curry', 'methi aloo', 'chicken momos', 'chicken chettinad', 'matar mushroom', 'cabbage carrot', 'sabzi', 'lauki sabzi', 'egg methi keema masala', 'cabbage matar', 'black chana', 'egg keema masala', 'paneer makhan wala', 'sem fhali', 'sabji', 'gajar matar sabzi', 'chicken korma', 'bhaji', 'chole', 'corn capsicum', 'paneer do payza', 'mixed vegetables', 'palak black chana', 'aloo capsicum', 'rajma masala', 'mushroom masala', 'chana curry', 'aloo matar', 'paneer tikka', 'bhindi fry', 'aloo bonda', 'carrot beans poriyal', 'paneer bhurji', 'lobiya masala', 'aloo bhujia', 'chana masala', 'malai kofta', 'paneer handi', 'methi matar chaman', 'corn palak', 'dum aloo', 'aloo jeera', 'kadhai paneer', 'kootu', 'veg kofta curry', 'chicken do pyaza', 'shimla mirch sabzi', 'tandoori chicken', 'biresra kadhi', 'curry', 'shahi paneer', 'rajma', 'kadhai chicken', 'chaap makhani', 'paneer do pyaza', 'karela fry', 'chilli paneer', 'white matar curry', 'keema masala', 'carrot capsicum', 'aloo papdi chaat', 'mutton curry', 'cabbage poriyal', 'soya chunk curry', 'mixed vegetable curry', 'mixed veg', 'paneer puff', 'chicken roll', 'karela masala', 'aloo methi', 'achari kaddu', 'gutta curry', 'tinda masala', 'mix veg', 'black chana masala', 'matar mushroom masala', 'aloo', 'rajasthani kadhi', 'avial', 'chicken tikka', 'bhindi', 'paneer butter masala', 'chicken curry', 'matar paneer', 'beans poriyal', 'masala chai', 'chole masala', 'gobhi masala', 'chicken', 'aloo gobi', 'tori sabzi', 'vegetable chettinad', 'soya chaap masala', 'paneer tikka masala', 'kadhi pakora', 'anda curry', 'masala dosa', 'patiyala murgh', 'paneer chat pata', 'baingan', 'gravy', 'sev tamatar sabzi', 'murgh adraki', 'butter chicken', 'gobhi aloo', 'gajar matar', 'palak paneer', 'murgh hydrabadi curry', 'kaddu sabzi', 'arbi masala', 'vegetable curry', 'baingan masala', 'kadai paneer', 'baingan bharta', 'cabbage sabzi', 'chaap masala', 'murgh saag wala', 'aloo palak', 'kadhai veg', 'matar sabzi', 'pumpkin sabzi', 'kadhi pakoda', 'chicken soup', 'aloo sem phali', 'soya masala', 'kabuli chana', 'gobi', 'veg hariyali', 'khatta meetha kaddu', 'paneer', 'sev tamatar', 'bhindi masala', 'onion kadhi', 'fish curry', 'lauki chana', 'aloo tamatar', 'lauki kofta curry', 'subzi miloni', 'aloo tikki', 'chilli chicken', 'parwal sabzi', 'palak sabzi', 'gobhi matar', 'chicken masala', 'egg masala'},
    {'salad vegetables', 'cucumber', 'kabuli chana chaat', 'salad', 'cucumber salad', 'sprouts salad', 'beetroot', 'onion salad', 'fruit salad', 'green salad', 'sliced cucumber', 'kachumber', 'onion', 'tomato'},
    {'green chutney', 'onion chutney', 'mango pickle', 'green chilli fry', 'fryum', 'lemon pickle', 'mint chutney', 'gunpowder podi', 'peanut chutney', 'tomato chilli chutney', 'tomato chutney', 'fried chilli', 'dip', 'pickle', 'ghee', 'jam', 'papad mangodi', 'papad', 'chutney', 'coconut chutney', 'butter', 'mixed pickle', 'garlic chutney', 'tamarind chutney', 'sauce', 'achar'},
    {'plain curd', 'cucumber raita', 'veg raita', 'lauki raita', 'raita', 'dahi', 'curd', 'curd vada', 'boondi raita', 'yogurt'},
    {'rasgulla', 'shrikhand', 'basundi', 'sabudana kheer', 'halwa', 'coconut laddu', 'sevai kheer', 'banana cake', 'dessert', 'jalebi', 'sandesh', 'sewai kheer', 'mysore pak', 'phirni', 'shakar para', 'kaju katli', 'barfi', 'kheer', 'rava kesari', 'laddu', 'pineapple halwa', 'sweet', 'pastry', 'kesari bhat', 'rabdi boondi', 'gujiya', 'malpua', 'badam halwa', 'fruit custard', 'kalakand', 'besan laddu', 'ras malai', 'sheera', 'coconut burfi', 'moti chur ke laddu', 'payasam', 'cake', 'gajar halwa', 'chocolate brownie', 'suji halwa', 'cupcake', 'gulab jamun', 'sakkara pongal', 'semiya payasam', 'ice cream', 'sponge cake', 'kesar phirni', 'custard', 'rabdi', 'brownie'},
    {'egg roll', 'scrambled egg', 'boiled egg', 'egg curry', 'egg puff', 'egg bhurji', 'kesariya thandai', 'egg', 'omelette', 'thandai', 'anda', 'bread omelette', 'anda curry'},
    {'medu vada', 'onion dosa', 'porridge', 'pesarattu', 'veg upma', 'mini idli', 'cheela', 'plain dosa', 'appam', 'idli', 'upma', 'set dosa', 'masala dosa', 'vada', 'dosa', 'oats porridge', 'rava idli', 'vada pav', 'semiya upma', 'rava dosa', 'rava upma', 'poha', 'uttapam'},
    {'jaljeera', 'sweet lassi', 'mango lassi', 'badam milk', 'cornfalkes with hot milk', 'bornvita', 'tea/coffee', 'hot and sour soup', 'beverage', 'mixed veg soup', 'nimbu pani', 'manchow soup', 'sweet corn soup', 'tomato soup', 'chaas', 'lemon water', 'butter milk', 'rooh afza', 'banana milkshake', 'aam panna', 'bournvita milk', 'flavored milk', 'milk', 'drink', 'jal jeera', 'coffee', 'cornflakes with hot milk', 'ice tea', 'cold milk', 'tea', 'lassi', 'hot milk'},
]

# Visual prompt aliases for Meta SAM 3 open-vocabulary text grounding.
# Maps common menu dish names to phrases that activate SAM 3's visual features strongly.
SAM3_VISUAL_PROMPT_EXPANSIONS: dict[str, list[str]] = {
    "achar": ['achar', 'spicy pickle', 'pickle'],
    "aloo bonda": ['aloo bonda', 'potato bonda', 'fritter'],
    "aloo capsicum": ['aloo capsicum', 'potato bell pepper', 'sabzi'],
    "aloo gobi": ['aloo gobi', 'potato cauliflower curry', 'vegetable curry'],
    "aloo matar": ['aloo matar', 'potato pea curry', 'vegetable curry'],
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
    "chole": ['chole masala', 'chana masala', 'chickpea curry'],
    "chutney": ['green chutney', 'mint chutney', 'coconut chutney', 'chutney'],
    "coconut chutney": ['coconut chutney', 'white chutney', 'chutney'],
    "cucumber": ['cucumber', 'sliced cucumber'],
    "cucumber salad": ['cucumber', 'sliced cucumber', 'salad'],
    "curd": ['curd', 'dahi', 'plain yogurt', 'yogurt'],
    "daal": ['dal tadka', 'yellow dal', 'lentil dal'],
    "dal": ['dal tadka', 'yellow dal', 'lentil dal', 'daal', 'dal fry'],
    "dal fry": ['dal fry', 'dal tadka', 'yellow dal', 'dal'],
    "dal makhani": ['dal makhani', 'black dal', 'dal'],
    "dal palak": ['dal palak', 'palak dal', 'dal tadka'],
    "dal tadka": ['dal tadka', 'yellow dal', 'dal fry', 'dal'],
    "dosa": ['masala dosa', 'plain dosa', 'crispy crepe'],
    "egg bhurji": ['egg bhurji', 'scrambled egg', 'egg'],
    "egg curry": ['egg curry', 'boiled egg curry', 'anda curry'],
    "fried rice": ['fried rice', 'veg fried rice', 'rice'],
    "green chutney": ['green chutney', 'mint chutney', 'coriander chutney'],
    "green salad": ['cucumber', 'sliced cucumber', 'green salad', 'salad'],
    "gulab jamun": ['gulab jamun', 'sweet dumpling', 'dessert'],
    "halwa": ['sooji halwa', 'halwa', 'gajar halwa'],
    "idli": ['steamed idli', 'idli', 'rice cake'],
    "jalebi": ['jalebi', 'crispy sweet'],
    "jeera rice": ['jeera rice', 'cumin rice', 'rice'],
    "kheer": ['kheer', 'rice pudding', 'payasam'],
    "khichdi": ['khichdi', 'dal khichdi', 'rice porridge'],
    "laddu": ['motichoor laddu', 'besan laddu', 'laddu'],
    "masala dosa": ['masala dosa', 'crispy dosa', 'dosa'],
    "matar paneer": ['matar paneer', 'paneer pea curry', 'paneer curry'],
    "mint chutney": ['mint chutney', 'green chutney', 'pudina chutney'],
    "mix veg": ['vegetable curry', 'mixed vegetable curry', 'mixed vegetables', 'sabzi'],
    "mixed veg": ['vegetable curry', 'mixed vegetable curry', 'mixed vegetables', 'sabzi'],
    "moong dal": ['moong dal', 'yellow dal', 'dal tadka'],
    "naan": ['butter naan', 'naan', 'flatbread'],
    "omelette": ['omelette', 'egg omelette'],
    "onion salad": ['onion slices', 'sliced onion', 'salad'],
    "pakoda": ['onion pakoda', 'veg pakoda', 'fritter'],
    "palak paneer": ['palak paneer', 'spinach cottage cheese', 'paneer curry'],
    "paneer": ['paneer curry', 'paneer butter masala', 'cottage cheese'],
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
    "sabji": ['vegetable curry', 'mixed vegetables', 'curry', 'sabji'],
    "sabzi": ['vegetable curry', 'mixed vegetables', 'curry', 'sabzi'],
    "sada rice": ['steamed rice', 'white rice', 'rice'],
    "salad": ['cucumber', 'sliced cucumber', 'green salad', 'salad'],
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


def find_menu_match(detected_label: str, menu_items: Optional[List[str]]) -> Optional[str]:
    """
    Find matching menu item for a detected food label using exact, substring,
    and Indian food synonym cluster matching.
    """
    if not menu_items:
        return None
    det_lower = detected_label.strip().lower()

    # 1. Exact match
    for m in menu_items:
        if m.strip().lower() == det_lower:
            return m.strip()

    # 2. Substring match
    for m in menu_items:
        m_lower = m.strip().lower()
        if (len(m_lower) >= 3 and m_lower in det_lower) or (len(det_lower) >= 3 and det_lower in m_lower):
            return m.strip()

    # 3. Synonym cluster match
    for group in SYNONYM_GROUPS:
        if det_lower in group:
            for m in menu_items:
                if m.strip().lower() in group:
                    return m.strip()

    return None
