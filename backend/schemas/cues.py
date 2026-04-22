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
