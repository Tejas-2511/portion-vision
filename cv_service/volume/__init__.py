"""
PortionVision Volume Integration Package.
"""

from volume.volume_integrator import (
    integrate_food_volume,
    classify_archetype,
    compute_physical_pixel_areas,
    get_planar_sheet_thickness_cm,
    get_salad_slice_thickness_cm,
    ARCHETYPE_PLANAR,
    ARCHETYPE_SALAD,
    ARCHETYPE_LIQUID,
    ARCHETYPE_MOUND,
    ARCHETYPE_CHUNK,
    ARCHETYPE_CONDIMENT,
)

__all__ = [
    "integrate_food_volume",
    "classify_archetype",
    "compute_physical_pixel_areas",
    "get_planar_sheet_thickness_cm",
    "get_salad_slice_thickness_cm",
    "ARCHETYPE_PLANAR",
    "ARCHETYPE_SALAD",
    "ARCHETYPE_LIQUID",
    "ARCHETYPE_MOUND",
    "ARCHETYPE_CHUNK",
    "ARCHETYPE_CONDIMENT",
]
