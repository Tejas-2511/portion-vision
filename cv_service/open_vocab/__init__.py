"""
Open-Vocabulary Food Identification & Instance Segmentation Module for PortionVision.
"""

from .pipeline import OpenVocabFoodSegmenter

# SAM3 segmenter — exported when available (requires sam3 conda env + CUDA)
try:
    from .sam3_segmenter import Sam3FoodSegmenter, is_sam3_available, get_sam3_segmenter
    __all__ = ["OpenVocabFoodSegmenter", "Sam3FoodSegmenter", "is_sam3_available", "get_sam3_segmenter"]
except ImportError:
    __all__ = ["OpenVocabFoodSegmenter"]

