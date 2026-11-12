"""
Monocular depth estimation using Depth Anything 3 (DA3) Metric.

Enhancements over baseline:
  • #1  Hybrid depth — fuses Depth Anything 3 metric depth with 486 per-food geometric priors
  • #4  Ellipse-based scale calibration — fits an ellipse to the plate rim
        for a more accurate cm-per-pixel estimate
  • #5  Gaussian smoothing before returning the depth map to suppress noise
  • #10 2D Planar Surface Normal Fitting — fits a continuous reference plane
        Z_plate(x, y) = Ax + By + C to plate rim/dividers to eliminate camera tilt slant

Produces physical metric depth in meters, calibrated and planar-normalized so
the plate surface is the exact zero-height baseline.
"""

from __future__ import annotations

import time
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy-loaded global model ─────────────────────────────────────────────────
_depth_model     = None
_depth_device    = None
_is_metric       = False


def is_metric_depth() -> bool:
    """Return whether the loaded depth model produces physical metric depth."""
    return _is_metric

# ── Food-specific height priors (min_cm, max_cm) ─────────────────────────────
# Used by apply_food_height_prior() to clamp and blend Depth Anything output.
FOOD_HEIGHT_PRIORS: dict[str, tuple[float, float]] = {
    "aam panna": (1.0, 3.5),
    "achar": (0.5, 2.0),
    "achari kaddu": (0.5, 2.0),
    "aloo": (2.0, 5.0),
    "aloo bhujia": (2.0, 4.5),
    "aloo bonda": (1.5, 4.5),
    "aloo capsicum": (2.0, 5.0),
    "aloo gobi": (2.0, 4.5),
    "aloo jeera": (2.0, 4.5),
    "aloo matar": (2.0, 4.5),
    "aloo methi": (2.0, 4.5),
    "aloo palak": (2.0, 4.5),
    "aloo papdi chaat": (1.5, 4.5),
    "aloo paratha": (0.5, 2.0),
    "aloo poori": (0.4, 1.8),
    "aloo pyaaz": (2.0, 4.5),
    "aloo sem phali": (2.0, 4.5),
    "aloo tamatar": (2.0, 4.5),
    "aloo tikki": (1.5, 4.5),
    "anda curry": (2.0, 5.0),
    "appam": (0.3, 0.8),
    "apple": (1.5, 4.5),
    "apple slices": (1.5, 4.5),
    "arbi masala": (2.0, 4.5),
    "arhar dal": (1.5, 3.5),
    "avial": (2.0, 4.5),
    "badam halwa": (1.5, 4.0),
    "badam milk": (1.0, 3.5),
    "bagara rice": (1.5, 4.5),
    "baingan": (2.0, 4.5),
    "baingan bharta": (2.0, 4.5),
    "baingan masala": (2.0, 4.5),
    "banana": (1.5, 4.5),
    "banana cake": (1.5, 3.5),
    "banana milkshake": (1.0, 3.5),
    "barfi": (1.0, 2.5),
    "basundi": (1.5, 4.0),
    "beans poriyal": (2.0, 4.5),
    "besan cheela": (1.5, 4.5),
    "besan laddu": (2.5, 5.5),
    "bhaji": (2.0, 4.5),
    "bhature": (0.4, 1.8),
    "bhel puri": (1.5, 4.5),
    "bhindi": (2.0, 4.5),
    "bhindi fry": (2.0, 4.5),
    "bhindi masala": (2.0, 4.5),
    "biresra kadhi": (1.5, 3.5),
    "biryani": (2.0, 5.0),
    "biscuit": (1.5, 4.5),
    "bisi bele bath": (1.5, 4.5),
    "black chana": (2.0, 4.5),
    "black chana masala": (2.0, 4.5),
    "black masoor dal": (1.5, 3.5),
    "black urad dal": (1.5, 3.5),
    "boiled egg": (2.5, 5.0),
    "boondi": (1.5, 4.5),
    "boondi raita": (1.5, 3.0),
    "bornvita": (1.0, 3.5),
    "bournvita milk": (1.0, 3.5),
    "bread": (1.5, 3.5),
    "bread butter": (0.4, 1.8),
    "bread jam": (0.4, 1.8),
    "bread omelette": (0.4, 1.8),
    "bread pakoda": (0.4, 1.8),
    "bread toast": (0.4, 1.8),
    "brownie": (1.5, 3.5),
    "butter": (0.5, 2.0),
    "butter chicken": (2.0, 5.0),
    "butter milk": (1.0, 3.5),
    "butter naan": (0.4, 1.8),
    "cabbage carrot": (2.0, 4.5),
    "cabbage matar": (2.0, 4.5),
    "cabbage poriyal": (2.0, 4.5),
    "cabbage sabzi": (2.0, 5.0),
    "cake": (1.5, 3.5),
    "carrot beans poriyal": (2.0, 4.5),
    "carrot capsicum": (2.0, 4.5),
    "chaap makhani": (2.0, 4.5),
    "chaap masala": (2.0, 4.5),
    "chaas": (1.0, 3.5),
    "chana": (2.0, 4.0),
    "chana curry": (2.0, 5.0),
    "chana dal": (1.5, 3.5),
    "chana dal burfi": (1.5, 3.5),
    "chana dal sabzi": (1.5, 3.5),
    "chana dal tadka": (1.5, 3.5),
    "chana masala": (2.0, 4.5),
    "chapati": (0.4, 1.5),
    "chicken": (2.5, 5.0),
    "chicken biryani": (1.5, 4.5),
    "chicken chettinad": (2.0, 5.0),
    "chicken curry": (2.5, 5.5),
    "chicken do pyaza": (2.0, 5.0),
    "chicken fried rice": (1.5, 4.5),
    "chicken korma": (2.0, 5.0),
    "chicken masala": (2.0, 5.0),
    "chicken momos": (2.0, 5.0),
    "chicken roll": (2.0, 5.0),
    "chicken soup": (2.0, 5.0),
    "chicken tikka": (2.0, 5.0),
    "chikoo": (1.5, 4.5),
    "chilka moong dal": (1.5, 3.5),
    "chilli chicken": (2.0, 5.0),
    "chilli gobi": (1.5, 4.5),
    "chilli paneer": (2.0, 5.0),
    "chitranna": (1.5, 4.5),
    "chocolate brownie": (1.5, 3.5),
    "chole": (2.0, 4.0),
    "chole bhature": (2.0, 5.0),
    "chole masala": (2.0, 5.0),
    "chole rice": (1.5, 4.5),
    "chutney": (0.5, 2.0),
    "coconut burfi": (1.5, 4.0),
    "coconut chutney": (0.5, 2.0),
    "coconut laddu": (2.5, 5.5),
    "coconut rice": (1.5, 4.5),
    "coffee": (1.0, 3.5),
    "cold milk": (1.0, 3.5),
    "corn capsicum": (2.0, 4.5),
    "corn chaat": (1.5, 4.5),
    "corn palak": (2.0, 4.5),
    "corn pulao": (1.5, 4.5),
    "cornfalkes with hot milk": (1.0, 3.5),
    "cornflakes": (1.5, 4.5),
    "cornflakes with hot milk": (1.0, 3.5),
    "cucumber": (0.4, 1.2),
    "cucumber salad": (0.8, 2.5),
    "curd": (1.5, 3.0),
    "curd rice": (1.5, 3.0),
    "curd vada": (1.5, 3.0),
    "custard": (1.5, 4.0),
    "dal": (1.5, 3.5),
    "dal amritsari": (1.5, 3.5),
    "dal banjara": (1.5, 3.5),
    "dal curry": (1.5, 3.5),
    "dal dakshani": (1.5, 3.5),
    "dal fry": (1.5, 3.5),
    "dal khichdi": (1.5, 3.5),
    "dal makhani": (1.5, 3.5),
    "dal pakoda": (1.5, 3.5),
    "dal palak": (1.5, 3.5),
    "dal panchmail": (1.5, 3.5),
    "dal panchratan": (1.5, 3.5),
    "dal rice": (1.5, 3.5),
    "dal tadka": (1.5, 3.5),
    "dal vada curry": (2.0, 4.5),
    "daliya": (1.5, 3.5),
    "dhokla": (1.5, 4.5),
    "dosa": (0.3, 0.8),
    "dum aloo": (2.0, 4.5),
    "dum aloo kashmiri": (2.0, 4.5),
    "egg": (3.0, 5.5),
    "egg bhurji": (2.5, 5.0),
    "egg biryani": (1.5, 4.5),
    "egg curry": (2.0, 4.5),
    "egg fried rice": (1.5, 4.5),
    "egg keema masala": (2.5, 5.0),
    "egg masala": (2.5, 5.0),
    "egg methi keema masala": (2.5, 5.0),
    "egg puff": (2.5, 5.0),
    "egg roll": (2.5, 5.0),
    "fish curry": (2.0, 4.5),
    "fish curry rice": (1.5, 4.5),
    "fish fry": (2.0, 5.0),
    "flavored milk": (1.0, 3.5),
    "fried chilli": (0.5, 2.0),
    "fried rice": (1.5, 4.0),
    "fruit custard": (1.5, 4.0),
    "fruit salad": (0.8, 2.5),
    "fryum": (0.2, 0.5),
    "gajar halwa": (1.5, 4.0),
    "gajar matar": (2.0, 4.5),
    "gajar matar sabzi": (2.0, 5.0),
    "garlic chutney": (0.5, 2.0),
    "garlic khichdi": (1.5, 4.5),
    "garlic naan": (0.4, 1.8),
    "ghee": (0.5, 2.0),
    "ghee rice": (1.5, 4.5),
    "gobhi aloo": (2.0, 4.5),
    "gobhi masala": (2.0, 4.5),
    "gobhi matar": (2.0, 4.5),
    "gobi": (2.0, 4.5),
    "gobi manchurian": (1.5, 4.5),
    "gobi paratha": (0.5, 2.0),
    "grapes": (1.5, 4.5),
    "green chilli fry": (0.5, 2.0),
    "green chutney": (0.5, 2.0),
    "green moong dal": (1.5, 3.5),
    "green moong dal khichdi": (1.5, 3.5),
    "green moong dal tadka": (1.5, 3.5),
    "green peas pulao": (1.5, 4.5),
    "green salad": (0.8, 2.5),
    "grilled sandwich": (1.5, 4.5),
    "guava": (1.5, 4.5),
    "gujiya": (1.5, 4.0),
    "gulab jamun": (3.0, 5.5),
    "gunpowder podi": (0.5, 2.0),
    "gutta curry": (2.0, 5.0),
    "halwa": (2.0, 4.0),
    "hot and sour soup": (1.0, 3.5),
    "hot milk": (1.0, 3.5),
    "ice cream": (1.5, 4.0),
    "ice tea": (1.0, 3.5),
    "idli": (3.0, 5.5),
    "jal jeera": (1.0, 3.5),
    "jalebi": (1.5, 4.0),
    "jaljeera": (1.0, 3.5),
    "jam": (0.5, 2.0),
    "jeera pulao": (1.5, 4.5),
    "jeera rice": (1.5, 4.0),
    "kabuli chana": (2.0, 4.5),
    "kabuli chana chaat": (0.8, 2.5),
    "kachori": (1.5, 4.5),
    "kaddu sabzi": (2.0, 5.0),
    "kadhai chicken": (2.0, 5.0),
    "kadhai paneer": (2.0, 5.0),
    "kadhai veg": (2.0, 4.5),
    "kadhi chawal": (1.5, 3.5),
    "kadhi pakoda": (1.5, 3.5),
    "kadhi pakora": (1.5, 3.5),
    "kaju katli": (1.5, 4.0),
    "kalakand": (1.5, 4.0),
    "karela fry": (2.0, 4.5),
    "karela masala": (2.0, 4.5),
    "keema masala": (2.0, 4.5),
    "kesar phirni": (1.5, 4.0),
    "kesari bhat": (1.5, 4.0),
    "kesariya thandai": (1.0, 3.5),
    "khandvi": (1.5, 4.5),
    "khatta meetha kaddu": (2.0, 4.5),
    "khatti dal": (1.5, 3.5),
    "kheer": (1.5, 3.5),
    "khichdi": (2.0, 5.0),
    "kofta": (2.5, 5.0),
    "kootu": (2.0, 4.5),
    "kulcha": (0.5, 2.0),
    "laddu": (3.5, 6.0),
    "lahsuni dal": (1.5, 3.5),
    "langarwali dal": (1.5, 3.5),
    "lassi": (1.5, 4.0),
    "lauki chana": (2.0, 4.5),
    "lauki chana dal": (1.5, 3.5),
    "lauki kofta curry": (2.0, 5.0),
    "lauki raita": (1.5, 3.0),
    "lauki sabzi": (2.0, 5.0),
    "lemon pickle": (0.5, 2.0),
    "lemon rice": (1.5, 4.5),
    "lemon water": (1.0, 3.5),
    "lobia dal": (1.5, 3.5),
    "lobiya masala": (2.0, 4.5),
    "luchi": (0.4, 1.8),
    "macaroni": (1.5, 4.5),
    "maggi": (1.5, 4.5),
    "malai kofta": (2.0, 4.5),
    "malpua": (1.5, 4.0),
    "manchow soup": (1.0, 3.5),
    "manchurian": (1.5, 4.5),
    "mango": (1.5, 4.5),
    "mango lassi": (1.0, 3.5),
    "mango pickle": (0.5, 2.0),
    "mangoda": (1.5, 4.5),
    "masala bhat": (1.5, 4.5),
    "masala chai": (1.0, 3.5),
    "masala dosa": (0.3, 0.8),
    "masala puri": (1.5, 4.5),
    "masala rice": (1.5, 4.5),
    "masoor dal": (1.5, 3.5),
    "masoor dal tadka": (1.5, 3.5),
    "matar mushroom": (2.0, 4.5),
    "matar mushroom masala": (2.0, 4.5),
    "matar paneer": (2.0, 5.0),
    "matar sabzi": (2.0, 5.0),
    "medu vada": (2.5, 5.0),
    "methi aloo": (2.0, 4.5),
    "methi dal": (1.5, 3.5),
    "methi matar chaman": (2.0, 4.5),
    "methi rice": (1.5, 4.5),
    "methi thepla": (0.4, 1.8),
    "milk": (1.0, 3.0),
    "mini idli": (2.5, 5.0),
    "mint chutney": (0.5, 2.0),
    "mirchi bajji": (1.5, 4.5),
    "misal pav": (1.5, 4.5),
    "missi roti": (0.4, 1.8),
    "mix bhajiya": (1.5, 4.5),
    "mix dal": (1.5, 3.5),
    "mix dal tadka": (1.5, 3.5),
    "mix veg": (2.0, 4.5),
    "mixed pickle": (0.5, 2.0),
    "mixed veg": (2.0, 4.5),
    "mixed veg soup": (1.0, 3.5),
    "mixed vegetable curry": (2.0, 5.0),
    "moong dal cheela": (1.5, 3.5),
    "moong dal halwa": (1.5, 3.5),
    "moong dal khichdi": (1.5, 3.5),
    "moong dal tadka": (1.5, 3.5),
    "mosambi": (1.5, 4.5),
    "moti chur ke laddu": (2.5, 5.5),
    "moti rice": (1.5, 4.5),
    "murgh adraki": (2.0, 4.5),
    "murgh hydrabadi curry": (2.0, 5.0),
    "murgh saag wala": (2.0, 4.5),
    "mushroom masala": (2.0, 4.5),
    "muskmelon": (1.5, 4.5),
    "mutton": (2.5, 5.5),
    "mutton biryani": (1.5, 4.5),
    "mutton curry": (2.0, 5.0),
    "mysore bonda": (1.5, 4.5),
    "mysore pak": (1.5, 4.0),
    "naan": (0.5, 1.8),
    "namkeen": (1.5, 4.5),
    "nimbu pani": (1.0, 3.5),
    "noodles": (1.5, 4.5),
    "oats": (2.0, 4.5),
    "oats porridge": (1.5, 3.5),
    "omelette": (0.5, 2.0),
    "onion chutney": (0.5, 2.0),
    "onion dosa": (0.3, 0.8),
    "onion kadhi": (1.5, 3.5),
    "onion pakoda": (1.5, 4.5),
    "onion pulao": (1.5, 4.5),
    "onion rice": (1.5, 4.5),
    "onion salad": (0.8, 2.5),
    "orange": (1.5, 4.5),
    "orange segments": (1.5, 4.5),
    "palak black chana": (2.0, 4.5),
    "palak chana dal": (1.5, 3.5),
    "palak dal": (1.5, 3.5),
    "palak paneer": (2.0, 5.0),
    "palak poori": (0.4, 1.8),
    "palak sabzi": (2.0, 5.0),
    "paneer": (2.5, 5.0),
    "paneer bhurji": (2.0, 5.0),
    "paneer butter masala": (2.5, 5.0),
    "paneer chat pata": (2.0, 5.0),
    "paneer do payza": (2.0, 5.0),
    "paneer do pyaza": (2.5, 5.0),
    "paneer handi": (2.0, 5.0),
    "paneer makhan wala": (2.0, 5.0),
    "paneer paratha": (0.5, 2.0),
    "paneer puff": (2.0, 5.0),
    "paneer tikka": (2.0, 5.0),
    "paneer tikka masala": (2.0, 5.0),
    "pani poori": (1.5, 4.5),
    "pani puri": (1.5, 4.5),
    "papad": (0.2, 0.5),
    "papad mangodi": (0.2, 0.5),
    "papaya": (1.5, 4.5),
    "papaya slices": (1.5, 4.5),
    "papdi chaat": (1.5, 4.5),
    "paratha": (0.5, 2.0),
    "parwal sabzi": (2.0, 5.0),
    "pasta": (1.5, 4.5),
    "patiyala murgh": (2.0, 4.5),
    "pav": (0.4, 1.8),
    "pav bhaji": (1.5, 4.5),
    "payasam": (1.5, 4.0),
    "peanut chutney": (0.5, 2.0),
    "pear": (1.5, 4.5),
    "pesarattu": (2.0, 4.5),
    "phirni": (1.5, 4.0),
    "phulka": (0.4, 1.8),
    "pickle": (0.5, 2.0),
    "pineapple": (1.5, 4.5),
    "pineapple halwa": (1.5, 4.0),
    "pineapple slices": (1.5, 4.5),
    "plain dosa": (0.3, 0.8),
    "plain rice": (1.5, 4.5),
    "poha": (1.5, 3.5),
    "pomegranate": (1.5, 4.5),
    "pomegranate seeds": (1.5, 4.5),
    "pongal": (1.5, 4.5),
    "poori": (0.4, 1.8),
    "poriyal": (2.0, 4.0),
    "porridge": (1.5, 3.5),
    "potato chips": (1.5, 4.5),
    "pulao": (1.5, 4.5),
    "pulihora": (1.5, 4.5),
    "pumpkin sabzi": (2.0, 5.0),
    "puri bhaji": (1.5, 4.5),
    "puttu": (1.5, 4.5),
    "rabdi": (1.5, 4.0),
    "rabdi boondi": (1.5, 4.0),
    "raita": (1.5, 3.0),
    "rajasthani kadhi": (1.5, 3.5),
    "rajma": (2.0, 4.0),
    "rajma chawal": (2.0, 5.0),
    "rajma masala": (2.0, 5.0),
    "ras malai": (1.5, 4.0),
    "rasam": (1.0, 2.5),
    "rasgulla": (2.5, 5.5),
    "rava dosa": (0.3, 0.8),
    "rava idli": (2.5, 5.0),
    "rava kesari": (1.5, 4.0),
    "rava upma": (1.5, 4.5),
    "red masoor dal tadka": (1.5, 3.5),
    "rice": (1.5, 4.5),
    "rice kheer": (1.5, 4.5),
    "rooh afza": (1.0, 3.5),
    "roti": (0.4, 1.5),
    "rumali roti": (0.4, 1.8),
    "sabji": (2.0, 5.0),
    "sabudana kheer": (1.5, 4.0),
    "sabudana khichdi": (1.5, 4.5),
    "sabzi": (2.0, 5.0),
    "sada rice": (1.5, 4.5),
    "sakkara pongal": (1.5, 4.0),
    "salad": (1.0, 3.0),
    "sambar": (1.5, 3.0),
    "sambar rice": (1.5, 3.5),
    "sambar vada": (1.5, 3.5),
    "sambhar": (1.5, 3.5),
    "samosa": (2.5, 5.0),
    "sandesh": (1.5, 4.0),
    "scrambled egg": (2.5, 5.0),
    "sem fhali": (2.0, 4.5),
    "semiya payasam": (1.5, 4.0),
    "semiya upma": (1.5, 4.5),
    "set dosa": (0.3, 0.8),
    "sev puri": (1.5, 4.5),
    "sev tamatar": (2.0, 4.5),
    "sev tamatar sabzi": (2.0, 5.0),
    "sevai kheer": (1.5, 4.0),
    "sewai kheer": (1.5, 4.0),
    "shahi paneer": (2.0, 5.0),
    "shakar para": (1.5, 4.0),
    "sheera": (1.5, 4.0),
    "shimla mirch sabzi": (2.0, 5.0),
    "shrikhand": (1.5, 4.0),
    "sindhi dal": (1.5, 3.5),
    "sitaphal": (1.5, 4.5),
    "smoked dal": (1.5, 3.5),
    "soya chaap masala": (2.0, 4.5),
    "soya chunk curry": (2.0, 5.0),
    "soya masala": (2.0, 4.5),
    "spring roll": (1.5, 4.5),
    "sprouts salad": (0.8, 2.5),
    "steam rice": (1.5, 4.0),
    "steamed rice": (1.5, 4.5),
    "subzi miloni": (2.0, 4.5),
    "suji halwa": (1.5, 4.0),
    "sweet bun": (1.5, 4.5),
    "sweet corn soup": (1.0, 3.5),
    "sweet daliya": (1.5, 3.5),
    "sweet lassi": (1.0, 3.5),
    "tamarind chutney": (0.5, 2.0),
    "tamarind rice": (1.5, 4.5),
    "tandoori chicken": (2.0, 5.0),
    "tandoori roti": (0.4, 1.8),
    "tea": (1.0, 3.5),
    "tea/coffee": (1.0, 3.5),
    "thandai": (1.0, 3.5),
    "tinda masala": (2.0, 4.5),
    "tomato chilli chutney": (0.5, 2.0),
    "tomato chutney": (0.5, 2.0),
    "tomato dal fry": (0.8, 2.5),
    "tomato pappu": (0.8, 2.5),
    "tomato rice": (0.8, 2.5),
    "tomato soup": (0.8, 2.5),
    "toor dal tadka": (1.5, 3.5),
    "tori sabzi": (2.0, 5.0),
    "upma": (2.0, 4.5),
    "uttapam": (2.0, 4.5),
    "vada pav": (2.5, 5.0),
    "vangi bath": (1.5, 4.5),
    "veg biryani": (1.5, 4.5),
    "veg cutlet": (2.5, 5.0),
    "veg fried rice": (1.5, 4.5),
    "veg hariyali": (2.0, 4.5),
    "veg kofta curry": (2.0, 5.0),
    "veg kolhapuri": (2.0, 4.5),
    "veg momos": (1.5, 4.5),
    "veg paratha": (0.5, 2.0),
    "veg pongal": (1.5, 4.5),
    "veg puff": (1.5, 4.5),
    "veg pulao": (1.5, 4.5),
    "veg raita": (1.5, 3.0),
    "veg sandwich": (1.5, 4.5),
    "veg upma": (1.5, 4.5),
    "vegetable chettinad": (2.0, 4.5),
    "vegetable pulao": (1.5, 4.5),
    "watermelon": (1.5, 4.5),
    "watermelon slices": (1.5, 4.5),
    "white matar curry": (2.0, 5.0),
    "yellow dal": (1.5, 3.5),
    "yellow moong dal": (1.5, 3.5),
}

