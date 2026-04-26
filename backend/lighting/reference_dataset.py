"""
lighting/reference_dataset.py

Embedded reference dataset from annotated DJ video segments.
Provides query functions for influential segments, realism priors, and motion
family bias weights used by the cue engine's diversity/reference layer.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Embedded dataset
# ---------------------------------------------------------------------------

_DATASET: dict[str, dict] = {
    "v1_drop_crosshatch": {
        "segment_id": "v1_drop_crosshatch",
        "section_type": "drop_or_peak",
        "reference_weight": 0.95,
        "exclude_from_training": False,
        "motion_families": ["crosshatch", "laser_burst_cluster", "audience_rake", "symmetrical_mirror"],
        "laser_presence": 0.98,
        "realism_priors": {
            "haze_density": 0.82,
            "source_legibility": 0.46,
            "audience_reveal_strength": 0.12,
            "stage_visibility": 0.14,
            "screen_visibility": 0.08,
        },
    },
    "v1_transition_fan": {
        "segment_id": "v1_transition_fan",
        "section_type": "transition",
        "reference_weight": 0.72,
        "exclude_from_training": False,
        "motion_families": ["fan_open", "color_split_transition", "stage_reveal"],
        "laser_presence": 0.70,
        "realism_priors": {
            "haze_density": 0.62,
            "source_legibility": 0.44,
            "audience_reveal_strength": 0.10,
            "stage_visibility": 0.34,
            "screen_visibility": 0.40,
        },
    },
    "v1_sustain_converge": {
        "segment_id": "v1_sustain_converge",
        "section_type": "sustain",
        "reference_weight": 0.88,
        "exclude_from_training": False,
        "motion_families": ["center_converge", "slow_sweep", "hold_then_snap"],
        "laser_presence": 0.60,
        "realism_priors": {
            "haze_density": 0.76,
            "source_legibility": 0.54,
            "audience_reveal_strength": 0.06,
            "stage_visibility": 0.16,
            "screen_visibility": 0.0,
        },
    },
    "v1_rebuild_hybrid": {
        "segment_id": "v1_rebuild_hybrid",
        "section_type": "rebuild_or_secondary_peak",
        "reference_weight": 0.90,
        "exclude_from_training": False,
        "motion_families": ["upper_lower_layer_split", "beam_stack", "fan_open", "alternating_side_sweep"],
        "laser_presence": 0.75,
        "realism_priors": {
            "haze_density": 0.74,
            "source_legibility": 0.58,
            "audience_reveal_strength": 0.08,
            "stage_visibility": 0.20,
            "screen_visibility": 0.0,
        },
    },
    "v1_reveal_whiteout": {
        "segment_id": "v1_reveal_whiteout",
        "section_type": "reveal_peak",
        "reference_weight": 0.97,
        "exclude_from_training": False,
        "motion_families": ["beam_stack", "reveal_whiteout", "audience_reveal"],
        "laser_presence": 0.22,
        "realism_priors": {
            "haze_density": 0.84,
            "source_legibility": 0.72,
            "audience_reveal_strength": 0.44,
            "stage_visibility": 0.28,
            "screen_visibility": 0.0,
        },
    },
    "v2_ambient_intro": {
        "segment_id": "v2_ambient_intro",
        "section_type": "ambient_intro",
        "reference_weight": 0.80,
        "exclude_from_training": False,
        "motion_families": ["static_hold", "minimal_source_reveal"],
        "laser_presence": 0.0,
        "realism_priors": {
            "haze_density": 0.25,
            "source_legibility": 0.38,
            "audience_reveal_strength": 0.12,
            "stage_visibility": 0.26,
            "screen_visibility": 0.0,
        },
    },
    "v2_white_beam_reveal": {
        "segment_id": "v2_white_beam_reveal",
        "section_type": "white_beam_reveal",
        "reference_weight": 0.93,
        "exclude_from_training": False,
        "motion_families": ["beam_stack", "reveal_whiteout", "symmetrical_mirror"],
        "laser_presence": 0.0,
        "realism_priors": {
            "haze_density": 0.72,
            "source_legibility": 0.74,
            "audience_reveal_strength": 0.34,
            "stage_visibility": 0.38,
            "screen_visibility": 0.0,
        },
    },
    "v3_peak_reveal": {
        "segment_id": "v3_peak_reveal",
        "section_type": "peak_reveal",
        "reference_weight": 0.96,
        "exclude_from_training": False,
        "motion_families": ["beam_stack", "reveal_whiteout", "symmetrical_mirror"],
        "laser_presence": 0.0,
        "realism_priors": {
            "haze_density": 0.86,
            "source_legibility": 0.86,
            "audience_reveal_strength": 0.52,
            "stage_visibility": 0.34,
            "screen_visibility": 0.0,
        },
    },
    "v3_horizontal_laser_sustain": {
        "segment_id": "v3_horizontal_laser_sustain",
        "section_type": "laser_sustain",
        "reference_weight": 0.98,
        "exclude_from_training": False,
        "motion_families": ["audience_rake", "horizontal_sheet_plane", "upper_lower_layer_split"],
        "laser_presence": 0.82,
        "realism_priors": {
            "haze_density": 0.78,
            "source_legibility": 0.62,
            "audience_reveal_strength": 0.28,
            "stage_visibility": 0.18,
            "screen_visibility": 0.0,
        },
    },
}

# Filter excluded segments at module load time
_ACTIVE_DATASET: dict[str, dict] = {
    k: v for k, v in _DATASET.items() if not v.get("exclude_from_training", False)
}

# ---------------------------------------------------------------------------
# Section type mapping: engine label → reference section_type strings
# ---------------------------------------------------------------------------

_SECTION_TYPE_MAP: dict[str, list[str]] = {
    "intro":     ["ambient_intro", "deep_ambient_hold"],
    "build":     ["transition", "rebuild_or_secondary_peak", "cooldown_transition"],
    "drop":      [
        "drop_or_peak", "reveal_peak", "peak_reveal", "white_beam_reveal",
        "sustain", "laser_sustain", "rebuild_or_secondary_peak",
    ],
    "breakdown": ["sustain", "dark_transition", "environment_reveal", "return_to_dark", "cooldown_transition"],
    "outro":     ["return_to_dark", "dark_transition", "ambient_intro"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score_segment(seg: dict, section_label: str, energy: float) -> float:
    """
    Score a reference segment for relevance to the given section + energy.

    score = type_match × energy_proximity × reference_weight
    """
    valid_types = _SECTION_TYPE_MAP.get(section_label, [section_label])
    type_match = 1.0 if seg["section_type"] in valid_types else 0.0
    if type_match == 0.0:
        return 0.0

    # Energy proximity: assume reference segments are most relevant at mid-energy (0.7)
    # We use a Gaussian-like decay from 0.7 as reference midpoint.
    # For now: proximity = 1 - |energy - 0.7| (linear, clamped)
    energy_proximity = max(0.0, 1.0 - abs(energy - 0.70))

    return type_match * energy_proximity * seg["reference_weight"]


def _default_realism_priors(section_label: str) -> dict:
    """Fallback realism priors per section when no reference segments match."""
    defaults: dict[str, dict] = {
        "intro": {
            "haze_density": 0.25,
            "source_legibility": 0.40,
            "audience_reveal_strength": 0.10,
            "stage_visibility": 0.25,
            "screen_visibility": 0.00,
        },
        "build": {
            "haze_density": 0.55,
            "source_legibility": 0.50,
            "audience_reveal_strength": 0.10,
            "stage_visibility": 0.25,
            "screen_visibility": 0.10,
        },
        "drop": {
            "haze_density": 0.80,
            "source_legibility": 0.50,
            "audience_reveal_strength": 0.20,
            "stage_visibility": 0.20,
            "screen_visibility": 0.05,
        },
        "breakdown": {
            "haze_density": 0.60,
            "source_legibility": 0.55,
            "audience_reveal_strength": 0.08,
            "stage_visibility": 0.20,
            "screen_visibility": 0.00,
        },
        "outro": {
            "haze_density": 0.30,
            "source_legibility": 0.45,
            "audience_reveal_strength": 0.08,
            "stage_visibility": 0.20,
            "screen_visibility": 0.00,
        },
    }
    return defaults.get(section_label, defaults["drop"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_influential_segments(
    section_label: str,
    energy: float,
    top_k: int = 3,
) -> list[dict]:
    """
    Return top-k reference segments most relevant to this section and energy level.

    Each returned dict is the raw segment dict augmented with a '_score' key.
    """
    scored: list[tuple[float, dict]] = []
    for seg in _ACTIVE_DATASET.values():
        score = _score_segment(seg, section_label, energy)
        if score > 0.0:
            scored.append((score, seg))

    scored.sort(key=lambda x: -x[0])
    result = []
    for score, seg in scored[:top_k]:
        entry = dict(seg)
        entry["_score"] = round(score, 4)
        result.append(entry)
    return result


def get_section_realism_priors(
    section_label: str,
    energy: float,
) -> dict:
    """
    Return a weighted blend of the top-3 matching reference segments' realism priors.

    Falls back to _default_realism_priors if no segments match.
    """
    segments = get_influential_segments(section_label, energy, top_k=3)
    if not segments:
        return _default_realism_priors(section_label)

    prior_keys = [
        "haze_density",
        "source_legibility",
        "audience_reveal_strength",
        "stage_visibility",
        "screen_visibility",
    ]

    total_weight = sum(s["_score"] for s in segments)
    blended: dict[str, float] = {k: 0.0 for k in prior_keys}

    for seg in segments:
        w = seg["_score"] / total_weight
        seg_priors = seg.get("realism_priors", {})
        for k in prior_keys:
            blended[k] += w * seg_priors.get(k, 0.0)

    return {k: round(v, 4) for k, v in blended.items()}


def get_motion_family_bias(
    section_label: str,
    energy: float,
    candidates: list[str],
) -> list[float]:
    """
    Return a list of bias weights (one per candidate) based on how often each
    motion family appears in the top reference segments.

    Base weight is 1.0; each reference occurrence adds a presence_boost
    proportional to the segment's score and reference_weight.
    """
    segments = get_influential_segments(section_label, energy, top_k=5)

    # Count weighted presence per family
    family_boost: dict[str, float] = {}
    for seg in segments:
        seg_score = seg.get("_score", 0.0)
        for family in seg.get("motion_families", []):
            if family not in family_boost:
                family_boost[family] = 0.0
            family_boost[family] += seg_score * seg.get("reference_weight", 1.0)

    # Normalise boost to [0, 1] range
    max_boost = max(family_boost.values()) if family_boost else 1.0
    if max_boost > 0:
        family_boost = {k: v / max_boost for k, v in family_boost.items()}

    # Build weight list for candidates
    weights: list[float] = []
    for candidate in candidates:
        boost = family_boost.get(candidate, 0.0)
        weights.append(1.0 + boost)  # base 1.0 + presence boost

    return weights
