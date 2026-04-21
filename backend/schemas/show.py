"""
schemas/show.py

Top-level data models for the show persistence and revision system.

Show          – the complete in-memory record for one generated show.
VisualizationPlan – what the frontend receives to drive playback.
ShowResponse  – API response wrapper (excludes heavy raw_cues from wire).
RevisionRequest / RevisionResult – revision-flow request/response pair.
RevisionMeta  – audit record of a single revision.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from backend.schemas.timeline import TimelineSchema, MoodAnalysis
from backend.schemas.cues import CueOutputSchema
from backend.schemas.style import EnvironmentRenderingProfile, StyleProfile, StylePatch


# ---------------------------------------------------------------------------
# VisualizationPlan — what the frontend renderer consumes
# ---------------------------------------------------------------------------

class VisualizationPlan(BaseModel):
    """
    Self-contained payload for the frontend lighting visualizer.
    Combines styled cues, stage layout, style metadata, and mood info.
    """
    rig_id:              str
    bpm:                 float
    total_duration_sec:  float
    cues:                CueOutputSchema
    layout:              dict   = Field(..., description="Stage layout from stage_layout.get_layout()")
    style_profile:       StyleProfile
    mood:                MoodAnalysis
    environment_profile: EnvironmentRenderingProfile = Field(
        default_factory=EnvironmentRenderingProfile,
        description="Venue geometry and material parameters for the Three.js renderer",
    )


# ---------------------------------------------------------------------------
# Show — full in-memory record
# ---------------------------------------------------------------------------

class RevisionMeta(BaseModel):
    revision_number: int
    prompt:          str
    patch:           StylePatch
    notes:           list[str]  = Field(default_factory=list)


class Show(BaseModel):
    """
    Complete record for one generated show, stored in the in-memory ShowStore.

    raw_cues       – cues produced by the cue engine before any style is applied.
                     Preserved so every revision re-applies from the same base.
    styled_cues    – cues after the style engine ran (what the frontend renders).
    style_profile  – current active style profile.
    original_style – the profile from initial generation (never mutated).
    """
    show_id:               str
    created_at:            str   # ISO-8601 UTC
    rig_id:                str
    timeline:              TimelineSchema
    raw_cues:              CueOutputSchema
    styled_cues:           CueOutputSchema
    style_profile:         StyleProfile
    original_style:        StyleProfile
    viz_plan:              VisualizationPlan
    creation_prompt:       str | None        = None
    revision_history:      list[RevisionMeta] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class ShowSummary(BaseModel):
    """Lightweight listing entry for /api/shows."""
    show_id:        str
    rig_id:         str
    created_at:     str
    creation_prompt: str | None
    revision_count: int
    bpm:            float
    duration_sec:   float
    emotion:        str
    key_label:      str


class ShowResponse(BaseModel):
    """
    API response for POST /api/shows and GET /api/shows/{show_id}.
    Returns the visualization plan and lightweight metadata; raw_cues are
    intentionally omitted from the wire to keep payload size reasonable.
    """
    show_id:          str
    created_at:       str
    rig_id:           str
    creation_prompt:  str | None
    revision_count:   int
    style_profile:    StyleProfile
    original_style:   StyleProfile
    viz_plan:         VisualizationPlan
    revision_history: list[RevisionMeta]


class RevisionRequest(BaseModel):
    """Body for POST /api/shows/{show_id}/revise."""
    revision_prompt: str = Field(..., min_length=3,
                                 description="Natural-language description of what to change")


class RevisionResult(BaseModel):
    """Response for POST /api/shows/{show_id}/revise."""
    show_id:               str
    revision_number:       int
    revision_prompt:       str
    patch:                 StylePatch
    updated_style_profile: StyleProfile
    updated_viz_plan:      VisualizationPlan
    notes:                 list[str]
