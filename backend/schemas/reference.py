"""
schemas/reference.py

Pydantic v2 models for the reference dataset (annotated DJ video segments).
Used by reference_dataset.py and the diversity/motion vocabulary layer.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class LaserProfile(BaseModel):
    presence: float = Field(0.0, ge=0, le=1)
    pattern_types: list[str] = []
    density: float = Field(0.0, ge=0, le=1)
    open_angle: str = "medium"
    movement_transition_speed: str = "medium"
    beam_thickness: str = "thin"


class LightingProfile(BaseModel):
    wash_level: float = Field(0.0, ge=0, le=1)
    beam_level: float = Field(0.0, ge=0, le=1)
    strobe_level: float = Field(0.0, ge=0, le=1)
    brightness_profile: str = "medium"
    bloom_level: float = Field(0.0, ge=0, le=1)


class SpatialUsage(BaseModel):
    upper_truss: float = Field(0.0, ge=0, le=1)
    mid_stage: float = Field(0.0, ge=0, le=1)
    floor_emitters: float = Field(0.0, ge=0, le=1)
    side_emitters: float = Field(0.0, ge=0, le=1)


class RealismPriors(BaseModel):
    haze_density: float = Field(0.5, ge=0, le=1)
    source_legibility: float = Field(0.5, ge=0, le=1)
    audience_reveal_strength: float = Field(0.1, ge=0, le=1)
    stage_visibility: float = Field(0.2, ge=0, le=1)
    screen_visibility: float = Field(0.0, ge=0, le=1)


class ReferenceSegment(BaseModel):
    segment_id: str
    section_type: str
    reference_weight: float = Field(0.0, ge=0, le=1)
    exclude_from_training: bool = False
    motion_families: list[str] = []
    laser_profile: Optional[LaserProfile] = None
    lighting_profile: Optional[LightingProfile] = None
    spatial_usage: Optional[SpatialUsage] = None
    realism_priors: Optional[RealismPriors] = None
    anti_repetition_guidance: list[str] = []
