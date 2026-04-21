"""
lighting/style_engine.py

Applies a StyleProfile to a CueOutputSchema, returning a new CueOutputSchema.

The music-derived timing structure is NEVER modified — only cue parameters
(intensities, colors, speeds, fan widths) and cue presence (filtered out based
on density / disabled flags) are affected.

Entry point:
    apply_style(raw_cues, profile, timeline) → CueOutputSchema

Design notes:
  - Every Cue is deep-copied before modification; raw_cues is not mutated.
  - Section brightness is derived from both the per-section scale and
    section_emphasis weight, giving fine-grained control per section.
  - High-frequency triggers (beat, beat_2_4, bar_beat_1) are subject to
    density filtering — a deterministic hash of the cue id selects which
    cues survive, keeping the filter reproducible across revisions.
  - Color substitution uses a fixed mapping table; unknown colors pass through.
"""

from __future__ import annotations

import hashlib
import copy
from typing import Any

from backend.schemas.cues import Cue, CueOutputSchema
from backend.schemas.style import StyleProfile
from backend.schemas.timeline import TimelineSchema


# ---------------------------------------------------------------------------
# Color substitution tables
# ---------------------------------------------------------------------------

# Wash palette maps (bidirectional)
_COOL_WASH: dict[str, str] = {
    "warm_amber":   "cool_blue",
    "build_orange": "breakdown_teal",
    "drop_red":     "deep_purple",
    "drop_yellow":  "cool_blue",
    "pure_white":   "cool_blue",     # not substituted in monochrome
}
_WARM_WASH: dict[str, str] = {
    "cool_blue":      "warm_amber",
    "deep_purple":    "drop_red",
    "breakdown_teal": "warm_amber",
    "outro_blue":     "warm_amber",
    "pure_white":     "warm_amber",
}

# Laser palette maps
_COOL_LASER: dict[str, str] = {
    "laser_red":    "laser_blue",
    "laser_yellow": "laser_cyan",
}
_WARM_LASER: dict[str, str] = {
    "laser_blue":  "laser_red",
    "laser_cyan":  "laser_yellow",
}
_GREEN_LASER: dict[str, str] = {
    k: "laser_green"
    for k in ("laser_red", "laser_blue", "laser_white", "laser_cyan", "laser_yellow")
}
_RED_LASER: dict[str, str] = {
    k: "laser_red"
    for k in ("laser_green", "laser_blue", "laser_white", "laser_cyan", "laser_yellow")
}
_WHITE_LASER: dict[str, str] = {
    k: "laser_white"
    for k in ("laser_red", "laser_green", "laser_blue", "laser_cyan", "laser_yellow")
}

# Map StyleProfile.laser_profile.palette → substitution dict
_LASER_PALETTE_MAP: dict[str, dict[str, str]] = {
    "cool":        _COOL_LASER,
    "warm":        _WARM_LASER,
    "green_only":  _GREEN_LASER,
    "red_only":    _RED_LASER,
    "white_only":  _WHITE_LASER,
    "rgb":         {},   # pass-through (all colors OK)
    "auto":        {},   # determined by wash palette
}


# ---------------------------------------------------------------------------
# Triggers subject to density filtering
# ---------------------------------------------------------------------------

