"""
Plate configuration — known real-world dimensions for mess plate types.

Since we're working with non-circular sectioned mess plates (thali trays),
we define known physical sizes so we can compute a pixel-to-cm scale factor
from detected compartments.
"""

# ── Standard Indian mess thali plate ─────────────────────────────────────
# Rectangular stainless-steel plate with molded compartments.
# Overall outer dimensions and individual compartment sizes (in cm).
#
# Layout reference (typical 6-compartment mess plate):
#  ┌──────────────────────────────────┐
#  │   ┌─────┐  ┌─────┐  ┌─────┐    │
#  │   │ sm1 │  │ sm2 │  │ sm3 │    │
#  │   └─────┘  └─────┘  └─────┘    │
#  │   ┌────────────┐  ┌─────────┐  │
#  │   │   large1   │  │  large2 │  │
#  │   └────────────┘  └─────────┘  │
#  └──────────────────────────────────┘

PLATE_PROFILES = {
    "standard_mess_thali": {
        "description": "Typical 6-compartment stainless steel mess plate",
        "outer_width_cm": 37.0,
        "outer_height_cm": 27.0,
        "compartments": [
            # Small round/square wells (top row — for dal, chutney, sweet)
            {"label": "small_1", "width_cm": 9.0,  "height_cm": 9.0,  "depth_cm": 2.5, "max_volume_ml": 150},
            {"label": "small_2", "width_cm": 9.0,  "height_cm": 9.0,  "depth_cm": 2.5, "max_volume_ml": 150},
            {"label": "small_3", "width_cm": 9.0,  "height_cm": 9.0,  "depth_cm": 2.5, "max_volume_ml": 150},
            # Large compartments (bottom row — for rice, roti, sabzi)
            {"label": "large_1", "width_cm": 16.0, "height_cm": 12.0, "depth_cm": 2.0, "max_volume_ml": 350},
            {"label": "large_2", "width_cm": 14.0, "height_cm": 12.0, "depth_cm": 2.0, "max_volume_ml": 300},
        ],
    },
    "4_compartment_plate": {
        "description": "4-compartment rectangular plate",
        "outer_width_cm": 33.0,
        "outer_height_cm": 25.0,
        "compartments": [
            {"label": "top_left",     "width_cm": 14.0, "height_cm": 10.0, "depth_cm": 2.5, "max_volume_ml": 250},
            {"label": "top_right",    "width_cm": 14.0, "height_cm": 10.0, "depth_cm": 2.5, "max_volume_ml": 250},
            {"label": "bottom_left",  "width_cm": 14.0, "height_cm": 11.0, "depth_cm": 2.0, "max_volume_ml": 250},
            {"label": "bottom_right", "width_cm": 14.0, "height_cm": 11.0, "depth_cm": 2.0, "max_volume_ml": 250},
        ],
    },
}

# Default plate profile to use when auto-detection picks a best match
DEFAULT_PLATE_PROFILE = "standard_mess_thali"


def get_plate_profile(name: str = None) -> dict:
    """Return a plate profile dict by name, falling back to default."""
    return PLATE_PROFILES.get(name or DEFAULT_PLATE_PROFILE, PLATE_PROFILES[DEFAULT_PLATE_PROFILE])
