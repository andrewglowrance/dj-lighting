"""
motion_variants.py
Per-motion-family variants (param modifiers) and beat behavior types.
Consumed by beat_choreographer.py to produce phrase-level diversity.
"""
from __future__ import annotations

# Each variant is a dict of modifiers applied on top of the vocabulary base params.
# Keys: variant_id (str), color (str|None), spread_scale (float), density_scale (float), direction (str)
MOTION_VARIANTS: dict[str, list[dict]] = {
    "crosshatch": [
        {"variant_id": "dense_center",   "color": "laser_green",  "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "compressed_red", "color": "laser_red",    "spread_scale": 0.65, "density_scale": 0.80, "direction": "center"},
        {"variant_id": "wide_white",     "color": "laser_white",  "spread_scale": 1.25, "density_scale": 1.15, "direction": "alternating"},
        {"variant_id": "mid_cyan",       "color": "laser_cyan",   "spread_scale": 0.85, "density_scale": 0.90, "direction": "center"},
    ],
    "fan_open": [
        {"variant_id": "expand_left",  "color": "laser_green", "spread_scale": 1.30, "density_scale": 1.00, "direction": "left"},
        {"variant_id": "expand_right", "color": "laser_red",   "spread_scale": 1.30, "density_scale": 1.00, "direction": "right"},
        {"variant_id": "wide_center",  "color": "laser_cyan",  "spread_scale": 1.50, "density_scale": 1.10, "direction": "center"},
        {"variant_id": "narrow_snap",  "color": "laser_white", "spread_scale": 0.50, "density_scale": 0.70, "direction": "center"},
    ],
    "fan_close": [
        {"variant_id": "blue_narrow",  "color": "laser_blue", "spread_scale": 0.60, "density_scale": 0.75, "direction": "center"},
        {"variant_id": "cyan_fade",    "color": "laser_cyan", "spread_scale": 0.45, "density_scale": 0.65, "direction": "center"},
    ],
    "center_converge": [
        {"variant_id": "tight_blue",    "color": "laser_blue",  "spread_scale": 0.55, "density_scale": 0.80, "direction": "center"},
        {"variant_id": "loose_cyan",    "color": "laser_cyan",  "spread_scale": 0.90, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "pulsing_white", "color": "laser_white", "spread_scale": 0.70, "density_scale": 0.90, "direction": "center"},
        {"variant_id": "release_green", "color": "laser_green", "spread_scale": 1.20, "density_scale": 1.10, "direction": "expand"},
    ],
    "alternating_side_sweep": [
        {"variant_id": "l_red",   "color": "laser_red",   "spread_scale": 1.00, "density_scale": 1.00, "direction": "left"},
        {"variant_id": "r_green", "color": "laser_green", "spread_scale": 1.00, "density_scale": 1.00, "direction": "right"},
        {"variant_id": "l_cyan",  "color": "laser_cyan",  "spread_scale": 0.85, "density_scale": 0.90, "direction": "left"},
        {"variant_id": "r_white", "color": "laser_white", "spread_scale": 0.85, "density_scale": 0.90, "direction": "right"},
    ],
    "audience_rake": [
        {"variant_id": "low_horizon",   "color": "laser_red",   "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "wide_sweep",    "color": "laser_green", "spread_scale": 1.30, "density_scale": 1.10, "direction": "alternating"},
        {"variant_id": "narrow_center", "color": "laser_cyan",  "spread_scale": 0.65, "density_scale": 0.75, "direction": "center"},
        {"variant_id": "side_pull",     "color": "laser_white", "spread_scale": 0.80, "density_scale": 0.85, "direction": "left"},
    ],
    "horizontal_sheet_plane": [
        {"variant_id": "blue_wide",  "color": "laser_blue",  "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "cyan_left",  "color": "laser_cyan",  "spread_scale": 0.85, "density_scale": 0.90, "direction": "left"},
        {"variant_id": "white_right","color": "laser_white", "spread_scale": 0.85, "density_scale": 0.90, "direction": "right"},
        {"variant_id": "green_full", "color": "laser_green", "spread_scale": 1.15, "density_scale": 1.05, "direction": "alternating"},
    ],
    "ceiling_rake": [
        {"variant_id": "white_ceiling", "color": "laser_white", "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "cyan_alt",      "color": "laser_cyan",  "spread_scale": 0.80, "density_scale": 0.85, "direction": "alternating"},
    ],
    "burst_outward": [
        {"variant_id": "white_explosion","color": "laser_white", "spread_scale": 1.00, "density_scale": 1.00, "direction": "expand"},
        {"variant_id": "color_burst",    "color": "laser_red",   "spread_scale": 1.20, "density_scale": 1.10, "direction": "expand"},
    ],
    "burst_inward": [
        {"variant_id": "red_collapse",   "color": "laser_red",   "spread_scale": 0.60, "density_scale": 0.85, "direction": "center"},
        {"variant_id": "white_compress", "color": "laser_white", "spread_scale": 0.70, "density_scale": 0.90, "direction": "center"},
    ],
    "hold_then_snap": [
        {"variant_id": "blue_hold",  "color": "laser_blue",  "spread_scale": 0.50, "density_scale": 0.70, "direction": "center"},
        {"variant_id": "white_snap", "color": "laser_white", "spread_scale": 1.20, "density_scale": 1.00, "direction": "expand"},
    ],
    "upper_lower_layer_split": [
        {"variant_id": "upper_dominant",  "color": "laser_blue",  "spread_scale": 1.10, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "lower_dominant",  "color": "laser_cyan",  "spread_scale": 0.90, "density_scale": 0.85, "direction": "center"},
        {"variant_id": "balanced_split",  "color": "laser_white", "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "crossing_layers", "color": "laser_green", "spread_scale": 1.15, "density_scale": 1.10, "direction": "alternating"},
    ],
    "tunnel": [
        {"variant_id": "white_ring",  "color": "laser_white", "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "cyan_narrow", "color": "laser_cyan",  "spread_scale": 0.75, "density_scale": 0.85, "direction": "center"},
        {"variant_id": "blue_wide",   "color": "laser_blue",  "spread_scale": 1.25, "density_scale": 1.10, "direction": "center"},
        {"variant_id": "color_chase", "color": None,          "spread_scale": 1.00, "density_scale": 1.00, "direction": "alternating"},
    ],
    "sheet_plane": [
        {"variant_id": "green_low",  "color": "laser_green", "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "blue_wide",  "color": "laser_blue",  "spread_scale": 1.30, "density_scale": 1.10, "direction": "alternating"},
    ],
    "staggered_chase": [
        {"variant_id": "left_to_right", "color": "laser_red",   "spread_scale": 1.00, "density_scale": 1.00, "direction": "left"},
        {"variant_id": "right_to_left", "color": "laser_green", "spread_scale": 1.00, "density_scale": 1.00, "direction": "right"},
        {"variant_id": "center_out",    "color": "laser_cyan",  "spread_scale": 1.20, "density_scale": 1.10, "direction": "expand"},
        {"variant_id": "wide_scatter",  "color": "laser_white", "spread_scale": 1.40, "density_scale": 1.20, "direction": "alternating"},
    ],
    "laser_burst_cluster": [
        {"variant_id": "max_density",   "color": None,          "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "focused_burst", "color": "laser_white", "spread_scale": 0.75, "density_scale": 0.85, "direction": "center"},
        {"variant_id": "wide_spray",    "color": None,          "spread_scale": 1.30, "density_scale": 1.15, "direction": "alternating"},
        {"variant_id": "red_cluster",   "color": "laser_red",   "spread_scale": 0.90, "density_scale": 0.95, "direction": "center"},
    ],
    "beam_stack": [
        {"variant_id": "upper_center", "color": None, "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "wide_spread",  "color": None, "spread_scale": 1.30, "density_scale": 1.15, "direction": "alternating"},
        {"variant_id": "narrow_focus", "color": None, "spread_scale": 0.65, "density_scale": 0.80, "direction": "center"},
        {"variant_id": "asymmetric",   "color": None, "spread_scale": 0.90, "density_scale": 0.90, "direction": "left"},
    ],
    "reveal_whiteout": [
        {"variant_id": "full_flood",    "color": None, "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "staged_reveal", "color": None, "spread_scale": 1.30, "density_scale": 1.00, "direction": "expand"},
    ],
    "mirror_sweep": [
        {"variant_id": "symmetric_in",   "color": "laser_white", "spread_scale": 0.70, "density_scale": 0.85, "direction": "center"},
        {"variant_id": "symmetric_out",  "color": "laser_blue",  "spread_scale": 1.30, "density_scale": 1.10, "direction": "expand"},
        {"variant_id": "left_dominant",  "color": "laser_cyan",  "spread_scale": 1.00, "density_scale": 1.00, "direction": "left"},
        {"variant_id": "right_dominant", "color": "laser_red",   "spread_scale": 1.00, "density_scale": 1.00, "direction": "right"},
    ],
    "symmetrical_mirror": [
        {"variant_id": "balanced_wide",  "color": "laser_white", "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "compressed_sym", "color": "laser_blue",  "spread_scale": 0.70, "density_scale": 0.80, "direction": "center"},
        {"variant_id": "expanded_sym",   "color": "laser_cyan",  "spread_scale": 1.40, "density_scale": 1.15, "direction": "expand"},
        {"variant_id": "green_sym",      "color": "laser_green", "spread_scale": 1.00, "density_scale": 1.00, "direction": "alternating"},
    ],
    "radial_wash_expand": [
        {"variant_id": "white_expand", "color": "laser_white", "spread_scale": 1.00, "density_scale": 1.00, "direction": "expand"},
        {"variant_id": "red_radial",   "color": "laser_red",   "spread_scale": 1.20, "density_scale": 1.10, "direction": "expand"},
        {"variant_id": "cyan_mid",     "color": "laser_cyan",  "spread_scale": 0.85, "density_scale": 0.90, "direction": "center"},
    ],
    "slow_drift": [
        {"variant_id": "blue_hold",   "color": "laser_blue", "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "cyan_gentle", "color": "laser_cyan", "spread_scale": 0.80, "density_scale": 0.80, "direction": "center"},
    ],
    "static_hold":           [{"variant_id": "dark_hold",  "color": None, "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"}],
    "fade_to_black":         [{"variant_id": "fade_out",   "color": None, "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"}],
    "minimal_source_reveal": [
        {"variant_id": "blue_single",  "color": "laser_blue",  "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
        {"variant_id": "white_sparse", "color": "laser_white", "spread_scale": 0.80, "density_scale": 0.80, "direction": "center"},
    ],
    "aperture_hold": [
        {"variant_id": "narrow_x",    "color": "laser_blue",  "spread_scale": 0.40, "density_scale": 0.60, "direction": "center"},
        {"variant_id": "mid_cross",   "color": "laser_cyan",  "spread_scale": 0.65, "density_scale": 0.70, "direction": "center"},
    ],
}

# Default fallback variants for any family not listed above
_DEFAULT_VARIANTS: list[dict] = [
    {"variant_id": "default", "color": None, "spread_scale": 1.00, "density_scale": 1.00, "direction": "center"},
]

def get_variants(motion_family: str) -> list[dict]:
    """Return the variant list for a motion family, falling back to defaults."""
    return MOTION_VARIANTS.get(motion_family, _DEFAULT_VARIANTS)


# Beat behaviors per motion family (deterministic selection order)
BEAT_BEHAVIORS_BY_FAMILY: dict[str, list[str]] = {
    "crosshatch":              ["micro_snap_on_beat", "downbeat_hit", "density_pulse", "2bar_angle_shift"],
    "fan_open":                ["fan_width_modulation", "downbeat_hit", "alternating_L_R", "progressive_expand"],
    "fan_close":               ["hold_then_release", "brightness_pulse"],
    "center_converge":         ["center_snap", "hold_then_release", "brightness_pulse", "micro_snap_on_beat"],
    "audience_rake":           ["rake_pulse", "2bar_angle_shift", "downbeat_hit", "density_pulse"],
    "horizontal_sheet_plane":  ["rake_pulse", "density_pulse", "hold_then_release", "alternating_L_R"],
    "laser_burst_cluster":     ["micro_snap_on_beat", "density_pulse", "downbeat_hit"],
    "staggered_chase":         ["alternating_L_R", "density_pulse", "downbeat_hit", "2bar_angle_shift"],
    "tunnel":                  ["center_snap", "brightness_pulse", "micro_snap_on_beat"],
    "beam_stack":              ["brightness_pulse", "downbeat_hit", "2bar_angle_shift", "fan_width_modulation"],
    "reveal_whiteout":         ["brightness_pulse", "downbeat_hit"],
    "mirror_sweep":            ["alternating_L_R", "brightness_pulse", "downbeat_hit", "2bar_angle_shift"],
    "symmetrical_mirror":      ["brightness_pulse", "downbeat_hit", "2bar_angle_shift"],
    "alternating_side_sweep":  ["alternating_L_R", "density_pulse", "downbeat_hit", "2bar_angle_shift"],
    "upper_lower_layer_split": ["brightness_pulse", "2bar_angle_shift", "downbeat_hit"],
    "burst_outward":           ["downbeat_hit", "density_pulse"],
    "burst_inward":            ["center_snap", "downbeat_hit"],
    "radial_wash_expand":      ["progressive_expand", "downbeat_hit", "density_pulse"],
    "ceiling_rake":            ["rake_pulse", "2bar_angle_shift", "alternating_L_R"],
    "sheet_plane":             ["rake_pulse", "hold_then_release", "density_pulse"],
    "hold_then_snap":          ["hold_then_release", "center_snap", "brightness_pulse"],
    "slow_drift":              ["hold_then_release", "very_subtle_pulse"],
    "static_hold":             ["hold_then_release"],
    "minimal_source_reveal":   ["very_subtle_pulse", "hold_then_release"],
    "fade_to_black":           ["hold_then_release"],
    "aperture_hold":           ["hold_then_release", "very_subtle_pulse", "center_snap"],
}

DEFAULT_BEAT_BEHAVIORS: list[str] = ["downbeat_hit", "micro_snap_on_beat", "brightness_pulse"]

def get_beat_behaviors(motion_family: str) -> list[str]:
    """Return beat behavior list for a family, falling back to defaults."""
    return BEAT_BEHAVIORS_BY_FAMILY.get(motion_family, DEFAULT_BEAT_BEHAVIORS)
