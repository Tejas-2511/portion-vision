import os
import sys
import glob
import json
import datetime
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from open_vocab.pipeline import OpenVocabFoodSegmenter

base_dir = os.path.dirname(os.path.abspath(__file__))
outputs_dir = os.path.join(base_dir, "outputs")
os.makedirs(outputs_dir, exist_ok=True)

# Find image
img_path = os.path.join(outputs_dir, "20260406_200944_def9be09", "input", "original.png")
if not os.path.exists(img_path):
    samples = glob.glob(os.path.join(outputs_dir, "**", "input", "original.png"), recursive=True)
    img_path = samples[0] if samples else None

if not img_path or not os.path.exists(img_path):
    print("No test plate image found in cv_service/outputs/.")
    sys.exit(1)

img = cv2.imread(img_path)
print(f"Image loaded from {img_path}:", img.shape if img is not None else None)

pipeline = OpenVocabFoodSegmenter()
res = pipeline.process_plate(img, menu_items=["steamed rice", "dal palak", "chapati"])

print(f"\nResults: {res['total_items']} items found ({res['recognized_count']} recognized, {res['unlisted_count']} unlisted, {res['uncertain_count']} uncertain)")
serializable_items = []
for idx, item in enumerate(res["food_items"], 1):
    print(f" {idx}. {item['food_name']} | status={item['identification_status']} | menu_match={item['menu_match']} | conf={item['confidence']:.4f} | bbox={item['bounding_box']} | area={item['area_pixels']}")
    it = dict(item)
    if isinstance(it.get("mask"), np.ndarray):
        it["mask_shape"] = list(it["mask"].shape)
    it["mask"] = None
    serializable_items.append(it)

res_copy = dict(res)
res_copy["food_items"] = serializable_items
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_json = os.path.join(outputs_dir, f"test_open_vocab_{timestamp}.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(res_copy, f, indent=2)

print(f"\nSaved structured output to: {out_json}")
