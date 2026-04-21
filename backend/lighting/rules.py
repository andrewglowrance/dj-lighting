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
        # Sustained ambient wash that covers the full intro — no dark gaps
        {
            "trigger":       "section_start",
            "cue_type":      "wash",
            "target_groups": [GROUP_WASH_ALL],
            "fill_section":  True,
            "params": {"color": "cool_blue", "intensity": 0.20, "fade_in": 2.0},
        },
        # Gentle slow movement — adds depth without distracting
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "fill_section":   True,
            "params": {"speed": 0.12, "pattern": "slow_drift"},
        },
        {
            "trigger":        "bar_beat_1",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.25,
            "params": {"color": "cool_blue", "intensity": 0.40},
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
        # Sustained low-level wash fills the section between pulses
        {
            "trigger":        "section_start",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL],
            "fill_section":   True,
            "params": {"color": "warm_amber", "intensity": 0.22, "fade_in": 0.5},
        },
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "fill_section":   True,
            "params": {"speed": 0.40, "pattern": "sweep"},
        },
        {
            "trigger":        "beat",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.50,
            "params": {
                "color":           "warm_amber",
                "intensity_start": 0.40,
                "intensity_end":   0.90,
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
        # Laser: slow single-beam scan that sustains the whole build
        {
            "trigger":        "section_start",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "fill_section":   True,
            "params": {
                "color":      "laser_green",
                "speed":      0.25,
                "fan_count":  1,
                "spread_deg": 10,
                "intensity":  0.60,
            },
        },
        # Last 4 bars: widen to 3-beam scan, speed up (overrides fill above)
        {
            "trigger":        "build_last4",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 1.0,
            "params": {
                "color":      "laser_cyan",
                "speed":      0.70,
                "fan_count":  3,
                "spread_deg": 30,
                "intensity":  0.85,
            },
        },
        # Pre-drop: laser snaps to white static fan — anticipation hit
        {
            "trigger":        "pre_drop",
            "cue_type":       "laser_static",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 0.25,
            "params": {
                "color":      "laser_white",
                "pattern":    "fan",
                "fan_count":  5,
                "spread_deg": 60,
                "intensity":  1.0,
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
        {
            "trigger":        "beat_2_4",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_BACK_WASH],
            "duration_beats": 0.50,
            "params": {"color": "drop_yellow", "intensity": 0.80},
        },
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS],
            "duration_beats": 0.25,
            "params": {"color": "_drop_cycle", "transition": "snap"},
        },
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "duration_beats": 4.0,
            "params": {"speed": 1.0, "pattern": "fast_pan"},
        },
        # Laser: full RGB chase that sustains the entire drop
        {
            "trigger":        "section_start",
            "cue_type":       "laser_chase",
            "target_groups":  [GROUP_LASERS],
            "fill_section":   True,
            "params": {
                "colors":      ["laser_red", "laser_green", "laser_blue", "laser_white"],
                "beam_count":  6,
                "step_beats":  0.25,
                "intensity":   1.0,
            },
        },
        # Every 2 bars: alternate between chase and full fan
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "laser_static",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 4.0,
            "params": {
                "color":      "laser_red",
                "pattern":    "x_cross",
                "fan_count":  6,
                "spread_deg": 80,
                "intensity":  1.0,
            },
        },
        # Every 4 bars: back to RGB chase
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "laser_chase",
            "target_groups":  [GROUP_LASERS],
            "duration_beats": 8.0,
            "params": {
                "colors":      ["laser_red", "laser_yellow", "laser_green", "laser_cyan", "laser_blue", "laser_white"],
                "beam_count":  6,
                "step_beats":  0.5,
                "intensity":   1.0,
            },
        },
    ],

    # -----------------------------------------------------------------------
    "breakdown": [
        # Sustained low ambient wash — section stays lit throughout
        {
            "trigger":        "section_start",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL],
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
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 8.0,
            "params": {"color": "breakdown_teal", "intensity": 0.20, "fade_in": 1.5},
        },
        # Laser: single atmospheric beam that holds for the full section
        {
            "trigger":       "section_start",
            "cue_type":      "laser_static",
            "target_groups": [GROUP_LASERS],
            "fill_section":  True,
            "params": {
                "color":      "laser_blue",
                "pattern":    "single",
                "fan_count":  1,
                "spread_deg": 0,
                "intensity":  0.30,
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
        # Laser: slow single-beam scan that sustains the full outro
        {
            "trigger":        "section_start",
            "cue_type":       "laser_scan",
            "target_groups":  [GROUP_LASERS],
            "fill_section":   True,
            "params": {
                "color":      "laser_blue",
                "speed":      0.10,
                "fan_count":  1,
                "spread_deg": 10,
                "intensity":  0.20,
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
