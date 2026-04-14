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
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------

COLORS: dict[str, tuple[int, int, int]] = {
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

GROUP_WASH_ALL = "wash_all"
GROUP_SPOTS = "spots"
GROUP_MOVING_HEADS = "moving_heads"
GROUP_STROBE = "strobe"
GROUP_BACK_WASH = "back_wash"


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

SECTION_RULES: dict[str, list[dict]] = {

    # -----------------------------------------------------------------------
    "intro": [
        # Section start: set all wash fixtures to a low-intensity cool wash
        {
            "trigger":       "section_start",
            "cue_type":      "wash",
            "target_groups": [GROUP_WASH_ALL],
            "duration_sec":  4.0,
            "params": {"color": "cool_blue", "intensity": 0.30, "fade_in": 2.0},
        },
        # Every bar (beat 1): gentle pulse to indicate energy without strobing
        {
            "trigger":        "bar_beat_1",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.25,
            "params": {"color": "cool_blue", "intensity": 0.40},
        },
    ],

    # -----------------------------------------------------------------------
    "build": [
        # Enable moving heads at moderate speed as section starts
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "duration_beats": 4.0,
            "params": {"speed": 0.40, "pattern": "sweep"},
        },
        # Every beat: intensity linearly ramps from 0.40 → 0.90 over the section.
        # cue_engine computes per-beat intensity from section progress.
        {
            "trigger":        "beat",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.50,
            "params": {
                "color":           "warm_amber",
                "intensity_start": 0.40,
                "intensity_end":   0.90,
                "_ramp":           True,  # engine reads this flag to compute per-beat intensity
            },
        },
        # Color shift every 4 bars; color cycles through BUILD_COLOR_CYCLE
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.25,
            "params": {
                "color":       "_build_cycle",  # engine resolves this dynamically
                "transition":  "snap",
            },
        },
        # Final 4 bars: strobe hit on beat 1 and beat 3 to build tension
        {
            "trigger":        "build_last4",
            "cue_type":       "strobe_hit",
            "target_groups":  [GROUP_STROBE],
            "duration_beats": 0.125,
            "params": {"intensity": 1.0},
        },
        # Very last beat before the drop: white flash on all groups
        {
            "trigger":        "pre_drop",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS],
            "duration_beats": 0.25,
            "params": {"color": "pure_white", "transition": "snap"},
        },
    ],

    # -----------------------------------------------------------------------
    "drop": [
        # Opening hit: simultaneous strobe burst + color to drop_red
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
        # Every beat: front wash pulse at 90%
        {
            "trigger":        "beat",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 0.50,
            "params": {"color": "drop_red", "intensity": 0.90},
        },
        # Beat 2 and 4 of every bar: back wash counter-punch
        {
            "trigger":        "beat_2_4",
            "cue_type":       "pulse",
            "target_groups":  [GROUP_BACK_WASH],
            "duration_beats": 0.50,
            "params": {"color": "drop_yellow", "intensity": 0.80},
        },
        # Every 2 bars: cycle through drop colors on wash + spots
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "color_shift",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS],
            "duration_beats": 0.25,
            "params": {
                "color":       "_drop_cycle",  # engine resolves dynamically
                "transition":  "snap",
            },
        },
        # Every 4 bars: moving heads kick to full-speed pan
        {
            "trigger":        "bar_4_beat_1",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "duration_beats": 4.0,
            "params": {"speed": 1.0, "pattern": "fast_pan"},
        },
    ],

    # -----------------------------------------------------------------------
    "breakdown": [
        # Immediate fade to near-black
        {
            "trigger":       "section_start",
            "cue_type":      "fade_out",
            "target_groups": [GROUP_WASH_ALL, GROUP_SPOTS, GROUP_STROBE],
            "duration_sec":  2.0,
            "params": {"target_intensity": 0.15, "fade_time": 2.0},
        },
        # Slow movement on moving heads
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "duration_beats": 4.0,
            "params": {"speed": 0.15, "pattern": "slow_drift"},
        },
        # Every 2 bars: single slow wash
        {
            "trigger":        "bar_2_beat_1",
            "cue_type":       "wash",
            "target_groups":  [GROUP_WASH_ALL],
            "duration_beats": 8.0,  # holds for 2 bars
            "params": {"color": "breakdown_teal", "intensity": 0.20, "fade_in": 1.5},
        },
    ],

    # -----------------------------------------------------------------------
    "outro": [
        # Slow down movement at section start
        {
            "trigger":        "section_start",
            "cue_type":       "movement_enable",
            "target_groups":  [GROUP_MOVING_HEADS],
            "duration_beats": 4.0,
            "params": {"speed": 0.10, "pattern": "slow_drift"},
        },
        # Each bar: fade_out with linearly decreasing intensity (0.40 → 0.0).
        # Engine computes per-bar intensity from bar position within section.
        {
            "trigger":        "bar_beat_1",
            "cue_type":       "fade_out",
            "target_groups":  [GROUP_WASH_ALL, GROUP_SPOTS, GROUP_BACK_WASH],
            "duration_beats": 4.0,
            "params": {
                "color":              "outro_blue",
                "intensity_start":    0.40,
                "intensity_end":      0.0,
                "_linear_fade":       True,  # engine computes per-bar intensity
            },
        },
    ],
}
