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

    # ── Renderer directives (read these before building the Three.js scene) ──
    # Pre-computed per-fixture animation spec. The frontend must use ONLY these
    # values to drive laser beam positions — do NOT re-derive from fixture aim vectors.
    laser_animation_preset: dict = Field(
        default_factory=dict,
        description=(
            "Complete, unambiguous laser animation specification. "
            "Contains one entry per laser fixture with origin, aim_center, "
            "pan_range_deg (inverted for right units), tilt_range_deg, "
            "phase_offset_deg, and beam_length. "
            "The frontend interpolates between range[0] and range[1] using "
            "sin(t * freq * 2π + phase_offset_rad) mapped to [0,1]. "
            "This is the authoritative source — renderer_directives and fixture "
            "layout aim vectors are secondary."
        ),
    )

    # ── Pre-computed laser beam endpoints (authoritative — use these, not preset math) ──
    #
    # For EVERY beat in the track, this array contains the exact world-space start
    # and end coordinates for each laser beam.  The frontend needs zero rotation
    # math: just find the current beat index, lerp between adjacent keyframes, and
    # update the THREE.Line geometry directly.
    #
    # Format per entry:
    #   time           float  — beat onset time in seconds
    #   beat_index     int    — absolute beat index in the track
    #   is_bar_downbeat bool  — True on beat 0 of each bar (burst frames)
    #   beams          list   — one entry per active laser fixture:
    #     id           str    — fixture id (matches layout fixture id)
    #     sx,sy,sz     float  — beam start (fixture origin, world-space metres)
    #     ex,ey,ez     float  — beam end (world-space metres, pre-computed)
    #
    # Sweep pattern across beats:
    #   bar downbeat   → beams burst to maximum spread (V-shape, beams diverge)
    #   beat alternates → LEFT and RIGHT endpoints swap every beat, creating X↔V motion
    #   LEFT beam      → endpoint swings left↔right across beats
    #   RIGHT beam     → endpoint mirrors LEFT (opposite direction), guaranteed symmetric
    laser_keyframes: list[dict] = Field(
        default_factory=list,
        description=(
            "Pre-computed per-beat laser beam endpoints in world-space metres. "
            "Frontend: find current beat index from beat_times, lerp between "
            "laser_keyframes[i].beams and laser_keyframes[i+1].beams. "
            "No rotation math needed — just lerp sx/sy/sz → ex/ey/ez."
        ),
    )

    renderer_directives: dict = Field(
        default_factory=lambda: {
            # ── LIGHTING MODEL ────────────────────────────────────────────────
            "scene_lighting": "fixture_only",
            # No THREE.AmbientLight, HemisphereLight, or DirectionalLight.
            # Illumination comes exclusively from per-cue fixture objects.

            # ── FLOOR ─────────────────────────────────────────────────────────
            "floor_material": "subtle_standard",
            # Use MeshStandardMaterial({
            #   color: 0x111111,   // very dark grey — not pure black
            #   roughness: 0.96,
            #   metalness: 0.04,
            #   envMapIntensity: 0,
            # })
            # This gives the floor a barely-visible surface that shows beam
            # grazing without creating bright circular pools.
            "floor_reflectivity": 0.06,
            # Keep at this value — do not raise above 0.10 or floor pools return.
            "floor_receives_shadows": False,
            "wash_floor_pool": False,
            # No circular spot / pool rendered on floor for any wash/PAR cue.

            # ── LASER BEAM GEOMETRY ───────────────────────────────────────────
            "laser_render_style": "line_segment",
            # Each beam = THREE.Line from fixture.position in fixture.aim direction.
            # Length exactly = fixture.beam_length metres; alpha fades 1→0 along length.
            # NEVER extend beyond beam_length. NEVER intersect with floor plane.
            "laser_aim_is_horizontal": True,
            # All aim Y=0 → beams travel horizontally through haze at truss height.
            "laser_off_means_invisible": True,
            # cue_type "laser_off" → opacity 0 on all beams immediately.

            # ── WASH BEAMS ────────────────────────────────────────────────────
            "wash_render_style": "volumetric_cone",
            # Additive CylinderGeometry / ShaderMaterial cone — no SpotLight.

            # ── LASER SWEEP ANIMATION ─────────────────────────────────────────
            "laser_animation": "continuous_sweep",
            "laser_static_mode_allowed": False,
            # Every active laser must always be in motion.

            # ── LASER SYMMETRY CONTRACT ───────────────────────────────────────
            "laser_symmetry": "bilateral",
            # The lasers group is split into three roles, read from fixture.id:
            #   "laser_oh_l" → LEFT unit,   sweep_phase_offset = 0°
            #   "laser_oh_r" → RIGHT unit,  sweep_phase_offset = 180°  ← mirror
            #   "laser_oh_c" → CENTER unit, sweep_phase_offset = 0°  (full scan)
            #
            # Bilateral sweep rule:
            #   sharedPhase = sin(t * freq * 2π) * phaseSign
            #   LEFT  pan  = +sharedPhase  (pans right as phase increases)
            #   RIGHT pan  = -sharedPhase  (pans LEFT — perfect mirror of LEFT)
            #   CENTER pan = +sharedPhase  (follows left, scanning full width)
            #
            # This guarantees the two outer beams always form a symmetric V
            # or X shape and span the full width of the stage simultaneously.

            "laser_burst_on_downbeat": True,
            # On bar downbeats (bar_times array), briefly fan all beams to
            # max scan_angle simultaneously for 1–2 frames, then resume sweep.
            # Creates the "burst" / explosive open-fan moment on the 1.

            "laser_full_span_required": True,
            # The combined sweep arc of all active lasers must cover the full
            # horizontal stage width on every sweep cycle — never cluster on
            # one side only.
        },
        description=(
            "Explicit renderer construction directives. These override any "
            "inferred behavior. Read once at scene init and apply globally."
        ),
    )