_DENSITY_TRIGGERS = frozenset({"beat", "beat_2_4", "bar_beat_1"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section_scale(section: str, profile: StyleProfile) -> float:
    """
    Combined brightness scale for a section:
      global_scale × per-section_scale × section_emphasis_weight
    """
    bp = profile.brightness_profile
    se = profile.section_emphasis
    section_scales = {
        "intro":     bp.intro_scale     * se.intro_weight,
        "build":     bp.build_scale     * se.build_weight,
        "drop":      bp.drop_scale      * se.drop_weight,
        "breakdown": bp.breakdown_scale * se.breakdown_weight,
        "outro":     bp.outro_scale     * se.outro_weight,
    }
    return bp.global_scale * section_scales.get(section, 1.0)


def _density_keep(cue_id: str, density: float) -> bool:
    """Deterministic density filter using MD5 hash of the cue id."""
    if density >= 1.0:
        return True
    if density <= 0.0:
        return False
    h = int(hashlib.md5(cue_id.encode()).hexdigest(), 16) % 10_000
    return h < int(density * 10_000)


def _scale_intensity(v: Any, scale: float) -> float:
    """Scale a numeric intensity value, clamping to [0, 1]."""
    if isinstance(v, (int, float)):
        return round(min(1.0, max(0.0, float(v) * scale)), 4)
    return v


def _sub_color(color: str, table: dict[str, str]) -> str:
    return table.get(color, color)


def _sub_laser_colors(colors: list[str], table: dict[str, str]) -> list[str]:
    return [table.get(c, c) for c in colors]


def _effective_laser_table(profile: StyleProfile) -> dict[str, str]:
    """Pick the laser color substitution table based on laser_profile.palette."""
    lp_palette = profile.laser_profile.palette
    if lp_palette != "auto":
        return _LASER_PALETTE_MAP.get(lp_palette, {})
    # "auto" inherits wash palette direction
    if profile.palette == "cool":
        return _COOL_LASER
    if profile.palette == "warm":
        return _WARM_LASER
    return {}


def _effective_wash_table(profile: StyleProfile) -> dict[str, str]:
    if profile.palette == "cool":
        return _COOL_WASH
    if profile.palette == "warm":
        return _WARM_WASH
    return {}


# ---------------------------------------------------------------------------
# Per-cue style application
# ---------------------------------------------------------------------------

def _style_cue(cue: Cue, profile: StyleProfile) -> Cue | None:
    """
    Apply the style profile to a single cue.
    Returns None if the cue should be filtered out entirely.
    """
    lp = profile.laser_profile
    sp = profile.strobe_profile
    mp = profile.movement_profile
    is_laser = cue.cue_type.startswith("laser_")

    # ── Filtering ────────────────────────────────────────────────────────
    # Laser: disabled entirely
    if is_laser and not lp.enabled:
        return None

    # Laser: restrict to drops
    if is_laser and lp.restrict_to_drops and cue.section != "drop":
        return None

    # laser_off passes through with no parameter changes
    if cue.cue_type == "laser_off":
        return cue

    # Strobe: disabled
    if cue.cue_type == "strobe_hit" and not sp.enabled:
        return None

    # Strobe: restrict to drops
    if cue.cue_type == "strobe_hit" and sp.restrict_to_drops and cue.section != "drop":
        return None

    # Movement: disabled
    if cue.cue_type == "movement_enable" and not mp.enabled:
        return None

    # Density filter (only for high-frequency non-structural triggers)
    if cue.trigger in _DENSITY_TRIGGERS:
        effective_density = profile.visual_density
        if is_laser:
            effective_density = min(effective_density, lp.density)
        if not _density_keep(cue.id, effective_density):
            return None

    # ── Parameter modification ────────────────────────────────────────────
    params = copy.copy(cue.parameters)
    s_scale = _section_scale(cue.section, profile)
    wash_table  = _effective_wash_table(profile)
    laser_table = _effective_laser_table(profile)

    if is_laser:
        params = _style_laser_params(params, cue.cue_type, profile, laser_table)
    elif cue.cue_type == "strobe_hit":
        params = _style_strobe_params(params, s_scale, sp)
    elif cue.cue_type == "movement_enable":
        params = _style_movement_params(params, mp)
    else:
        params = _style_wash_params(params, s_scale, wash_table)

    if params == cue.parameters:
        return cue   # nothing changed — return original object

    return Cue(
        id=cue.id,
        time=cue.time,
        duration=cue.duration,
        cue_type=cue.cue_type,
        section=cue.section,
        trigger=cue.trigger,
        target_groups=cue.target_groups,
        parameters=params,
    )


def _style_wash_params(
    params: dict, scale: float, color_table: dict[str, str]
) -> dict:
    p = dict(params)
    # Color substitution
    if "color" in p:
        p["color"] = _sub_color(p["color"], color_table)
    # Intensity scaling
    for key in ("intensity", "target_intensity"):
        if key in p:
            p[key] = _scale_intensity(p[key], scale)
    # Range intensities
    for key in ("intensity_start", "intensity_end"):
        if key in p:
            p[key] = _scale_intensity(p[key], scale)
    return p


def _style_strobe_params(params: dict, scale: float, sp) -> dict:
    p = dict(params)
    combined = scale * sp.intensity_scale
    if "intensity" in p:
        p["intensity"] = _scale_intensity(p["intensity"], combined)
    return p


def _style_movement_params(params: dict, mp) -> dict:
    p = dict(params)
    if "speed" in p and isinstance(p["speed"], (int, float)):
        p["speed"] = round(min(1.0, max(0.0, float(p["speed"]) * mp.speed_scale)), 4)
    if mp.transition_style != "auto" and "pattern" not in p:
        p["transition_style"] = mp.transition_style
    return p


def _style_laser_params(
    params: dict, cue_type: str, profile: StyleProfile, laser_table: dict[str, str]
) -> dict:
    lp = profile.laser_profile
    p = dict(params)

    # Intensity scaling
    if "intensity" in p:
        s = _section_scale("drop", profile) if profile.laser_profile.restrict_to_drops else 1.0
        p["intensity"] = _scale_intensity(p["intensity"], lp.intensity_scale * s)

    # Color substitution
    if "color" in p:
        p["color"] = _sub_color(p["color"], laser_table)
    if "colors" in p and isinstance(p["colors"], list):
        p["colors"] = _sub_laser_colors(p["colors"], laser_table)

    # Fan width
    if "spread_deg" in p and isinstance(p["spread_deg"], (int, float)):
        p["spread_deg"] = round(
            min(180.0, max(0.0, float(p["spread_deg"]) * lp.fan_width_scale)), 2)

    # Movement speed (laser_scan)
    if cue_type == "laser_scan" and "speed" in p:
        p["speed"] = round(min(1.0, max(0.0, float(p["speed"]) * lp.movement_speed)), 4)

    # Chase intensity
    if cue_type == "laser_chase":
        if "intensity" in p:
            p["intensity"] = _scale_intensity(p["intensity"], lp.chase_intensity)

    return p


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def apply_style(
    raw_cues: CueOutputSchema,
    profile: StyleProfile,
    timeline: TimelineSchema,          # kept for possible future per-beat scaling
) -> CueOutputSchema:
    """
    Apply a StyleProfile to a set of raw (un-styled) cues.

    The raw_cues object is never mutated.  Returns a new CueOutputSchema.
    """
    styled: list[Cue] = []
    for cue in raw_cues.cues:
        result = _style_cue(cue, profile)
        if result is not None:
            styled.append(result)

    return CueOutputSchema(
        bpm=raw_cues.bpm,
        total_duration_sec=raw_cues.total_duration_sec,
        total_cues=len(styled),
        cues=styled,
    )