# Blending weights for hybrid depth
_DEPTH_ALPHA = 0.70   # weight given to raw depth output
_PRIOR_BETA  = 0.30   # weight given to the geometric prior mid-point

# Assumed plate outer diameter in cm — used by ellipse calibrator.
# For rectangular mess trays (typically 33-37 cm wide) this will over-estimate
# scale. Pass the actual tray width as known_diameter_cm if known.
_PLATE_DIAMETER_CM = 26.0


# ── Depth model ───────────────────────────────────────────────────────────────

def _load_depth_model() -> None:
    """
    Load Depth Anything 3 metric depth model.
    Defaults to 'depth-anything/DA3METRIC-LARGE' for direct physical metric depth (meters).
    Falls back gracefully to 'depth-anything/da3-small' or Depth Anything V2 if needed.
    """
    global _depth_model, _depth_device, _is_metric

    if _depth_model is not None:
        return

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _depth_device = device

    try:
        from depth_anything_3.api import DepthAnything3
        logger.info(f"Loading Depth Anything 3 (DA3METRIC-LARGE) on {device}...")
        _depth_model = DepthAnything3.from_pretrained("depth-anything/DA3METRIC-LARGE").to(device)
        _depth_model.eval()
        _is_metric = True
        logger.info("Depth Anything 3 Metric model loaded successfully.")
    except Exception as err:
        logger.warning(f"Could not load DA3METRIC-LARGE: {err}. Attempting da3-small...")
        try:
            from depth_anything_3.api import DepthAnything3
            _depth_model = DepthAnything3.from_pretrained("depth-anything/da3-small").to(device)
            _depth_model.eval()
            _is_metric = False
            logger.info("Depth Anything 3 Small model loaded successfully.")
        except Exception as err2:
            logger.warning(f"Could not load Depth Anything 3: {err2}. Falling back to Depth Anything V2 pipeline...")
            from transformers import pipeline
            dev_idx = 0 if device == "cuda" else -1
            _depth_model = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=dev_idx)
            _is_metric = False
            logger.info(f"Depth Anything V2 loaded on device factor {dev_idx}")


