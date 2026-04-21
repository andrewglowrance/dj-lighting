"""
Pydantic v2 models for the Phase 1 audio analysis output (timeline JSON).

These models define the contract between the analysis pipeline and any
downstream consumer (cue engine, frontend, export layer).
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

EmotionLabel = Literal["euphoric", "uplifting", "dark", "melancholic", "intense", "chill"]
TemperatureLabel = Literal["warm", "cool", "neutral"]


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


class MoodAnalysis(BaseModel):
    """
    Musical key and emotional profile derived from audio chromagram analysis.
    Consumed by the frontend visualizer to drive color temperature and emotion-
    responsive wash colors.
    """
    key_note:    str   = Field(..., description="Tonic note, e.g. 'A', 'F#'")
    mode:        Literal["major", "minor"]
    key_label:   str   = Field(..., description="Human-readable key, e.g. 'A minor'")
    key_index:   int   = Field(..., ge=0, le=11, description="Chromatic pitch class 0=C…11=B")
    temperature: TemperatureLabel = Field(..., description="Color temperature hint for visualizer")
    valence:     float = Field(..., ge=0.0, le=1.0, description="Emotional positivity [0=sad, 1=happy]")
    energy:      float = Field(..., ge=0.0, le=1.0, description="Perceived energy level [0=calm, 1=intense]")
    emotion:     EmotionLabel
    color_bias:  str   = Field(..., description="Recommended base wash palette key from rules.COLORS")


class BeatNote(BaseModel):
    """
    Per-beat musical note analysis for note-responsive wash light coloring.

    dominant_note_index  → chromatic pitch class 0–11 (0 = C, 1 = C#, … 11 = B)
    dominant_note        → human-readable note name  ("C", "C#", "D", … "B")
    chroma_intensity     → strength of that pitch relative to the chromagram peak [0-1]
    onset_strength       → normalized onset salience at this beat [0-1]
    rms_energy           → normalized RMS amplitude at this beat [0-1]
    tone_duration_beats  → estimated number of consecutive beats sharing the same note
    key_relative_degree  → scale degree relative to song's tonic (0=tonic … 11)
    smoothed_hue         → EMA-smoothed HSL hue [0, 1] — use this for wash color
                           (stays within the key's color family; drifts gradually)
    tonal_brightness     → harmonic stability × chroma clarity [0, 1]
                           (tonic/5th = bright; tritone/min2 = dim)
    """
    beat_index:          int   = Field(..., ge=0)
    dominant_note_index: int   = Field(..., ge=0, le=11,
                                       description="Pitch class 0=C…11=B")
    dominant_note:       str   = Field(..., description="Note name e.g. 'C', 'F#'")
    chroma_intensity:    float = Field(..., ge=0.0, le=1.0)
    onset_strength:      float = Field(..., ge=0.0, le=1.0)
    rms_energy:          float = Field(..., ge=0.0, le=1.0)
    tone_duration_beats: float = Field(..., ge=0.0)
    key_relative_degree: int   = Field(0, ge=0, le=11,
                                       description="Scale degree vs. key tonic")
    smoothed_hue:        float = Field(0.0, ge=0.0, le=1.0,
                                       description="EMA-smoothed HSL hue for renderer [0, 1]")
    tonal_brightness:    float = Field(0.5, ge=0.0, le=1.0,
                                       description="Harmonic stability × chroma clarity")


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

    metadata:        TrackMetadata
    bpm:             BPMInfo
    beats:           list[Beat]
    bars:            list[Bar]
    sections:        list[Section]
    drop_candidates: list[DropCandidate]
    mood:            MoodAnalysis
    beat_notes:      list[BeatNote] = Field(
        default_factory=list,
        description="Per-beat dominant note, energy, and tone-length data for note-responsive lighting",
    )
