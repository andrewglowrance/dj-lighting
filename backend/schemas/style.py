"""
schemas/style.py

Pydantic v2 models for the style-profile system.

A StyleProfile is a structured representation of the user's visual intent.
It sits between the music-derived CueOutputSchema and the final rendered
visualization payload.  The cue timing is never modified — only intensities,
colors, densities, and movement parameters are affected.

StylePatch is a sparse overlay used by the revision flow: any field left as
None means "keep the current value unchanged".

Advanced field groups (AdvancedLaserFields, AdvancedLightFields) encode
finer-grained rendering parameters derived from the reference dataset:
geometric plane orientation, beam edge hardness, temporal behavior modes,
spatial zone routing, audience reveal strength, and color separation modes.
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Vocabulary types derived from the visual reference dataset
# ---------------------------------------------------------------------------

VisualFamilyType = Literal[
    "laser_burst",          # explosive multi-beam burst from multiple origins
    "laser_fan",            # wide spread fan from single or symmetric origins
    "laser_sheet",          # flat planar sweep filling horizontal space
    "laser_tunnel",         # converging beams creating a vanishing-point tunnel
    "crossbeam_laser",      # beams crossing each other from opposing sources
    "wash_only",            # no lasers; pure wash/beam fill
    "wash_plus_laser",      # hybrid: moving-head beams + laser accents
    "beam_stack",           # multiple parallel or fanned moving-head shafts
    "strobe_accent",        # strobe-forward moment with reduced laser
    "crowd_blinder_moment", # white blinder / whiteout reveal
]

LaserMovementMechanic = Literal[
    "static_hold",           # locked in place, no sweep
    "slow_sweep",            # gradual left↔right oscillation
    "fast_sweep",            # rapid left↔right oscillation
    "fan_open",              # spread_deg expands outward over time
    "fan_close",             # spread_deg collapses inward
    "burst_outward",         # sudden radial explosion from origin
    "burst_inward",          # beams converge rapidly to a centre point
    "crosshatch",            # beams from opposing sources crossing mid-air
    "alternating_left_right",# beams snap alternately to left then right
    "stacked_vertical_layers",# upper zone and lower zone with independent colors
    "ceiling_rake",          # beams aimed up to paint the ceiling
    "audience_rake",         # beams angled into the audience space
    "center_converge",       # all beams converge to a single mid-air point
    "symmetrical_mirror",    # left and right sides mirror each other perfectly
]

# Advanced vocabulary from the annotated reference dataset
LaserPlaneOrientation = Literal["horizontal", "diagonal", "vertical", "mixed"]
LaserTemporalBehavior = Literal["hold", "pulse", "sweep", "alternate", "burst"]
LightTemporalBehavior = Literal["hold", "fade", "pulse", "chase", "reveal"]
MovementTransitionSpeed = Literal["snap", "fast", "medium", "slow"]
SpatialZone = Literal["upper_truss", "mid_stage", "floor_emitters", "side_emitters"]
ColorSeparationMode = Literal["single", "upper_lower_split", "left_right_split", "mixed"]


# ---------------------------------------------------------------------------
# Advanced field groups (reference-dataset derived)
# ---------------------------------------------------------------------------

class AdvancedLaserFields(BaseModel):
    """
    Finer-grained laser rendering parameters extracted from the annotated
    reference dataset.  These drive the frontend renderer — they do not alter
    cue timing.
    """
    # Geometry
    laser_plane_orientation: LaserPlaneOrientation = Field(
        "horizontal",
        description="Dominant plane of the laser fan: horizontal sheet, diagonal rake, vertical curtain, or mixed",
    )
    laser_open_angle_degrees: float = Field(
        45.0, ge=0.0, le=180.0,
        description="Estimated total fan opening angle in degrees across all active beams",
    )
    spatial_zone_usage: list[SpatialZone] = Field(
        default_factory=lambda: ["upper_truss", "floor_emitters"],
        description="Which physical zones are actively emitting beams",
    )

    # Beam appearance
    beam_edge_hardness: float = Field(
        0.70, ge=0.0, le=1.0,
        description="0 = soft, diffuse beam edge (scatter); 1 = hard knife-edge (sharp)",
    )
    bloom_radius_estimate: float = Field(
        0.30, ge=0.0, le=1.0,
        description="Bloom / glow halo radius around beams (0 = none, 1 = maximum)",
    )
    haze_density_estimate: float = Field(
        0.50, ge=0.0, le=1.0,
        description="Effective haze density in beam path; drives beam shaft visibility",
    )

    # Visibility
    source_legibility_score: float = Field(
        0.70, ge=0.0, le=1.0,
        description="How clearly the emitter origin point is visible to the audience",
    )
    audience_reveal_strength: float = Field(
        0.50, ge=0.0, le=1.0,
        description="Degree to which beams sweep into audience space (audience rake effect)",
    )
    screen_visibility_strength: float = Field(
        0.50, ge=0.0, le=1.0,
        description="Degree to which beams are legible against the stage backdrop",
    )

    # Temporal / motion
    laser_temporal_behavior: LaserTemporalBehavior = Field(
        "sweep",
        description="How beams behave over time: hold, pulse, sweep, alternate, or burst",
    )
    movement_transition_speed: MovementTransitionSpeed = Field(
        "medium",
        description="Speed at which the laser transitions between positions or patterns",
    )

    # Color layout
    color_separation_mode: ColorSeparationMode = Field(
        "single",
        description="How colors are spatially distributed: single, upper/lower split, left/right split, mixed",
    )


class EnvironmentRenderingProfile(BaseModel):
    """
    Static scene-geometry and material parameters consumed by the Three.js renderer
    to build a realistic venue environment around the lighting visualizer.

    Matches the environment_rendering_profile JSON structure provided by the user.
    Defaults below replicate the reference JSON values exactly.
    """
    # ── Geometry visibility flags ────────────────────────────────────────────
    show_stage_plane:          bool  = Field(True,  description="Render the stage floor plane")
    show_dj_booth_silhouette:  bool  = Field(True,  description="Render the DJ booth silhouette mesh")
    show_audience_band:        bool  = Field(False, description="Render an audience zone at the back")
    show_fixture_emitters:     bool  = Field(True,  description="Render visible emitter discs on fixtures")
    show_truss_lines:          bool  = Field(True,  description="Render truss pipe geometry")
    show_led_wall_blocks:      bool  = Field(True,  description="Render LED wall block grid on stage backdrop")

    # ── Audience style ───────────────────────────────────────────────────────
    audience_density:  Literal["sparse", "medium", "dense"] = Field(
        "medium", description="How many audience silhouettes to render")
    audience_style: Literal[
        "silhouette_heads_and_shoulders",
        "silhouette_full_body",
        "dot_crowd",
    ] = Field("silhouette_heads_and_shoulders",
              description="Visual style of the audience geometry")

    # ── Atmosphere / material properties ────────────────────────────────────
    haze_density_default:  float = Field(0.75, ge=0.0, le=1.0,
                                          description="Default haze density for the venue volume")
    screen_reflectivity:   float = Field(0.35, ge=0.0, le=1.0,
                                          description="LED backdrop / screen reflectivity [0=matte, 1=mirror]")
    floor_reflectivity:    float = Field(0.06, ge=0.0, le=1.0,
                                          description=(
                                              "Stage floor reflectivity [0=fully matte black, 1=mirror]. "
                                              "Keep at 0.06 for a barely-visible dark surface that shows "
                                              "fixture beams grazing it without creating bright floor pools."
                                          ))
    beam_bloom_strength:   float = Field(0.55, ge=0.0, le=2.0,
                                          description="UnrealBloomPass strength for wash / moving-head beams")
    laser_bloom_strength:  float = Field(0.18, ge=0.0, le=2.0,
                                          description="UnrealBloomPass strength for laser lines")

    # ── Scene lighting contract ──────────────────────────────────────────────
    # CRITICAL: the renderer must run in fixture-only lighting mode.
    # No AmbientLight, no HemisphereLight, no DirectionalLight added to the scene.
    # The only illumination comes from the active fixture cues (PointLight /
    # SpotLight / RectAreaLight per fixture). This prevents floor/wall color
    # bleeding from ambient fill.
    ambient_light_intensity: float = Field(
        0.0, ge=0.0, le=1.0,
        description=(
            "Intensity for the scene AmbientLight node. MUST be 0.0 — the scene "
            "uses fixture-only lighting. Any value > 0 will cause colored light to "
            "spill onto the floor and walls independent of active cues."
        ),
    )
    disable_scene_ambient:   bool  = Field(
        True,
        description=(
            "When True the renderer must NOT add any AmbientLight, HemisphereLight, "
            "or DirectionalLight to the Three.js scene. Illumination comes exclusively "
            "from fixture-driven PointLight / SpotLight objects that are activated "
            "and deactivated with each cue."
        ),
    )
    floor_material:          str   = Field(
        "MeshStandardMaterial_roughness1_metalness0_black",
        description=(
            "Material descriptor for the stage floor plane. Use MeshStandardMaterial "
            "with roughness=1.0, metalness=0.0, color=0x000000. This ensures the floor "
            "only brightens when a fixture beam physically hits it — no ambient fill."
        ),
    )


class AdvancedLightFields(BaseModel):
    """
    Advanced parameters for conventional fixture (wash, moving head, strobe)
    temporal rendering.  Mirrors AdvancedLaserFields for non-laser sources.
    """
    light_temporal_behavior: LightTemporalBehavior = Field(
        "hold",
        description="How conventional lights behave over time: hold, fade, pulse, chase, or reveal",
    )
    movement_transition_speed: MovementTransitionSpeed = Field(
        "medium",
        description="Speed at which moving heads transition between positions",
    )
    spatial_zone_usage: list[SpatialZone] = Field(
        default_factory=lambda: ["upper_truss"],
        description="Which physical zones are producing light output",
    )
    bloom_radius_estimate: float = Field(
        0.20, ge=0.0, le=1.0,
        description="Bloom radius for wash fixtures (0 = tight beam, 1 = heavy bloom)",
    )
    audience_reveal_strength: float = Field(
        0.40, ge=0.0, le=1.0,
        description="How aggressively wash beams spill into audience space",
    )


# ---------------------------------------------------------------------------
# Sub-profiles
# ---------------------------------------------------------------------------

class BrightnessProfile(BaseModel):
    """Per-section intensity multipliers stacked on top of global_scale."""
    global_scale:      float = Field(1.0, ge=0.0, le=2.0,
                                     description="Master brightness multiplier applied to all sections")
    intro_scale:       float = Field(0.60, ge=0.0, le=2.0)
    build_scale:       float = Field(0.80, ge=0.0, le=2.0)
    drop_scale:        float = Field(1.00, ge=0.0, le=2.0)
    breakdown_scale:   float = Field(0.40, ge=0.0, le=2.0)
    outro_scale:       float = Field(0.50, ge=0.0, le=2.0)


class MovementProfile(BaseModel):
    enabled:           bool  = True
    speed_scale:       float = Field(1.0,  ge=0.0, le=3.0,
                                     description="Multiplier on movement_enable speed params")
    range_scale:       float = Field(1.0,  ge=0.0, le=2.0,
                                     description="Multiplier on laser scan_angle / sweep range")
    transition_style:  Literal["snap", "fade", "auto"] = "auto"


class StrobeProfile(BaseModel):
    enabled:           bool  = True
    intensity_scale:   float = Field(1.0, ge=0.0, le=2.0)
    rate_scale:        float = Field(1.0, ge=0.0, le=2.0)
    restrict_to_drops: bool  = False


class AtmosphereProfile(BaseModel):
    style:       Literal["dark", "warm", "cinematic", "neutral", "festival"] = "neutral"
    fade_speed:  Literal["slow", "medium", "fast"] = "medium"
    fog_density: float = Field(0.5, ge=0.0, le=1.0)


class SectionEmphasis(BaseModel):
    """Weight multipliers that scale section-level brightness and density."""
    intro_weight:     float = Field(1.0, ge=0.0, le=2.0)
    build_weight:     float = Field(1.0, ge=0.0, le=2.0)
    drop_weight:      float = Field(1.0, ge=0.0, le=2.0)
    breakdown_weight: float = Field(1.0, ge=0.0, le=2.0)
    outro_weight:     float = Field(1.0, ge=0.0, le=2.0)


class LaserLayerProfile(BaseModel):
    """
    Dual-zone color layer separation, as seen in the red/blue split reference.
    When enabled, upper-zone beams use upper_palette and lower-zone beams use
    lower_palette — two independent color families coexist simultaneously.
    """
    enabled:           bool  = False
    upper_palette:     str   = "laser_red"   # color key for overhead / canopy beams
    lower_palette:     str   = "laser_blue"  # color key for stage-deck / floor beams
    upper_beam_count:  int   = Field(4, ge=1, le=20)
    lower_beam_count:  int   = Field(4, ge=1, le=20)
    upper_spread_deg:  float = Field(45.0, ge=0.0, le=180.0)
    lower_spread_deg:  float = Field(60.0, ge=0.0, le=180.0)


class LaserProfile(BaseModel):
    enabled:           bool  = True
    density:           float = Field(0.70, ge=0.0, le=1.0,
                                     description="Fraction of laser cues retained [0=none, 1=all]")
    intensity_scale:   float = Field(1.0,  ge=0.0, le=2.0)
    palette:           Literal["rgb", "cool", "warm", "green_only", "magenta_only",
                               "red_only", "white_only", "auto"] = "auto"
    movement_speed:    float = Field(1.0,  ge=0.0, le=3.0)
    movement_range:    float = Field(1.0,  ge=0.0, le=2.0)
    fan_width_scale:   float = Field(1.0,  ge=0.0, le=2.0,
                                     description="Multiplier on spread_deg for fan patterns")
    restrict_to_drops: bool  = False
    chase_intensity:   float = Field(1.0,  ge=0.0, le=2.0)

    # Reference-dataset-derived fields
    visual_family:       VisualFamilyType         = "laser_fan"
    movement_mechanics:  list[LaserMovementMechanic] = Field(
        default_factory=lambda: ["slow_sweep", "symmetrical_mirror"])
    layer_profile:       LaserLayerProfile         = Field(default_factory=LaserLayerProfile)
    burst_cluster:       bool  = False   # enables multi-origin burst geometry
    crosshatch:          bool  = False   # enables opposing-source crossing beams
    emission_zones:      list[Literal["overhead", "stage_deck", "side"]] = Field(
        default_factory=lambda: ["overhead"],
        description="Which fixture zones actively emit beams")
    beam_count_target:   int   = Field(8, ge=1, le=48,
                                       description="Desired total beam count across all fixtures")
    haze_dependency:     float = Field(0.70, ge=0.0, le=1.0,
                                       description="How strongly beam visibility scales with fog_density")


# ---------------------------------------------------------------------------
# Top-level StyleProfile
# ---------------------------------------------------------------------------

class StyleProfile(BaseModel):
    """
    Complete style specification derived from a user prompt (or defaults).
    Every field here drives the style engine — never the cue timing.
    """

    # Global feel knobs (0–1 scales)
    aggressiveness:      float = Field(0.50, ge=0.0, le=1.0,
                                       description="0=gentle, 1=maximal intensity")
    smoothness:          float = Field(0.50, ge=0.0, le=1.0,
                                       description="0=snappy/hard-cut, 1=slow/flowing")
    festival_scale_bias: float = Field(0.50, ge=0.0, le=1.0,
                                       description="0=intimate club, 1=festival mainstage")
    restraint_level:     float = Field(0.30, ge=0.0, le=1.0,
                                       description="0=chaotic/dense, 1=minimal/sparse")
    visual_density:      float = Field(0.70, ge=0.0, le=1.0,
                                       description="Fraction of high-frequency cues retained")

    # Color
    palette: Literal["cool", "warm", "neutral", "monochrome", "auto"] = "auto"

    # Sub-profiles
    brightness_profile: BrightnessProfile = Field(default_factory=BrightnessProfile)
    movement_profile:   MovementProfile   = Field(default_factory=MovementProfile)
    strobe_profile:     StrobeProfile     = Field(default_factory=StrobeProfile)
    atmosphere_profile: AtmosphereProfile = Field(default_factory=AtmosphereProfile)
    section_emphasis:   SectionEmphasis   = Field(default_factory=SectionEmphasis)
    laser_profile:      LaserProfile      = Field(default_factory=LaserProfile)

    # Advanced rendering fields (reference-dataset derived)
    advanced_laser:  AdvancedLaserFields = Field(default_factory=AdvancedLaserFields)
    advanced_light:  AdvancedLightFields = Field(default_factory=AdvancedLightFields)

    # Provenance
    prompt_source: str | None         = Field(None, description="Original prompt text")
    notes:         list[str]          = Field(default_factory=list,
                                              description="Human-readable explanation of applied signals")


# ---------------------------------------------------------------------------
# StylePatch — sparse delta for the revision flow
# ---------------------------------------------------------------------------

class StylePatch(BaseModel):
    """
    A sparse set of overrides produced by a revision prompt.
    None means "no change to this field".
    Applied on top of the current StyleProfile to produce a new one.
    """
    aggressiveness:      float | None = None
    smoothness:          float | None = None
    festival_scale_bias: float | None = None
    restraint_level:     float | None = None
    visual_density:      float | None = None
    palette:             str   | None = None

    # Brightness
    brightness_global_scale:    float | None = None
    brightness_drop_scale:      float | None = None
    brightness_build_scale:     float | None = None
    brightness_breakdown_scale: float | None = None
    brightness_intro_scale:     float | None = None

    # Movement
    movement_enabled:    bool  | None = None
    movement_speed:      float | None = None
    movement_range:      float | None = None

    # Strobe
    strobe_enabled:      bool  | None = None
    strobe_intensity:    float | None = None
    strobe_drops_only:   bool  | None = None

    # Atmosphere
    atmosphere_style:    str   | None = None
    atmosphere_fog:      float | None = None

    # Section emphasis
    drop_weight:         float | None = None
    build_weight:        float | None = None
    breakdown_weight:    float | None = None

    # Laser — base
    laser_enabled:       bool  | None = None
    laser_density:       float | None = None
    laser_intensity:     float | None = None
    laser_palette:       str   | None = None
    laser_movement:      float | None = None
    laser_range:         float | None = None
    laser_fan_width:     float | None = None
    laser_drops_only:    bool  | None = None
    laser_chase_intens:  float | None = None
    laser_beam_count:    int   | None = None

    # Laser — reference-dataset fields
    laser_visual_family:    str  | None = None   # VisualFamilyType key
    laser_burst_cluster:    bool | None = None
    laser_crosshatch:       bool | None = None
    laser_haze_dependency:  float| None = None
    laser_layer_enabled:    bool | None = None
    laser_layer_upper_pal:  str  | None = None
    laser_layer_lower_pal:  str  | None = None
    laser_emission_zones:   list[str] | None = None

    # Advanced laser fields (reference-dataset derived)
    adv_laser_plane:          str   | None = None   # LaserPlaneOrientation
    adv_laser_open_angle:     float | None = None
    adv_laser_spatial_zones:  list[str] | None = None   # list[SpatialZone]
    adv_laser_edge_hardness:  float | None = None
    adv_laser_bloom:          float | None = None
    adv_laser_haze_density:   float | None = None
    adv_laser_src_legibility: float | None = None
    adv_laser_audience_rev:   float | None = None
    adv_laser_screen_vis:     float | None = None
    adv_laser_temporal:       str   | None = None   # LaserTemporalBehavior
    adv_laser_transition_spd: str   | None = None   # MovementTransitionSpeed
    adv_laser_color_sep:      str   | None = None   # ColorSeparationMode

    # Advanced light fields (reference-dataset derived)
    adv_light_temporal:       str   | None = None   # LightTemporalBehavior
    adv_light_transition_spd: str   | None = None   # MovementTransitionSpeed
    adv_light_spatial_zones:  list[str] | None = None
    adv_light_bloom:          float | None = None
    adv_light_audience_rev:   float | None = None

    # Revision notes (filled in by apply_patch)
    changed_fields: list[str] = Field(default_factory=list)
    notes:          list[str] = Field(default_factory=list)
