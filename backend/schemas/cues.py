"""
Pydantic v2 models for the deterministic lighting cue output.

Each Cue is self-contained: it carries enough information for a rig-template
mapper to translate it into DMX channel values without re-reading the timeline.

Design notes:
- target_groups are abstract fixture group names (e.g. "wash_all", "moving_heads").
  Rig-template mapping (Phase 2) resolves these to concrete fixture/channel assignments.
- parameters is intentionally untyped (dict) so new cue_types can be added without
  schema changes. The cue engine enforces parameter shapes internally via rules.py.
"""

from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


CueType = Literal[
    "wash",           # Set fixtures to a sustained color/intensity
    "pulse",          # Single-beat bump at specified intensity
    "strobe_hit",     # Short strobe burst
    "color_shift",    # Snap or transition to a new color
    "movement_enable",# Enable/configure moving-head motion
    "fade_out",       # Ramp intensity down to a target level
    # --- Laser cue types ---
    "laser_static",   # Hold a fixed fan or beam at set angle and color
    "laser_scan",     # Single beam or narrow fan sweeping left↔right
    "laser_chase",    # Multiple beams firing in rapid alternating sequence
    "laser_off",      # Cut all laser output immediately
]

# All valid abstract fixture group names.
# Phase 2 rig templates map these to physical fixtures.
TargetGroup = Literal[
    "wash_all",
    "spots",
    "moving_heads",
    "strobe",
    "back_wash",
    "lasers",         # RGB or single-colour laser fixtures
]


class Cue(BaseModel):
    id: str = Field(..., description="Unique cue identifier, e.g. 'cue_0042'")
    time: float = Field(..., ge=0, description="Cue fire time in seconds from track start")
    duration: float = Field(..., gt=0, description="Cue hold/fade duration in seconds")
    cue_type: CueType
    section: str = Field(..., description="Source section label (for debugging/inspection)")
    trigger: str = Field(
        ...,
        description="Rule trigger that produced this cue (e.g. 'beat', 'bar_4_beat_1', 'section_start')",
    )
    target_groups: list[TargetGroup]
    parameters: dict[str, Any] = Field(
        ...,
        description=(
            "Cue-type-specific parameters. "
            "Keys vary by cue_type; see rules.py for the parameter spec per type."
        ),
    )


class CueOutputSchema(BaseModel):
    """
    Complete cue timeline for one track, produced by the cue engine.
    Cues are ordered by time ascending.
    """

    bpm: float = Field(..., gt=0)
    total_duration_sec: float = Field(..., ge=0)
    total_cues: int = Field(..., ge=0)
    cues: list[Cue]

    # Rendering hints consumed by the frontend visualizer
    brightness_multiplier: float = Field(
        1.5,
        ge=0.1,
        le=5.0,
        description=(
            "Global luminosity scale applied by the renderer on top of per-cue "
            "intensity values. 1.5 = 50%% brighter than the nominal rule values."
        ),
    )
    audience_fill: bool = Field(
        True,
        description=(
            "When True the renderer should project wash/beam fixtures toward the "
            "audience area in addition to the stage, extending light coverage "
            "into the crowd."
        ),
    )
    section_choreography: list[dict] = Field(
        default_factory=list,
        description=(
            "Per-section choreography log: which motion family was selected, "
            "why, and what realism priors apply. Useful for debugging and "
            "for the frontend to adjust rendering per section."
        ),
    )

    # Beat / bar timing arrays for frame-precise frontend sync
    # The frontend should use requestAnimationFrame and compare audio.currentTime
    # against these sorted arrays instead of computing timing from BPM.
    beat_times: list[float] = Field(
        default_factory=list,
        description=(
            "Sorted list of every beat onset time in seconds from track start. "
            "Use with requestAnimationFrame to trigger beat-locked visual effects "
            "with sub-frame precision — do NOT derive from BPM arithmetic."
        ),
    )
    bar_times: list[float] = Field(
        default_factory=list,
        description=(
            "Sorted list of every bar downbeat time (beat 0 of each bar) in seconds. "
            "Use for bar-level visual transitions (phrase changes, color shifts, etc.)."
        ),
    )

    # Renderer safety flag — tells the frontend never to project laser patterns
    # onto the floor plane regardless of pattern type.
    no_floor_projection: bool = Field(
        True,
        description=(
            "When True, the renderer must not project any laser beam onto the "
            "floor/ground plane. All laser cues use aerial projection (beams travel "
            "through haze above stage level). Overrides any pattern-type inference."
        ),
    )

    # Laser coordination contract (applies to every laser cue in this output):
    #
    # Every laser cue's parameters now include:
    #   synchronized: bool     — True means ALL fixtures must pan/tilt together as one
    #                            unit; no fixture should move independently.
    #   beat_sync: str         — "beat" | "downbeat" | "bar"
    #                            When to snap beam positions: every beat, downbeat only,
    #                            or bar downbeat only. Use beat_times / bar_times arrays.
    #   sweep_direction: str   — "left_to_right" | "right_to_left" | "alternating" |
    #                            "center_out"
    #                            Direction for the current phrase's sweep cycle.
    #                            Reverse on each beat_sync event for alternating.
    #
    # Laser_off cues mean ZERO visible output — no dim glow, no idle beam.
    laser_sync_contract: str = Field(
        "synchronized_aerial_beat_locked",
        description=(
            "Renderer contract string. Value is always 'synchronized_aerial_beat_locked': "
            "all laser fixtures sweep together (synchronized=True), project into haze "
            "only (projection=aerial), snap/reverse direction on each beat_sync event "
            "using the beat_times array. laser_off means full blackout of all laser output."
        ),
    )