def estimate_depth(image_bgr: np.ndarray, ctx=None) -> np.ndarray:
    """
    Run Depth Anything depth estimation on a BGR image.

    Returns a depth map (H, W) as float32.
    Higher values = closer to camera (i.e., taller objects).
    When Depth Anything 3 Metric is active, the raw depth represents height-oriented
    metric distance in centimeters (-Z * 100 cm).

    Enhancement #5: Gaussian smoothing is applied before returning to
    reduce per-pixel noise that would otherwise inflate volume estimates.
    """
    debug = ctx is not None and ctx.debug
    t0 = time.perf_counter()

    _load_depth_model()

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    import torch

    if hasattr(_depth_model, "inference"):
        # Depth Anything 3 API
        with torch.inference_mode():
            prediction = _depth_model.inference([rgb])
        pred_depth = prediction.depth[0]  # Metric depth in meters (or relative for da3-small)

        # Resize prediction to match input image dimensions
        depth_m = cv2.resize(pred_depth, (image_bgr.shape[1], image_bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
        depth_m = depth_m.astype(np.float32)

        if _is_metric:
            # Metric depth: pred_depth is distance Z in meters from camera.
            # Invert sign and convert to cm so higher value = closer to camera (cm).
            depth = -(depth_m * 100.0)
        else:
            depth = -(depth_m * 100.0)

        # Clear transient PyTorch VRAM to ensure SAM 3 has full headroom
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    else:
        # Depth Anything V2 fallback pipeline
        from PIL import Image
        pil_img = Image.fromarray(rgb)
        prediction = _depth_model(pil_img)
        pred_depth = prediction["predicted_depth"].squeeze().cpu().numpy()
        depth = cv2.resize(pred_depth, (image_bgr.shape[1], image_bgr.shape[0]))
        depth = depth.astype(np.float32)

    # #5 — Smooth depth map before any downstream use
    depth = cv2.GaussianBlur(depth, (5, 5), 0)

    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_raw_depth.npy", depth)

        d_norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        idx = ctx.next_index("depth")
        ctx.save_image("depth", f"{idx:02d}_depth_normalized.png", d_norm)

        d_colored = cv2.applyColorMap(d_norm, cv2.COLORMAP_INFERNO)
        idx = ctx.next_index("depth")
        fname = f"{idx:02d}_depth_colored.png"
        ctx.save_image("depth", fname, d_colored)

        ctx.log("Depth Estimation", "Depth Anything depth map computed (smoothed)",
                {"device": str(_depth_device),
                 "is_metric": _is_metric,
                 "shape": list(depth.shape),
                 "min": round(float(depth.min()), 3),
                 "max": round(float(depth.max()), 3)},
                elapsed=elapsed, output_file=fname)

    return depth


def apply_food_height_prior(
    height_map: np.ndarray,
    food_label: str,
    alpha: float = _DEPTH_ALPHA,
    beta: float = _PRIOR_BETA,
) -> np.ndarray:
    """
    Enhancement #1 — Hybrid depth fusion with food-specific geometric priors.

    When Depth Anything 3 Metric is active:
      `height_map` is calibrated physical height in centimeters.
      It is bounded and blended with the physiological prior range [min_h, max_h].
    When in relative depth mode:
      `height_map` is normalized to [0, 1] and mapped into plausible cm range.

    Args:
        height_map:  Per-pixel height (cm if metric, or [0, 1] relative).
        food_label:  Canonical food name (must match keys in FOOD_HEIGHT_PRIORS).
        alpha:       Weight for depth-derived height (default 0.70).
        beta:        Weight for prior mid-point (default 0.30).

    Returns:
        Height map in cm, clamped to the food's physiological range (float32).
    """
    key = food_label.strip().lower()
    # Try exact match, then substring
    prior = None
    if key in FOOD_HEIGHT_PRIORS:
        prior = FOOD_HEIGHT_PRIORS[key]
    else:
        for k, v in FOOD_HEIGHT_PRIORS.items():
            if k in key or key in k:
                prior = v
                break

    if _is_metric:
        # ── Physical Metric Depth Fusion ──
        if prior is None:
            return np.clip(height_map, 0.2, 5.0).astype(np.float32)

        min_h, max_h = prior
        # Bounded measured metric height in centimeters
        bounded_measured = np.clip(height_map, min_h * 0.75, max_h * 1.5)
        prior_mid = (min_h + max_h) / 2.0
        fused = alpha * bounded_measured + beta * prior_mid
        clamped = np.clip(fused, min_h * 0.5, max_h * 1.25)
        return clamped.astype(np.float32)
    else:
        # ── Relative Depth Mode ──
        if prior is None:
            # No known prior — scale relative map to a generic 0–5 cm range
            return (height_map * 3.5).astype(np.float32)

        min_h, max_h = prior
        scaled_height = height_map * max_h
        prior_clipped = np.clip(scaled_height, min_h * 0.5, max_h)
        fused = alpha * scaled_height + beta * prior_clipped
        clamped = np.clip(fused, 0.1, max_h)
        return clamped.astype(np.float32)


def calibrate_scale_from_ellipse(
    image_bgr: np.ndarray,
    known_diameter_cm: float = _PLATE_DIAMETER_CM,
    plate_profile: dict | None = None,
) -> float | None:
    """
    Enhancement #4 — Estimate cm-per-pixel scale by fitting an ellipse to:
      1. Circular compartment wells (for multi-compartment trays), OR
      2. The outer plate rim (for circular thalis/plates).

    Avoids applying circular 26cm diameter to rectangular trays.
    Returns cm_per_pixel if a credible ellipse is found, else None.
    """
    gray    = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edges   = cv2.Canny(blurred, 30, 100)

    # Dilate to close small gaps in the plate/well rim
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h, w = image_bgr.shape[:2]
    img_area = h * w
    aspect_image = max(h, w) / max(min(h, w), 1)

    # Check if plate profile is rectangular (e.g. aspect ratio > 1.15)
    is_rectangular_tray = False
    well_diameter_cm = None

    if plate_profile:
        pw = plate_profile.get("outer_width_cm", 30.0)
        ph = plate_profile.get("outer_height_cm", 30.0)
        if abs(pw - ph) > 3.0 or aspect_image > 1.20:
            is_rectangular_tray = True
        # Look for circular wells in profile (width == height)
        for comp in plate_profile.get("compartments", []):
            cw, ch = comp.get("width_cm", 0), comp.get("height_cm", 0)
            if abs(cw - ch) < 1.0 and 8.0 <= cw <= 15.0:
                well_diameter_cm = (cw + ch) / 2.0
                break
    elif aspect_image > 1.25:
        is_rectangular_tray = True
        well_diameter_cm = 12.0  # standard circular well in Indian mess tray

    best_cm_per_px = None
    best_score     = 0.0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if len(cnt) < 5:
            continue

        try:
            (cx, cy), (major, minor), angle = cv2.fitEllipse(cnt)
            if minor < 1e-3:
                continue
            aspect = major / minor
            if aspect > 1.35:  # must be reasonably circular
                continue

            avg_axis_px = (major + minor) / 2.0

            if is_rectangular_tray and well_diameter_cm:
                # Target circular wells (typically 3% to 25% of image area)
                if img_area * 0.03 <= area <= img_area * 0.30:
                    cm_per_px = well_diameter_cm / avg_axis_px
                    score = area / (aspect * aspect)
                    if score > best_score:
                        best_score = score
                        best_cm_per_px = cm_per_px
            elif not is_rectangular_tray:
                # Target outer plate rim for round plates (15% to 92% of frame)
                if img_area * 0.15 <= area <= img_area * 0.92:
                    cm_per_px = known_diameter_cm / avg_axis_px
                    score = area
                    if score > best_score:
                        best_score = score
                        best_cm_per_px = cm_per_px

        except cv2.error:
            continue

    if best_cm_per_px is not None:
        target_name = f"circular well ({well_diameter_cm}cm)" if (is_rectangular_tray and well_diameter_cm) else f"plate rim ({known_diameter_cm}cm)"
        logger.info(f"Ellipse scale calibration: {best_cm_per_px:.5f} cm/px [target={target_name}]")
    return best_cm_per_px


# ── Depth normalisation helpers (unchanged from baseline) ─────────────────────

def normalize_depth_to_plate(
    depth_map: np.ndarray,
    plate_mask: np.ndarray = None,
    ctx=None,
) -> np.ndarray:
    """
    Normalize the depth map relative to the plate surface.
    Enhancement #10 — 2D Planar Surface Normal Fitting:
    Fits a reference plane Z(x, y) = A*x + B*y + C to the plate surface / rim points.
    This eliminates oblique camera perspective tilt across the plate so that
    height = depth_map(x, y) - Z_plane(x, y) is globally zeroed to the true plate floor.

    In our height-oriented depth representation, higher values = closer to camera.
    """
    debug = ctx is not None and ctx.debug
    t0    = time.perf_counter()

    H, W = depth_map.shape[:2]

    # Outer border 8% of the frame representing rim / tray boundary
    rim_mask = np.zeros((H, W), dtype=bool)
    rim_mask[:int(H * 0.08), :] = True
    rim_mask[int(H * 0.92):, :] = True
    rim_mask[:, :int(W * 0.08)] = True
    rim_mask[:, int(W * 0.92):] = True

    # Identify candidate plate baseline pixels
    if plate_mask is not None and plate_mask.any() and float(np.mean(plate_mask)) <= 0.75:
        # Valid plate mask (compartment wells excluded) combined with tray rim
        valid_mask = plate_mask | rim_mask
    else:
        # Fallback: outer rim when compartments are not detected or unmasked
        valid_mask = rim_mask

    # Filter out extreme depth outliers on rim points (e.g. background reflections)
    pts_vals = depth_map[valid_mask]
    if len(pts_vals) > 50:
        p_low, p_high = np.percentile(pts_vals, [5, 90])
        inlier_mask = valid_mask & (depth_map >= p_low) & (depth_map <= p_high)
    else:
        inlier_mask = valid_mask

    y_coords, x_coords = np.where(inlier_mask)
    fitted_plane = False
    baseline_val = 0.0
    height_map_rel = depth_map.copy()

    if len(y_coords) >= 30:
        try:
            # Fit Z(x, y) = A*x + B*y + C using least squares
            A_mat = np.column_stack([x_coords, y_coords, np.ones_like(x_coords, dtype=np.float32)])
            z_obs = depth_map[y_coords, x_coords].astype(np.float32)
            coeffs, _, rank, _ = np.linalg.lstsq(A_mat, z_obs, rcond=None)
            if rank == 3:
                A, B, C = coeffs
                X_grid, Y_grid = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
                plane_surface = A * X_grid + B * Y_grid + C
                height_map_rel = depth_map - plane_surface
                baseline_val = float(np.median(plane_surface[inlier_mask]))
                fitted_plane = True
        except Exception as e:
            logger.warning("Planar surface fitting failed, falling back to scalar median: %s", e)

    if not fitted_plane:
        # Scalar fallback
        if plate_mask is not None and plate_mask.any():
            baseline_val = float(np.median(depth_map[plate_mask]))
        else:
            baseline_val = float(np.percentile(depth_map, 25))
        height_map_rel = depth_map - baseline_val

    elapsed = time.perf_counter() - t0

    if debug:
        idx = ctx.next_index("depth")
        ctx.save_npy("depth", f"{idx:02d}_height_relative.npy", height_map_rel)

        vis = height_map_rel - height_map_rel.min()
        if vis.max() > 0:
            vis = (vis / vis.max() * 255).astype(np.uint8)
        else:
            vis = np.zeros_like(height_map_rel, dtype=np.uint8)
        vis_colored = cv2.applyColorMap(vis, cv2.COLORMAP_JET)
        idx = ctx.next_index("depth")
        fname = f"{idx:02d}_height_relative_colored.png"
        ctx.save_image("depth", fname, vis_colored)

        ctx.log("Depth Normalization", "Surface normal plane subtracted from depth",
                {"baseline": round(float(baseline_val), 3),
                 "fitted_plane": fitted_plane,
                 "is_metric": _is_metric},
                elapsed=elapsed, output_file=fname)

    return height_map_rel


def depth_to_cm(
    height_map_relative: np.ndarray,
    raw_depth: np.ndarray,
    cm_per_pixel: float,
    image_width_px: int,
    ctx=None,
) -> np.ndarray:
    """
    Convert a normalised relative depth map to calibrated height in cm (or [0, 1] relative if uncalibrated).
    """
    debug = ctx is not None and ctx.debug
    t0    = time.perf_counter()

    if _is_metric:
        # Depth Anything 3 Metric: height_map_relative is ALREADY in physical centimeters!
        height_cm = np.clip(height_map_relative, 0.0, 15.0).astype(np.float32)
        elapsed = time.perf_counter() - t0
        if debug:
            idx = ctx.next_index("depth")
            ctx.save_npy("depth", f"{idx:02d}_height_metric_cm.npy", height_cm)
            ctx.log("Depth Metric [cm]", "Metric depth height in cm directly computed",
                    {"cm_per_pixel": round(cm_per_pixel, 5),
                     "min_cm": round(float(height_cm.min()), 2),
                     "max_cm": round(float(height_cm.max()), 2),
                     "mean_cm": round(float(height_cm.mean()), 2)},
                    elapsed=elapsed)
        return height_cm
    else:
        # Clamp negative values (food below the plate baseline is not physical)
        clamped = np.clip(height_map_relative, 0, None)

        # Normalise to [0, 1]
        max_val = clamped.max()
        if max_val > 1e-6:
            normalised = clamped / max_val
        else:
            normalised = clamped

        elapsed = time.perf_counter() - t0

        if debug:
            idx = ctx.next_index("depth")
            ctx.save_npy("depth", f"{idx:02d}_height_normalised.npy", normalised.astype(np.float32))
            ctx.log("Depth Normalised [0-1]", "Relative depth map normalised to [0,1]",
                    {"cm_per_pixel": round(cm_per_pixel, 5),
                     "image_width_px": image_width_px,
                     "max_raw_val": round(float(max_val), 4)},
                    elapsed=elapsed)

        return normalised.astype(np.float32)
