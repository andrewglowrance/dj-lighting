"""
lighting/rules.py

Declarative rules specification for the deterministic cue engine.

This file defines:
  - Color palettes (named RGB tuples, 0-255)
  - Abstract fixture group names
  - Per-section rule tables consumed by cue_engine.py

Rules are pure data — no logic lives here. The engine iterates the rule
table and calls an emitter function per trigger type.

--- Parameter contracts per cue_type ---

wash:
    color: str          – palette key
    intensity: float    – [0, 1]
    fade_in: float      – seconds (optional, default 0)

pulse:
    color: str
    intensity: float    – peak intensity [0, 1]

strobe_hit:
    intensity: float    – [0, 1]

color_shift:
    color: str
    transition: str     – "snap" | "fade"

movement_enable:
    speed: float        – [0, 1], 0=stop, 1=full speed
    pattern: str        – "sweep" | "fast_pan" | "slow_drift"

fade_out:
    target_intensity: float  – [0, 1] target level (0 = full black)
    fade_time: float         – seconds (optional)
    color: str               – (optional) color during fade

laser_static:
    color: str               – laser palette key (laser_green, laser_red, etc.)
    pattern: str             – "fan" | "single" | "x_cross"
    fan_count: int           – number of beams in fan (2-8, default 5)
    spread_deg: float        – total fan spread in degrees (default 60)
    intensity: float         – [0, 1]

laser_scan:
    color: str
    speed: float             – scan speed [0, 1], 0=stopped, 1=full speed
    fan_count: int           – beams in the scan group (1-3, default 1)
    spread_deg: float        – spread of scan group (default 20)
    intensity: float

laser_chase:
    colors: list[str]        – palette keys cycling per step
    beam_count: int          – total beams (default 4)
    step_beats: float        – how many beats per color step (default 0.5)
    intensity: float

laser_off:
    (no parameters)
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------

COLORS: dict[str, tuple[int, int, int]] = {
    # Laser palette — pure saturated wavelengths, no mixing
    "laser_green":     (0,   255, 0),
    "laser_red":       (255, 0,   0),
    "laser_blue":      (30,  80,  255),
    "laser_white":     (255, 255, 255),
    "laser_cyan":      (0,   255, 220),
    "laser_yellow":    (255, 220, 0),
    # Wash palette
    "cool_blue":       (0,   80,  255),
    "warm_amber":      (255, 120, 0),
    "deep_purple":     (80,  0,   200),
    "drop_red":        (255, 0,   40),
    "drop_yellow":     (255, 200, 0),
    "breakdown_teal":  (0,   160, 140),
    "pure_white":      (255, 255, 255),
    "outro_blue":      (0,   40,  100),
    "build_orange":    (255, 80,  0),

    # Note-responsive wash palette — chromesthetic mapping (Newton color wheel)
    # Each key maps a chromatic pitch class to a distinct hue for wash lights.
    # Cue engine substitutes these when use_note_color: True is set on a rule.
    "note_C":  (255,  30,  30),   # C  → Red
    "note_Cs": (255,  90,  10),   # C# → Red-Orange
    "note_D":  (255, 145,   0),   # D  → Orange
    "note_Ds": (255, 190,   0),   # D# → Amber-Yellow
    "note_E":  (230, 220,   0),   # E  → Yellow
    "note_F":  (100, 210,   0),   # F  → Yellow-Green
    "note_Fs": (  0, 200,  30),   # F# → Green
    "note_G":  (  0, 195, 120),   # G  → Cyan-Green
    "note_Gs": (  0, 190, 210),   # G# → Cyan
    "note_A":  (  0,  90, 255),   # A  → Blue
    "note_As": ( 80,   0, 255),   # A# → Blue-Violet
    "note_B":  (160,   0, 200),   # B  → Violet
}

# Color sequences cycled during drop and build sections
DROP_COLOR_CYCLE: list[str] = ["drop_red", "drop_yellow", "pure_white", "deep_purple"]
BUILD_COLOR_CYCLE: list[str] = ["warm_amber", "build_orange", "deep_purple"]


# ---------------------------------------------------------------------------
# Abstract fixture groups
# ---------------------------------------------------------------------------
# Rig-template mapping (Phase 2) resolves these strings to physical fixtures
# and DMX channels. The cue engine never mentions specific fixtures.

GROUP_WASH_ALL    = "wash_all"
GROUP_SPOTS       = "spots"
GROUP_MOVING_HEADS= "moving_heads"
GROUP_STROBE      = "strobe"
GROUP_BACK_WASH   = "back_wash"
GROUP_LASERS      = "lasers"


# ---------------------------------------------------------------------------
# Per-section rules
# ---------------------------------------------------------------------------
# Each rule is a dict with these mandatory keys:
#
#   trigger        str   When to fire within the section:
#                          "section_start"  – once, at section.start
#                          "beat"           – every beat
#                          "bar_beat_1"     – beat 0 of every bar
#                          "bar_4_beat_1"   – beat 0 of every 4th bar
#                          "bar_2_beat_1"   – beat 0 of every 2nd bar
#                          "build_last4"    – beat 0/2 in last 4 bars of build
#                          "pre_drop"       – last beat of a build section
#                          "beat_2_4"       – beats 1 and 3 within each bar
#
#   cue_type       str   One of the CueType literals from schemas/cues.py
#   target_groups  list  Fixture groups this rule fires on
#   params         dict  Passed through to Cue.parameters; see contracts above
#
# Optional keys:
#   duration_beats float  Override duration = beat_duration * N
#   duration_sec   float  Override duration to a fixed number of seconds
#   fill_section   bool   If True, duration spans the full section (eliminates dark gaps)

SECTION_RULES: dict[str, list[dict]] = {

    # -----------------------------------------------------------------------
    "intro": [
        # Sustained ambient wash that covers the full intro — no dark gaps.
        # back_wash is audience-facing: keeps the crowd lit from the start.
        {
            "trigger":       "section_start",
            "cue_type":      "wash",
            "target_groups": [GROUP_WASH_ALL, GROUP_BACK_WASH],
            "fill_section":  True,
            "params": {"color": "cool_blue", "intensity": 0.20, "fade_in": 2.0},
        },
        # Gentle slow movement — adds depth without distracting
        # Base speed is the 120-BPM / full-energy target; engine scales it down
        # for quieter/slower passages via _apply_energy_scale.
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "fill_section":   True,
            "params": {"speed": 0.18, "pattern": "slow_drift"},
        },
        # Note-responsive pulse: color and intensity track the dominant pitch
        {
            "trigger":        "bar_beat_1",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "use_note_color": True,   # cue engine substitutes note color + energy scale
            "use_tone_duration": True, # duration stretches to match the note length
            "duration_beats": 0.50,   # fallback if beat_notes unavailable
            "params": {"color": "cool_blue", "intensity": 0.38},
        },
        # Lasers OFF for full intro — reserve impact for the drop
        {
            "trigger":       "section_start",
            "cue_type":      "laser_off",
            "target_groups": [GROUP_LASERS],
            "fill_section":  True,
            "params": {},
        },
    ],

    # -----------------------------------------------------------------------
    "build": [
        # Sustained low-level wash fills the section between pulses.
        # Including back_wash keeps audience illuminated as tension rises.
        {
            "trigger":        "section_start",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL, GROUP_BACK_WASH],
            "fill_section":   True,
            "params": {"color": "warm_amber", "intensity": 0.22, "fade_in": 0.5},
        },
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "fill_section":   True,
            "params": {"speed": 0.60, "pattern": "sweep"},
        },
        # Note-responsive beat pulse: hue tracks dominant pitch, intensity ramps +
        # scales with the beat's RMS energy; duration stretches to note length
        {
            "trigger":        "beat",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "use_note_color": True,
            "use_tone_duration": True,
            "duration_beats": 0.50,
            "params": {
                "color":           "warm_amber",   # fallback; overridden per beat
                "intensity_start": 0.38,
                "intensity_end":   0.85,
                "_ramp":           True,
            },
        },
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.25,
            "params": {"color": "_build_cycle", "transition": "snap"},
        },
        # Strobe on beats 2 & 4 throughout the build — energy scaling keeps it
        # subtle at the start and aggressive in the last bars before the drop.
        {
            "trigger":        "beat_2_4",
            "cue_type":       "strobe_hit",
            "target_groups":  [GROUP_STROBE],
            "duration_beats": 0.10,
            "params": {"intensity": 0.45},
        },
        {
            "trigger":        "build_last4",
            "cue_type":       "strobe_hit",
            "target_groups":  [GROUP_STROBE],
            "duration_beats": 0.125,
            "params": {"intensity": 1.0},
        },
        {
            "trigger":        "pre_drop",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS],
            "duration_beats": 0.25,
            "params": {"color": "pure_white", "transition": "snap"},
        },
        # Laser: diagonal sweep building tension — all fixtures track together
        {
            "trigger":        "section_start",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "fill_section":   True,
            "params": {
                "color":          "laser_green",
                "speed":          0.45,
                "fan_count":      2,
                "spread_deg":     22,
                "intensity":      0.65,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "beat",
                "sweep_axis":     "diagonal",
                "sweep_direction":"left_to_right",
                "tilt_speed":     0.25,
                "tilt_range_deg": 20, "active_zones": ["overhead"],
            },
        },
        # Last 4 bars: widen to horizontal fan sweep + vertical tilt
        {
            "trigger":        "build_last4",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 1.0,
            "params": {
                "color":          "laser_cyan",
                "speed":          0.90,
                "fan_count":      4,
                "spread_deg":     45,
                "intensity":      0.92,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "beat",
                "sweep_axis":     "horizontal",
                "sweep_direction":"alternating",
                "tilt_speed":     0.50,
                "tilt_range_deg": 30, "active_zones": ["overhead"],
            },
        },
        # Pre-drop: full vertical sweep burst — all units tilt down-to-up together
        {
            "trigger":        "pre_drop",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 0.25,
            "params": {
                "color":          "laser_white",
                "speed":          1.0,
                "fan_count":      5,
                "spread_deg":     60,
                "intensity":      1.0,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "downbeat",
                "sweep_axis":     "vertical",
                "sweep_direction":"center_out",
                "tilt_speed":     1.0,
                "tilt_range_deg": 40, "active_zones": ["overhead", "side_tower"],
            },
        },
    ],

    # -----------------------------------------------------------------------
    "drop": [
        # Full-section sustained wash ensures the room stays lit between pulses
        {
            "trigger":        "section_start",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL],
            "fill_section":   True,
            "params": {"color": "drop_red", "intensity": 0.25, "fade_in": 0.0},
        },
        {
            "trigger":        "section_start",
            "cue_type":       "strobe_hit",
            "target_groups":  [GROUP_STROBE, GROUP_WASH_ALL],
            "duration_beats": 0.50,
            "params": {"intensity": 1.0},
        },
        {
            "trigger":        "section_start",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS],
            "duration_beats": 4.0,
            "params": {"color": "drop_red", "transition": "snap"},
        },
        {
            "trigger":        "beat",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.50,
            "params": {"color": "drop_red", "intensity": 0.90},
        },
        # Strobe on every beat during the drop — the main high-energy strobe effect.
        # Energy scaling drives it from ~0.45 at lower moments to 0.75+ at peaks.
        {
            "trigger":        "beat",
            "cue_type":       "strobe_hit",
            "target_groups":  [GROUP_STROBE],
            "duration_beats": 0.08,
            "params": {"intensity": 0.70},
        },
        # Back wash on beats 2&4 — note color + audience fill simultaneously.
        # Also adds a brighter strobe flash on those accented beats.
        {
            "trigger":        "beat_2_4",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_BACK_WASH],
            "use_note_color": True,
            "use_tone_duration": True,
            "duration_beats": 0.50,
            "params": {"color": "drop_yellow", "intensity": 0.80},
        },
        # Accent strobe on beats 2 & 4 — brighter burst on the snare hits
        {
            "trigger":        "beat_2_4",
            "cue_type":       "strobe_hit",
            "target_groups":  [GROUP_STROBE, GROUP_WASH_ALL],
            "duration_beats": 0.08,
            "params": {"intensity": 1.0},
        },
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS],
            "duration_beats": 0.25,
            "params": {"color": "_drop_cycle", "transition": "snap"},
        },
        # Every bar: brief high-speed pan blast — reacts to each new bar's energy
        {
            "trigger":        "bar_beat_1",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "duration_beats": 2.0,
            "params": {"speed": 1.0, "pattern": "fast_pan"},
        },
        # Every 4 bars: override with a full-section sustained fast_pan
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "duration_beats": 4.0,
            "params": {"speed": 1.0, "pattern": "fast_pan"},
        },
        # Laser: full RGB chase — horizontal sweep, all fixtures step together on beat
        {
            "trigger":        "section_start",
            "cue_type":       "laser_chase",
            "target_groups":  [GROUP_LASERS],
            "fill_section":   True,
            "params": {
                "colors":         ["laser_red", "laser_green", "laser_blue", "laser_white"],
                "beam_count":     4,
                "step_beats":     0.50,
                "intensity":      1.0,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "beat",
                "sweep_axis":     "horizontal",
                "sweep_direction":"alternating",
                "tilt_speed":     0.60,
                "tilt_range_deg": 25, "active_zones": ["overhead", "side_tower"],
            },
        },
        # Every 2 bars: wide vertical+horizontal scan — lasers sweep top-to-bottom
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 4.0,
            "params": {
                "color":          "laser_red",
                "speed":          0.95,
                "fan_count":      6,
                "spread_deg":     80,
                "intensity":      1.0,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "downbeat",
                "sweep_axis":     "vertical",
                "sweep_direction":"alternating",
                "tilt_speed":     0.80,
                "tilt_range_deg": 40, "active_zones": ["overhead", "side_tower"],
            },
        },
        # Every 4 bars: diagonal RGB chase — beams rake from high-L to low-R and back
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "laser_chase",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 8.0,
            "params": {
                "colors":         ["laser_red", "laser_yellow", "laser_green", "laser_cyan", "laser_blue", "laser_white"],
                "beam_count":     6,
                "step_beats":     0.5,
                "intensity":      1.0,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "beat",
                "sweep_axis":     "diagonal",
                "sweep_direction":"alternating",
                "tilt_speed":     0.70,
                "tilt_range_deg": 35, "active_zones": ["overhead", "floor", "side_tower"],
            },
        },
    ],

    # -----------------------------------------------------------------------
    "breakdown": [
        # Sustained low ambient wash — section stays lit throughout.
        # back_wash keeps the audience bathed in ambient teal during the quiet moment.
        {
            "trigger":        "section_start",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL, GROUP_BACK_WASH],
            "fill_section":   True,
            "params": {"color": "breakdown_teal", "intensity": 0.15, "fade_in": 2.0},
        },
        {
            "trigger":       "section_start",
            "cue_type":      "fade_out",
            "target_groups": [GROUP_SPOTS, GROUP_STROBE],
            "duration_sec":  2.0,
            "params": {"target_intensity": 0.0, "fade_time": 2.0},
        },
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "fill_section":   True,
            "params": {"speed": 0.15, "pattern": "slow_drift"},
        },
        # Breakdown washes drift with note color — atmospheric chromatic variation
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL, GROUP_BACK_WASH],
            "use_note_color": True,
            "use_tone_duration": True,
            "duration_beats": 8.0,
            "params": {"color": "breakdown_teal", "intensity": 0.18, "fade_in": 1.5},
        },
        # Very subtle strobe flash every 4 bars — just enough to keep tension alive.
        # Energy scaling will suppress it further in the quietest moments.
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "strobe_hit",
            "target_groups":  [GROUP_STROBE],
            "duration_beats": 0.10,
            "params": {"intensity": 0.15},
        },
        # Laser: very slow diagonal drift — ghostly atmospheric beam, always moving
        {
            "trigger":       "section_start",
            "cue_type":      "laser_scan",
            "target_groups": [GROUP_LASERS],
            "fill_section":  True,
            "params": {
                "color":          "laser_blue",
                "speed":          0.08,
                "fan_count":      1,
                "spread_deg":     20,
                "intensity":      0.30,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "bar",
                "sweep_axis":     "diagonal",
                "sweep_direction":"left_to_right",
                "tilt_speed":     0.06,
                "tilt_range_deg": 18, "active_zones": ["overhead"],
            },
        },
    ],

    # -----------------------------------------------------------------------
    "outro": [
        # Sustained low wash covers full outro — fades via bar-level linear_fade
        {
            "trigger":        "section_start",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL, GROUP_BACK_WASH],
            "fill_section":   True,
            "params": {"color": "outro_blue", "intensity": 0.30, "fade_in": 1.0},
        },
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "fill_section":   True,
            "params": {"speed": 0.10, "pattern": "slow_drift"},
        },
        {
            "trigger":        "bar_beat_1",
            "cue_type":       "fade_out",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS, GROUP_BACK_WASH],
            "duration_beats": 4.0,
            "params": {
                "color":           "outro_blue",
                "intensity_start": 0.30,
                "intensity_end":   0.0,
                "_linear_fade":    True,
            },
        },
        # Laser: slow horizontal drift fading to nothing — all fixtures sweep together
        {
            "trigger":        "section_start",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "fill_section":   True,
            "params": {
                "color":          "laser_blue",
                "speed":          0.10,
                "fan_count":      1,
                "spread_deg":     10,
                "intensity":      0.20,
                "projection":     "aerial",
                "synchronized":   True,
                "beat_sync":      "bar",
                "sweep_axis":     "horizontal",
                "sweep_direction":"left_to_right",
                "tilt_speed":     0.05,
                "tilt_range_deg": 10, "active_zones": ["overhead"],
            },
        },
        # Progressive laser-off starting mid-outro (every bar)
        {
            "trigger":        "bar_beat_1",
            "cue_type":       "laser_off",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 4.0,
            "params": {},
        },
    ],
}


# ---------------------------------------------------------------------------
# Section motion alternatives
# ---------------------------------------------------------------------------
# Per-section lists of motion family names for laser and movement cue types.
# The cue engine uses these when selecting alternatives for repeated play,
# ensuring variety across multiple listens of the same track.

SECTION_MOTION_ALTERNATIVES: dict[str, dict[str, list[str]]] = {
    "intro": {
        "laser":    ["minimal_source_reveal", "hold_then_snap", "slow_drift", "fade_to_black"],
        "movement": ["slow_drift", "static_hold", "minimal_source_reveal"],
    },
    "build": {
        "laser":    [
            "fan_open", "center_converge", "alternating_side_sweep",
            "ceiling_rake", "staggered_chase", "upper_lower_layer_split",
        ],
        "movement": ["sweep", "alternating_side_sweep", "fan_open"],
    },
    "drop": {
        "laser":    [
            "crosshatch", "laser_burst_cluster", "audience_rake", "burst_outward",
            "tunnel", "staggered_chase", "horizontal_sheet_plane", "symmetrical_mirror",
            "reveal_whiteout", "beam_stack", "upper_lower_layer_split",
        ],
        "movement": ["fast_pan", "radial_wash_expand", "burst_outward", "symmetrical_mirror"],
    },
    "breakdown": {
        "laser":    [
            "sheet_plane", "hold_then_snap", "fan_close", "center_converge",
            "horizontal_sheet_plane", "slow_drift",
        ],
        "movement": ["slow_drift", "fan_close", "hold_then_snap"],
    },
    "outro": {
        "laser":    ["fade_to_black", "slow_drift", "minimal_source_reveal", "fan_close"],
        "movement": ["slow_drift", "fade_to_black", "static_hold"],
    },
}
