"""
Plate configuration — known real-world dimensions for mess plate types.

Since we're working with non-circular sectioned mess plates (thali trays),
we define known physical sizes so we can compute a pixel-to-cm scale factor
from detected compartments.
"""

# ── Standard Indian mess thali plate ─────────────────────────────────────
# Rectangular stainless-steel plate with molded compartments.


PLATE_PROFILES = {
    # ── This is the actual tray used (matches the real output images) ──────────
    "mess_tray_5comp": {
        "description": "5-compartment stainless steel mess tray — 1 large left, 3 circular right, 1 small bottom-left",
        "outer_width_cm": 30.0,
        "outer_height_cm": 42.0,
        "compartments": [
            # Large left compartment — roti/rice/sabzi share this open space
            {"label": "large_left",   "width_cm": 15.0, "height_cm": 25.0, "depth_cm": 2.5, "max_volume_ml": 600, "_cx_norm": 0.27, "_cy_norm": 0.40},
            # Three circular wells — right column (top to bottom)
            {"label": "round_top",    "width_cm": 12.0, "height_cm": 12.0, "depth_cm": 3.0, "max_volume_ml": 250, "_cx_norm": 0.75, "_cy_norm": 0.17},
            {"label": "round_mid",    "width_cm": 12.0, "height_cm": 12.0, "depth_cm": 3.0, "max_volume_ml": 250, "_cx_norm": 0.75, "_cy_norm": 0.48},
            {"label": "round_bot",    "width_cm": 12.0, "height_cm": 12.0, "depth_cm": 3.0, "max_volume_ml": 250, "_cx_norm": 0.75, "_cy_norm": 0.78},
            # Small rectangular well — bottom left (chutney / salad / spoon)
            {"label": "small_rect",   "width_cm": 10.0, "height_cm":  7.0, "depth_cm": 1.5, "max_volume_ml":  80, "_cx_norm": 0.22, "_cy_norm": 0.82},
        ],
    },
    "standard_mess_thali": {
        "description": "Typical 6-compartment stainless steel mess plate",
        "outer_width_cm": 37.0,
        "outer_height_cm": 27.0,
        "compartments": [
            # Small round/square wells — top row (dal, chutney, sweet)
            # _cx_norm/_cy_norm = expected normalised centroid position in image
            {"label": "small_1", "width_cm": 9.0,  "height_cm": 9.0,  "depth_cm": 2.5, "max_volume_ml": 150, "_cx_norm": 0.13, "_cy_norm": 0.25},
            {"label": "small_2", "width_cm": 9.0,  "height_cm": 9.0,  "depth_cm": 2.5, "max_volume_ml": 150, "_cx_norm": 0.38, "_cy_norm": 0.25},
            {"label": "small_3", "width_cm": 9.0,  "height_cm": 9.0,  "depth_cm": 2.5, "max_volume_ml": 150, "_cx_norm": 0.63, "_cy_norm": 0.25},
            # Large compartments — bottom row (rice, roti, sabzi)
            {"label": "large_1", "width_cm": 16.0, "height_cm": 12.0, "depth_cm": 2.0, "max_volume_ml": 350, "_cx_norm": 0.27, "_cy_norm": 0.72},
            {"label": "large_2", "width_cm": 14.0, "height_cm": 12.0, "depth_cm": 2.0, "max_volume_ml": 300, "_cx_norm": 0.72, "_cy_norm": 0.72},
        ],
    },
    "4_compartment_plate": {
        "description": "4-compartment rectangular plate",
        "outer_width_cm": 33.0,
        "outer_height_cm": 25.0,
        "compartments": [
            {"label": "top_left",     "width_cm": 14.0, "height_cm": 10.0, "depth_cm": 2.5, "max_volume_ml": 250, "_cx_norm": 0.25, "_cy_norm": 0.25},
            {"label": "top_right",    "width_cm": 14.0, "height_cm": 10.0, "depth_cm": 2.5, "max_volume_ml": 250, "_cx_norm": 0.75, "_cy_norm": 0.25},
            {"label": "bottom_left",  "width_cm": 14.0, "height_cm": 11.0, "depth_cm": 2.0, "max_volume_ml": 250, "_cx_norm": 0.25, "_cy_norm": 0.75},
            {"label": "bottom_right", "width_cm": 14.0, "height_cm": 11.0, "depth_cm": 2.0, "max_volume_ml": 250, "_cx_norm": 0.75, "_cy_norm": 0.75},
        ],
    },
}

# Default plate profile to use when auto-detection picks a best match
DEFAULT_PLATE_PROFILE = "mess_tray_5comp"


def get_plate_profile(name: str = None) -> dict:
    """Return a plate profile dict by name, falling back to default."""
    return PLATE_PROFILES.get(name or DEFAULT_PLATE_PROFILE, PLATE_PROFILES[DEFAULT_PLATE_PROFILE])
