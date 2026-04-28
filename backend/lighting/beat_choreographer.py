"""
beat_choreographer.py

Three-level choreography planner.

Level 2: phrase/bar — assigns different motion variants every 2/4/8 bars
Level 3: beat — modulates intensity, spread, direction per beat position

Phrase length is energy-dependent:
    energy > 0.75 → 2-bar phrases  (fast, high-energy sections)
    0.45-0.75     → 4-bar phrases  (medium energy)
    < 0.45        → 8-bar phrases  (slow, ambient)

All selection is deterministic: same fingerprint + section_index always
produces the same phrase plan.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from backend.lighting.motion_variants import get_variants, get_beat_behaviors


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PhraseSlot:
    """One phrase period within a section."""
    phrase_index:     int
    bar_start:        int    # 0-based within section
    bar_end:          int    # exclusive
    motion_variant:   str    # e.g. "expand_left"
    beat_behavior:    str    # e.g. "micro_snap_on_beat"
    direction:        str    # "left" | "right" | "center" | "alternating" | "expand"
    color_key:        str    # laser color (empty = use base vocab color)
    spread_scale:     float  # multiplier on base spread_deg
    density_scale:    float  # multiplier on beam_count / fan_count
    zone_emphasis:    str    # "upper" | "lower" | "full" | "side"
    variation_reason: str


@dataclass
class PhrasePlan:
    """Complete phrase plan for one section."""
    motion_family:         str
    section_label:         str
    phrase_length_bars:    int
    phrases:               list[PhraseSlot]
    dominant_beat_behavior: str

    def get_phrase_for_bar(self, bar_index_in_section: int) -> PhraseSlot:
        """Return the PhraseSlot active at this bar offset."""
        phrase_idx = bar_index_in_section // max(self.phrase_length_bars, 1)
        phrase_idx = min(phrase_idx, len(self.phrases) - 1)
        return self.phrases[phrase_idx]

    def get_laser_override(
        self,
        bar_index_in_section: int,
        base_params: dict,
    ) -> dict:
        """
        Return laser params modified by the active phrase variant.
        Adds phrase metadata keys so the frontend can use them.
        """
        slot = self.get_phrase_for_bar(bar_index_in_section)
        p = dict(base_params)

        # Color override (only for single-color cues; skip laser_chase 'colors' list)
        if slot.color_key and "colors" not in p:
            p["color"] = slot.color_key

        # Spread scale
        if "spread_deg" in p:
            new_s = round(float(p["spread_deg"]) * slot.spread_scale, 1)
            p["spread_deg"] = max(3.0, min(120.0, new_s))

        # Density scale
        if "fan_count" in p:
            p["fan_count"] = max(1, min(8, round(float(p["fan_count"]) * slot.density_scale)))
        if "beam_count" in p:
            p["beam_count"] = max(1, min(12, round(float(p["beam_count"]) * slot.density_scale)))

        # Inject phrase metadata
        p["phrase_index"]      = slot.phrase_index
        p["motion_variant"]    = slot.motion_variant
        p["beat_behavior"]     = slot.beat_behavior
        p["direction"]         = slot.direction
        p["zone_usage"]        = [slot.zone_emphasis]
        p["variation_reason"]  = slot.variation_reason

        return p

    def get_movement_override(
        self,
        bar_index_in_section: int,
        base_params: dict,
    ) -> dict:
        """Return movement_enable params modified by phrase direction."""
        slot = self.get_phrase_for_bar(bar_index_in_section)
        p = dict(base_params)

        if slot.direction == "alternating":
            p["pattern"] = "fast_pan"
        elif slot.direction in ("left", "right", "expand"):
            p["pattern"] = "sweep"

        p["phrase_index"]   = slot.phrase_index
        p["motion_variant"] = slot.motion_variant
        p["beat_behavior"]  = slot.beat_behavior
        p["direction"]      = slot.direction

        return p

    def get_beat_modulation(
        self,
        beat_in_bar: int,
        bar_index_in_section: int,
        beat_energy: float,
    ) -> dict:
        """
        Return per-beat modulation params.

        Keys returned:
            beat_behavior (str)
            phrase_index  (int)
            motion_variant (str)
            intensity_mod  (float) — multiplier applied to intensity fields
            spread_mod     (float) — multiplier applied to spread_deg in laser cues
            direction      (str)   — current directional hint for the renderer
        """
        slot = self.get_phrase_for_bar(bar_index_in_section)
        beh = slot.beat_behavior

        mod: dict = {
            "beat_behavior":   beh,
            "phrase_index":    slot.phrase_index,
            "motion_variant":  slot.motion_variant,
            "direction":       slot.direction,
            "intensity_mod":   1.0,
            "spread_mod":      1.0,
        }

        if beh == "micro_snap_on_beat":
            mod["intensity_mod"] = 0.85 + 0.15 * int(beat_in_bar == 0)
            mod["spread_mod"]    = 1.0  + 0.08 * int(beat_in_bar % 2 == 0)

        elif beh == "downbeat_hit":
            if beat_in_bar == 0:
                mod["intensity_mod"] = 1.15
            else:
                mod["intensity_mod"] = 0.70
                mod["spread_mod"]    = 0.90

        elif beh == "alternating_L_R":
            mod["direction"]     = "left" if (beat_in_bar // 2) % 2 == 0 else "right"
            mod["intensity_mod"] = 0.90 + 0.10 * int(beat_in_bar == 0)

        elif beh == "density_pulse":
            mod["intensity_mod"] = 1.00 if beat_in_bar in (0, 2) else 0.75

        elif beh == "fan_width_modulation":
            phase = beat_in_bar / 4.0
            mod["spread_mod"]    = 0.88 + 0.22 * math.sin(phase * 2 * math.pi)
            mod["intensity_mod"] = 0.90

        elif beh == "center_snap":
            if beat_in_bar == 0:
                mod["spread_mod"]    = 0.55
                mod["intensity_mod"] = 1.10
            elif beat_in_bar == 2:
                mod["spread_mod"]    = 1.30
                mod["intensity_mod"] = 0.85
            else:
                mod["spread_mod"]    = 1.00
                mod["intensity_mod"] = 0.90

        elif beh == "brightness_pulse":
            mod["intensity_mod"] = (
                1.15 if beat_in_bar == 0
                else 0.92 if beat_in_bar == 2
                else 0.85
            )

        elif beh == "rake_pulse":
            mod["intensity_mod"] = 1.00 if beat_in_bar in (0, 2) else 0.80

        elif beh in ("hold_then_release", "progressive_expand"):
            mod["intensity_mod"] = 0.75 + 0.10 * int(beat_in_bar == 0)
            mod["spread_mod"]    = 1.20 if beat_in_bar == 0 else 0.85

        elif beh == "very_subtle_pulse":
            mod["intensity_mod"] = 0.92 + 0.05 * int(beat_in_bar == 0)

        elif beh == "2bar_angle_shift":
            # Handled at bar level; at beat level just a subtle pulse
            mod["intensity_mod"] = 0.90 + 0.08 * int(beat_in_bar == 0)

        # Cap intensity_mod so we never exceed 1.0 after the global scale
        mod["intensity_mod"] = min(1.20, max(0.30, mod["intensity_mod"]))
        mod["spread_mod"]    = min(2.00, max(0.30, mod["spread_mod"]))
        return mod


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------

def _hash_pick(key: str, n: int) -> int:
    """Return a deterministic integer in [0, n) using MD5."""
    if n <= 0:
        return 0
    h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
    return h % n


def _pick_avoiding(key: str, options: list, exclude: str | None) -> str:
    """Deterministically pick from options, avoiding exclude if possible."""
    filtered = [o for o in options if o != exclude] if exclude else options
    pool = filtered if filtered else options
    if not pool:
        return exclude or ""
    return pool[_hash_pick(key, len(pool))]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan_section(
    section_label:   str,
    motion_family:   str,
    section_energy:  float,
    n_bars:          int,
    fingerprint:     str,
    section_index:   int,
) -> PhrasePlan:
    """
    Build a PhrasePlan for one section.

    Phrase length depends on energy:
        > 0.75  → 2 bars  (high-energy: fast geometric changes)
        0.45-0.75 → 4 bars (medium)
        < 0.45  → 8 bars  (ambient/slow sections)
    """
    if section_energy > 0.75:
        phrase_length = 2
    elif section_energy > 0.45:
        phrase_length = 4
    else:
        phrase_length = 8

    n_phrases = max(1, math.ceil(n_bars / phrase_length))

    variants  = get_variants(motion_family)
    behaviors = get_beat_behaviors(motion_family)

    zone_options = ["upper", "full", "lower", "side", "full", "upper"]  # weighted toward full/upper

    _VARIATION_REASONS = [
        "opening phrase — matched to reference archetype",
        "diversity rotation: geometry shift",
        "phrase contrast: direction change",
        "density variation: anti-repetition rule",
        "color transition within section",
        "energy response: intensity modulation",
        "reference-guided variant selection",
    ]

    phrases: list[PhraseSlot] = []
    prev_variant_id: str | None = None
    prev_behavior:   str | None = None

    for i in range(n_phrases):
        bar_start = i * phrase_length
        bar_end   = min(bar_start + phrase_length, n_bars)

        # Variant selection (avoid repeating previous)
        v_key     = f"{fingerprint}|{section_index}|v|{i}"
        v_options = [v["variant_id"] for v in variants]
        v_id      = _pick_avoiding(v_key, v_options, prev_variant_id)
        variant   = next((v for v in variants if v["variant_id"] == v_id), variants[0])

        # Beat behavior selection (avoid repeating previous)
        b_key    = f"{fingerprint}|{section_index}|b|{i}"
        behavior = _pick_avoiding(b_key, behaviors, prev_behavior)

        # Zone emphasis
        z_key  = f"{fingerprint}|{section_index}|z|{i}"
        zone   = zone_options[_hash_pick(z_key, len(zone_options))]

        reason = _VARIATION_REASONS[i % len(_VARIATION_REASONS)]

        phrases.append(PhraseSlot(
            phrase_index     = i,
            bar_start        = bar_start,
            bar_end          = bar_end,
            motion_variant   = v_id,
            beat_behavior    = behavior,
            direction        = variant.get("direction", "center"),
            color_key        = variant.get("color") or "",
            spread_scale     = float(variant.get("spread_scale", 1.0)),
            density_scale    = float(variant.get("density_scale", 1.0)),
            zone_emphasis    = zone,
            variation_reason = reason,
        ))

        prev_variant_id = v_id
        prev_behavior   = behavior

    dominant_behavior = phrases[0].beat_behavior if phrases else "downbeat_hit"

    return PhrasePlan(
        motion_family          = motion_family,
        section_label          = section_label,
        phrase_length_bars     = phrase_length,
        phrases                = phrases,
        dominant_beat_behavior = dominant_behavior,
    )
