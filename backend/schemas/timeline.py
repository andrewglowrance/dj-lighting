"""
Pydantic v2 models for the Phase 1 audio analysis output (timeline JSON).

These models define the contract between the analysis pipeline and any
downstream consumer (cue engine, frontend, export layer).
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class TrackMetadata(BaseModel):
    filename: str
    duration_sec: float = Field(..., ge=0)
    sample_rate: int = Field(..., gt=0)
    analyzed_at: str  # ISO-8601 UTC string


class BPMInfo(BaseModel):
    bpm: float = Field(..., gt=0, description="Estimated tempo in beats per minute")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Tempo confidence [0, 1]")


class Beat(BaseModel):
    index: int = Field(..., ge=0, description="Global beat index (0-based)")
    time: float = Field(..., ge=0, description="Beat onset time in seconds")
    bar_index: int = Field(..., ge=0, description="Parent bar index")
    beat_in_bar: int = Field(..., ge=0, le=3, description="Position within bar [0-3] for 4/4")


class Bar(BaseModel):
    index: int = Field(..., ge=0)
    time: float = Field(..., ge=0, description="Time of beat 1 of this bar, in seconds")
    duration: float = Field(..., gt=0, description="Bar duration in seconds")
    beat_indices: list[int] = Field(
        ..., description="Indices into the top-level beats array"
    )


SectionLabel = Literal["intro", "build", "drop", "breakdown", "outro"]


class Section(BaseModel):
    label: SectionLabel
    start: float = Field(..., ge=0, description="Section start time in seconds")
    end: float = Field(..., ge=0, description="Section end time in seconds")
    bar_start: int = Field(..., ge=0, description="Index of first bar in section")
    bar_end: int = Field(..., ge=0, description="Index of last bar in section (exclusive)")
    energy_mean: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized mean RMS energy [0, 1]"
    )
    energy_peak: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized peak RMS energy [0, 1]"
    )


DropType = Literal["main_drop", "re_drop", "build_peak"]


class DropCandidate(BaseModel):
    time: float = Field(..., ge=0, description="Drop onset time in seconds")
    bar_index: int = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    type: DropType
    reasons: list[str] = Field(
        ..., description="Human-readable list of scoring factors"
    )
    energy_delta: float = Field(
        ..., description="RMS energy increase at drop boundary (raw, un-normalized)"
    )


# ---------------------------------------------------------------------------
# Top-level schema
# ---------------------------------------------------------------------------

class TimelineSchema(BaseModel):
    """
    Complete analysis output for a single audio file.
    Returned by POST /analyze-track and consumed by the cue engine.
    """

    metadata: TrackMetadata
    bpm: BPMInfo
    beats: list[Beat]
    bars: list[Bar]
    sections: list[Section]
    drop_candidates: list[DropCandidate]
