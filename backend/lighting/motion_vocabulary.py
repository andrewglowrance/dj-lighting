"""
lighting/motion_vocabulary.py

Named motion families with concrete cue parameters, spatial zones, energy
ranges, section affinities, and realism hints.

Each MotionDescriptor captures:
  - section_affinity: which section labels this family works best in
  - energy_range: (min, max) normalised energy float where this family applies
  - primary_zones: spatial zones activated by this family
  - laser_affinity: 0-1 how laser-heavy this family is (0 = no laser)
  - speed_profile: qualitative speed label
  - cooldown_sections: how many sections must pass before reuse
  - laser_params: concrete cue_type + params for the laser layer
  - movement_params: speed + pattern for the movement_enable cue
  - realism_hints: frontend rendering guidance
  - description: human-readable summary
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MotionDescriptor:
    section_affinity: list[str]
    energy_range: tuple[float, float]
    primary_zones: list[str]
    laser_affinity: float
    speed_profile: str
    cooldown_sections: int
    laser_params: dict
    movement_params: dict
    realism_hints: dict
    description: str


# ---------------------------------------------------------------------------
# Motion Vocabulary — 24 named families
# ---------------------------------------------------------------------------

MOTION_VOCABULARY: dict[str, MotionDescriptor] = {

    # 1. fan_open
    "fan_open": MotionDescriptor(
        section_affinity=["build", "drop"],
        energy_range=(0.45, 1.0),
        primary_zones=["upper_truss", "mid_stage"],
        laser_affinity=0.85,
        speed_profile="medium",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_green",
            "pattern": "fan",
            "fan_count": 5,
            "spread_deg": 70,
            "intensity": 0.80,
        },
        movement_params={"speed": 0.55, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.1, "bloom": 0.4},
        description="Laser fans spread outward — ideal for builds and drop entrances.",
    ),

    # 2. fan_close
    "fan_close": MotionDescriptor(
        section_affinity=["breakdown", "outro"],
        energy_range=(0.2, 0.6),
        primary_zones=["mid_stage"],
        laser_affinity=0.70,
        speed_profile="slow",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_blue",
            "pattern": "fan",
            "fan_count": 3,
            "spread_deg": 30,
            "intensity": 0.50,
        },
        movement_params={"speed": 0.25, "pattern": "slow_drift"},
        realism_hints={"haze_boost": 0.05, "bloom": 0.2},
        description="Laser fans contract inward — breakdown and transition calm-down.",
    ),

    # 3. crosshatch
    "crosshatch": MotionDescriptor(
        section_affinity=["drop"],
        energy_range=(0.70, 1.0),
        primary_zones=["upper_truss", "mid_stage", "side_emitters"],
        laser_affinity=0.95,
        speed_profile="fast",
        cooldown_sections=4,
        laser_params={
            "cue_type": "laser_chase",
            "colors": ["laser_green", "laser_red", "laser_cyan", "laser_white"],
            "beam_count": 8,
            "step_beats": 0.25,
            "intensity": 1.0,
        },
        movement_params={"speed": 1.0, "pattern": "fast_pan"},
        realism_hints={"haze_boost": 0.2, "bloom": 0.6},
        description="Dense crossing laser lattice — maximum energy drop moment.",
    ),

    # 4. center_converge
    "center_converge": MotionDescriptor(
        section_affinity=["drop", "breakdown"],
        energy_range=(0.40, 0.85),
        primary_zones=["upper_truss", "mid_stage"],
        laser_affinity=0.75,
        speed_profile="slow_to_medium",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_cyan",
            "pattern": "x_cross",
            "fan_count": 4,
            "spread_deg": 45,
            "intensity": 0.70,
        },
        movement_params={"speed": 0.45, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.1, "bloom": 0.35},
        description="Beams converge to center — sustain and breakdown focal point.",
    ),

    # 5. alternating_side_sweep
    "alternating_side_sweep": MotionDescriptor(
        section_affinity=["build", "drop"],
        energy_range=(0.5, 1.0),
        primary_zones=["side_emitters", "mid_stage"],
        laser_affinity=0.80,
        speed_profile="medium",
        cooldown_sections=2,
        laser_params={
            "cue_type": "laser_scan",
            "color": "laser_green",
            "speed": 0.70,
            "fan_count": 2,
            "spread_deg": 50,
            "intensity": 0.85,
        },
        movement_params={"speed": 0.65, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.1, "bloom": 0.3},
        description="L/R alternating laser sweep — build energy and drop transitions.",
    ),

    # 6. audience_rake
    "audience_rake": MotionDescriptor(
        section_affinity=["drop"],
        energy_range=(0.55, 1.0),
        primary_zones=["floor_emitters", "mid_stage"],
        laser_affinity=0.90,
        speed_profile="medium",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_scan",
            "color": "laser_green",
            "speed": 0.50,
            "fan_count": 3,
            "spread_deg": 70,
            "intensity": 0.90,
        },
        movement_params={"speed": 0.55, "pattern": "sweep"},
        realism_hints={"audience_reveal": 0.3, "haze_boost": 0.15},
        description="Horizontal laser planes sweep across the crowd — peak crowd moments.",
    ),

    # 7. ceiling_rake
    "ceiling_rake": MotionDescriptor(
        section_affinity=["build", "drop"],
        energy_range=(0.55, 1.0),
        primary_zones=["upper_truss"],
        laser_affinity=0.80,
        speed_profile="medium",
        cooldown_sections=2,
        laser_params={
            "cue_type": "laser_scan",
            "color": "laser_white",
            "speed": 0.60,
            "fan_count": 2,
            "spread_deg": 40,
            "intensity": 0.80,
        },
        movement_params={"speed": 0.60, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.15, "bloom": 0.4},
        description="Beams sweep ceiling — builds volume and vertical drama.",
    ),

    # 8. burst_outward
    "burst_outward": MotionDescriptor(
        section_affinity=["drop"],
        energy_range=(0.75, 1.0),
        primary_zones=["upper_truss", "mid_stage", "side_emitters", "floor_emitters"],
        laser_affinity=0.90,
        speed_profile="burst",
        cooldown_sections=4,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_white",
            "pattern": "fan",
            "fan_count": 6,
            "spread_deg": 90,
            "intensity": 1.0,
        },
        movement_params={"speed": 1.0, "pattern": "fast_pan"},
        realism_hints={"haze_boost": 0.25, "bloom": 0.7},
        description="All sources explode outward — the biggest drop impact moment.",
    ),

    # 9. burst_inward
    "burst_inward": MotionDescriptor(
        section_affinity=["build", "drop"],
        energy_range=(0.65, 1.0),
        primary_zones=["upper_truss", "mid_stage"],
        laser_affinity=0.85,
        speed_profile="burst",
        cooldown_sections=4,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_red",
            "pattern": "x_cross",
            "fan_count": 5,
            "spread_deg": 60,
            "intensity": 0.95,
        },
        movement_params={"speed": 0.90, "pattern": "fast_pan"},
        realism_hints={"haze_boost": 0.2, "bloom": 0.55},
        description="Sources collapse inward — anticipation burst before a transition.",
    ),

    # 10. hold_then_snap
    "hold_then_snap": MotionDescriptor(
        section_affinity=["drop", "breakdown", "intro"],
        energy_range=(0.3, 0.75),
        primary_zones=["upper_truss", "mid_stage"],
        laser_affinity=0.60,
        speed_profile="slow",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_blue",
            "pattern": "single",
            "fan_count": 2,
            "spread_deg": 20,
            "intensity": 0.55,
        },
        movement_params={"speed": 0.20, "pattern": "slow_drift"},
        realism_hints={"haze_boost": 0.05, "bloom": 0.2},
        description="Long static hold followed by a snap — tension and release.",
    ),

    # 11. upper_lower_layer_split
    "upper_lower_layer_split": MotionDescriptor(
        section_affinity=["drop", "build"],
        energy_range=(0.55, 1.0),
        primary_zones=["upper_truss", "floor_emitters"],
        laser_affinity=0.75,
        speed_profile="medium",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_scan",
            "color": "laser_cyan",
            "speed": 0.55,
            "fan_count": 3,
            "spread_deg": 50,
            "intensity": 0.80,
        },
        movement_params={"speed": 0.60, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.12, "bloom": 0.35},
        description="Upper truss and floor emitters on different planes — layered depth.",
    ),

    # 12. tunnel
    "tunnel": MotionDescriptor(
        section_affinity=["drop"],
        energy_range=(0.6, 1.0),
        primary_zones=["upper_truss", "side_emitters"],
        laser_affinity=0.88,
        speed_profile="medium",
        cooldown_sections=4,
        laser_params={
            "cue_type": "laser_chase",
            "colors": ["laser_white", "laser_cyan", "laser_blue"],
            "beam_count": 6,
            "step_beats": 0.50,
            "intensity": 0.95,
        },
        movement_params={"speed": 0.70, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.2, "bloom": 0.5},
        description="Circular tunnel effect — immersive peak moment.",
    ),

    # 13. sheet_plane
    "sheet_plane": MotionDescriptor(
        section_affinity=["breakdown", "drop"],
        energy_range=(0.35, 0.75),
        primary_zones=["mid_stage", "floor_emitters"],
        laser_affinity=0.70,
        speed_profile="slow",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_scan",
            "color": "laser_green",
            "speed": 0.30,
            "fan_count": 1,
            "spread_deg": 60,
            "intensity": 0.60,
        },
        movement_params={"speed": 0.30, "pattern": "slow_drift"},
        realism_hints={"haze_boost": 0.1, "bloom": 0.25},
        description="Thin horizontal laser plane sweeping crowd — atmospheric sustain.",
    ),

    # 14. horizontal_sheet_plane
    "horizontal_sheet_plane": MotionDescriptor(
        section_affinity=["drop", "breakdown"],
        energy_range=(0.4, 0.8),
        primary_zones=["mid_stage", "floor_emitters"],
        laser_affinity=0.82,
        speed_profile="medium",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_scan",
            "color": "laser_blue",
            "speed": 0.45,
            "fan_count": 2,
            "spread_deg": 90,
            "intensity": 0.75,
        },
        movement_params={"speed": 0.45, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.15, "bloom": 0.3, "audience_reveal": 0.25},
        description="Wide horizontal planes raking crowd — ref: video 3 blue laser.",
    ),

    # 15. staggered_chase
    "staggered_chase": MotionDescriptor(
        section_affinity=["drop", "build"],
        energy_range=(0.6, 1.0),
        primary_zones=["upper_truss", "side_emitters"],
        laser_affinity=0.88,
        speed_profile="fast",
        cooldown_sections=2,
        laser_params={
            "cue_type": "laser_chase",
            "colors": ["laser_red", "laser_green", "laser_blue"],
            "beam_count": 5,
            "step_beats": 0.25,
            "intensity": 0.90,
        },
        movement_params={"speed": 0.85, "pattern": "fast_pan"},
        realism_hints={"haze_boost": 0.18, "bloom": 0.5},
        description="Offset stagger chase — rapid-fire build and drop momentum.",
    ),

    # 16. reveal_whiteout
    "reveal_whiteout": MotionDescriptor(
        section_affinity=["drop"],
        energy_range=(0.75, 1.0),
        primary_zones=["upper_truss", "mid_stage"],
        laser_affinity=0.20,
        speed_profile="burst",
        cooldown_sections=6,
        laser_params={
            "cue_type": "",  # lasers step back — beams primary
        },
        movement_params={"speed": 0.80, "pattern": "fast_pan"},
        realism_hints={"haze_boost": 0.3, "bloom": 0.8, "source_legibility": 0.7},
        description="White beam architecture — rare maximum-impact reveal moment (cooldown 6).",
    ),

    # 17. beam_stack
    "beam_stack": MotionDescriptor(
        section_affinity=["drop", "build"],
        energy_range=(0.5, 1.0),
        primary_zones=["upper_truss"],
        laser_affinity=0.30,
        speed_profile="medium",
        cooldown_sections=3,
        laser_params={
            "cue_type": "",  # beams primary, no laser
        },
        movement_params={"speed": 0.55, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.2, "bloom": 0.5, "source_legibility": 0.6},
        description="Multiple overhead beam shafts — beams-primary, low laser affinity.",
    ),

    # 18. radial_wash_expand
    "radial_wash_expand": MotionDescriptor(
        section_affinity=["drop", "build"],
        energy_range=(0.55, 1.0),
        primary_zones=["upper_truss", "mid_stage", "floor_emitters"],
        laser_affinity=0.50,
        speed_profile="medium",
        cooldown_sections=2,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_white",
            "pattern": "fan",
            "fan_count": 4,
            "spread_deg": 60,
            "intensity": 0.75,
        },
        movement_params={"speed": 0.60, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.15, "bloom": 0.45},
        description="Wash expands radially from center — drop and build transition.",
    ),

    # 19. laser_burst_cluster
    "laser_burst_cluster": MotionDescriptor(
        section_affinity=["drop"],
        energy_range=(0.8, 1.0),
        primary_zones=["upper_truss", "mid_stage", "side_emitters"],
        laser_affinity=0.98,
        speed_profile="burst",
        cooldown_sections=4,
        laser_params={
            "cue_type": "laser_chase",
            "colors": ["laser_green", "laser_red", "laser_white", "laser_cyan", "laser_yellow"],
            "beam_count": 8,
            "step_beats": 0.125,
            "intensity": 1.0,
        },
        movement_params={"speed": 1.0, "pattern": "fast_pan"},
        realism_hints={"haze_boost": 0.25, "bloom": 0.75},
        description="Max-density rapid laser cluster — the absolute peak laser moment.",
    ),

    # 20. slow_drift
    "slow_drift": MotionDescriptor(
        section_affinity=["intro", "breakdown", "outro"],
        energy_range=(0.0, 0.45),
        primary_zones=["upper_truss", "mid_stage"],
        laser_affinity=0.25,
        speed_profile="slow",
        cooldown_sections=1,
        laser_params={
            "cue_type": "laser_scan",
            "color": "laser_blue",
            "speed": 0.15,
            "fan_count": 1,
            "spread_deg": 20,
            "intensity": 0.25,
        },
        movement_params={"speed": 0.18, "pattern": "slow_drift"},
        realism_hints={"haze_boost": 0.0, "bloom": 0.1},
        description="Gentle ambient drift — intro, outro, and low-energy breakdown.",
    ),

    # 21. static_hold
    "static_hold": MotionDescriptor(
        section_affinity=["intro"],
        energy_range=(0.0, 0.30),
        primary_zones=["upper_truss"],
        laser_affinity=0.0,
        speed_profile="static",
        cooldown_sections=1,
        laser_params={
            "cue_type": "",  # no laser
        },
        movement_params={"speed": 0.05, "pattern": "slow_drift"},
        realism_hints={"haze_boost": 0.0, "bloom": 0.05},
        description="Near-zero movement static hold — deep ambient intro moments.",
    ),

    # 22. minimal_source_reveal
    "minimal_source_reveal": MotionDescriptor(
        section_affinity=["intro", "outro"],
        energy_range=(0.0, 0.40),
        primary_zones=["upper_truss", "mid_stage"],
        laser_affinity=0.05,
        speed_profile="slow",
        cooldown_sections=2,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_blue",
            "pattern": "single",
            "fan_count": 1,
            "spread_deg": 5,
            "intensity": 0.15,
        },
        movement_params={"speed": 0.10, "pattern": "slow_drift"},
        realism_hints={"source_legibility": 0.4, "haze_boost": 0.0},
        description="Individual fixture sources visible in darkness — deep atmosphere.",
    ),

    # 23. fade_to_black
    "fade_to_black": MotionDescriptor(
        section_affinity=["outro", "breakdown"],
        energy_range=(0.0, 0.25),
        primary_zones=["upper_truss"],
        laser_affinity=0.0,
        speed_profile="slow",
        cooldown_sections=3,
        laser_params={
            "cue_type": "",  # no laser
        },
        movement_params={"speed": 0.05, "pattern": "slow_drift"},
        realism_hints={"haze_boost": 0.0, "bloom": 0.0},
        description="Progressive dark fade — outro and end-of-breakdown darkness.",
    ),

    # 24. symmetrical_mirror
    "symmetrical_mirror": MotionDescriptor(
        section_affinity=["drop", "build"],
        energy_range=(0.6, 1.0),
        primary_zones=["upper_truss", "side_emitters"],
        laser_affinity=0.78,
        speed_profile="medium",
        cooldown_sections=3,
        laser_params={
            "cue_type": "laser_static",
            "color": "laser_white",
            "pattern": "fan",
            "fan_count": 6,
            "spread_deg": 80,
            "intensity": 0.90,
        },
        movement_params={"speed": 0.65, "pattern": "sweep"},
        realism_hints={"haze_boost": 0.15, "bloom": 0.45, "source_legibility": 0.5},
        description="L/R symmetric beam architecture — drop, peak, and reveal moments.",
    ),
}


# ---------------------------------------------------------------------------
# Section-affinity map
# ---------------------------------------------------------------------------

_AFFINITY_MAP: dict[str, list[str]] = {
    "intro":     ["intro"],
    "build":     ["build"],
    "drop":      ["drop"],
    "breakdown": ["breakdown"],
    "outro":     ["outro"],
}


def get_motions_for_section(
    section_label: str,
    energy: float,
    top_k: int = 6,
) -> list[str]:
    """
    Return the top-k motion family names best suited to this section and energy.

    Scoring:
      - +2.0 if section_label is in the family's section_affinity
      - +1.0 if energy is within the family's energy_range
      - +0.5 if energy is within 0.15 of the energy_range boundary (near-match)
    """
    affinity_labels = _AFFINITY_MAP.get(section_label, [section_label])

    scored: list[tuple[float, str]] = []
    for name, desc in MOTION_VOCABULARY.items():
        score = 0.0

        # Section affinity score
        if any(a in desc.section_affinity for a in affinity_labels):
            score += 2.0

        # Energy range score
        e_min, e_max = desc.energy_range
        if e_min <= energy <= e_max:
            score += 1.0
        elif energy < e_min and (e_min - energy) <= 0.15:
            score += 0.5
        elif energy > e_max and (energy - e_max) <= 0.15:
            score += 0.5

        scored.append((score, name))

    # Sort descending by score, then alphabetically for stability
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [name for _, name in scored[:top_k]]
