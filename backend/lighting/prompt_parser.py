"""
lighting/prompt_parser.py

Deterministic keyword-based prompt → StyleProfile / StylePatch converter.

Expanded in v2 with:
  - 6 named style-token presets derived from the visual reference dataset
    (warehouse_blue_burst, festival_green_room_fan, magenta_spike_attack,
     red_blue_split_layers, white_reveal_stadium, amber_room_bath)
  - Full VisualFamilyType and LaserMovementMechanic vocabulary
  - Multi-zone emission signals (overhead / stage_deck / side)
  - Dual-layer color separation (LaserLayerProfile)
  - Expanded movement mechanics (crosshatch, burst_outward, center_converge,
    fan_open/close, audience_rake, ceiling_rake, alternating_left_right)
  - Haze dependency and beam-count target signals
  - Magenta / violet palette support

Expanded in v3 with AdvancedLaserFields / AdvancedLightFields signals:
  - Laser plane orientation (horizontal, diagonal, vertical, mixed)
  - Beam edge hardness (hard knife-edge vs. soft scatter)
  - Laser temporal behavior (hold, pulse, sweep, alternate, burst)
  - Light temporal behavior (hold, fade, pulse, chase, reveal)
  - Spatial zone routing (upper_truss, mid_stage, floor_emitters, side_emitters)
  - Color separation mode (single, upper_lower_split, left_right_split, mixed)
  - Audience reveal and screen visibility strength
  - Movement transition speed (snap, fast, medium, slow)
  - Bloom and haze density estimates

Design goals:
  - No LLM dependency — purely rule-based; output is inspectable and testable.
  - Every change is recorded in notes[] for frontend display.
  - Initial generation: parse_prompt()    → full StyleProfile (from defaults).
  - Revision:          parse_revision()  → StylePatch (delta only).
  - Patch merge:       apply_patch()     → new StyleProfile from patch + current.
"""

from __future__ import annotations

from backend.schemas.style import (
    AdvancedLaserFields,
    AdvancedLightFields,
    AtmosphereProfile,
    BrightnessProfile,
    LaserLayerProfile,
    LaserProfile,
    MovementProfile,
    SectionEmphasis,
    StrobeProfile,
    StylePatch,
    StyleProfile,
)


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _has(text: str, *phrases: str) -> bool:
    return any(p in text for p in phrases)


# ---------------------------------------------------------------------------
# Default working dicts (mirrors StyleProfile defaults)
# ---------------------------------------------------------------------------

def _default_top() -> dict:
    return dict(aggressiveness=0.50, smoothness=0.50, festival_scale_bias=0.50,
                restraint_level=0.30, visual_density=0.70, palette="auto")


def _default_bp() -> dict:
    return dict(global_scale=1.0, intro_scale=0.60, build_scale=0.80,
                drop_scale=1.00, breakdown_scale=0.40, outro_scale=0.50)


def _default_mp() -> dict:
    return dict(enabled=True, speed_scale=1.0, range_scale=1.0,
                transition_style="auto")


def _default_sp() -> dict:
    return dict(enabled=True, intensity_scale=1.0, rate_scale=1.0,
                restrict_to_drops=False)


def _default_ap() -> dict:
    return dict(style="neutral", fade_speed="medium", fog_density=0.5)


def _default_se() -> dict:
    return dict(intro_weight=1.0, build_weight=1.0, drop_weight=1.0,
                breakdown_weight=1.0, outro_weight=1.0)


def _default_lp() -> dict:
    return dict(
        enabled=True, density=0.70, intensity_scale=1.0, palette="auto",
        movement_speed=1.0, movement_range=1.0, fan_width_scale=1.0,
        restrict_to_drops=False, chase_intensity=1.0,
        visual_family="laser_fan",
        movement_mechanics=["slow_sweep", "symmetrical_mirror"],
        burst_cluster=False, crosshatch=False,
        emission_zones=["overhead"],
        beam_count_target=8, haze_dependency=0.70,
    )


def _default_layer() -> dict:
    return dict(enabled=False, upper_palette="laser_red", lower_palette="laser_blue",
                upper_beam_count=4, lower_beam_count=4,
                upper_spread_deg=45.0, lower_spread_deg=60.0)


def _default_adv_laser() -> dict:
    return dict(
        laser_plane_orientation="horizontal",
        laser_open_angle_degrees=45.0,
        spatial_zone_usage=["upper_truss", "floor_emitters"],
        beam_edge_hardness=0.70,
        bloom_radius_estimate=0.30,
        haze_density_estimate=0.50,
        source_legibility_score=0.70,
        audience_reveal_strength=0.50,
        screen_visibility_strength=0.50,
        laser_temporal_behavior="sweep",
        movement_transition_speed="medium",
        color_separation_mode="single",
    )


def _default_adv_light() -> dict:
    return dict(
        light_temporal_behavior="hold",
        movement_transition_speed="medium",
        spatial_zone_usage=["upper_truss"],
        bloom_radius_estimate=0.20,
        audience_reveal_strength=0.40,
    )


# ---------------------------------------------------------------------------
# Named style-token presets (derived from visual reference dataset)
# ---------------------------------------------------------------------------

# Each preset returns (top_overrides, bp_overrides, lp_overrides, layer_overrides, ap_overrides, note)
_STYLE_TOKENS: dict[str, dict] = {

    # ── warehouse blue burst ────────────────────────────────────────────────
    # Reference: dense blue/cyan burst canopy, multiple floor + overhead origins
    "warehouse_blue_burst": dict(
        top=dict(aggressiveness=0.75, smoothness=0.25, festival_scale_bias=0.55,
                 restraint_level=0.10, visual_density=0.95, palette="cool"),
        bp=dict(global_scale=0.85, drop_scale=1.0, breakdown_scale=0.20),
        ap=dict(style="dark", fog_density=0.90, fade_speed="fast"),
        lp=dict(density=0.95, intensity_scale=1.3, palette="cool",
                visual_family="laser_burst", movement_speed=1.8,
                movement_range=1.4, fan_width_scale=0.6,
                burst_cluster=True, crosshatch=True,
                emission_zones=["overhead", "stage_deck"],
                beam_count_target=28, haze_dependency=0.95,
                movement_mechanics=["burst_outward", "symmetrical_mirror",
                                    "crosshatch", "center_converge"]),
        layer=dict(enabled=False),
        note="Style preset: warehouse blue burst — dense cyan/blue multi-origin burst, high haze"),

    # ── festival green room fan ─────────────────────────────────────────────
    # Reference: extreme-width green fan arrays from overhead, audience rake
    "festival_green_room_fan": dict(
        top=dict(aggressiveness=0.80, smoothness=0.30, festival_scale_bias=0.95,
                 restraint_level=0.05, visual_density=1.00, palette="neutral"),
        bp=dict(global_scale=0.90, drop_scale=1.0),
        ap=dict(style="festival", fog_density=0.85, fade_speed="fast"),
        lp=dict(density=1.0, intensity_scale=1.4, palette="green_only",
                visual_family="laser_fan", movement_speed=1.5,
                movement_range=1.8, fan_width_scale=1.8,
                burst_cluster=False, crosshatch=True,
                emission_zones=["overhead", "side"],
                beam_count_target=36, haze_dependency=0.95,
                movement_mechanics=["fan_open", "audience_rake",
                                    "crosshatch", "symmetrical_mirror"]),
        layer=dict(enabled=False),
        note="Style preset: festival green room fan — wall-to-wall green fan sheets, extreme density"),

    # ── magenta spike attack ────────────────────────────────────────────────
    # Reference: angular violet/magenta needle beams, non-uniform geometry
    "magenta_spike_attack": dict(
        top=dict(aggressiveness=0.85, smoothness=0.15, festival_scale_bias=0.70,
                 restraint_level=0.10, visual_density=0.85, palette="cool"),
        bp=dict(global_scale=0.90, drop_scale=1.0, breakdown_scale=0.25),
        ap=dict(style="dark", fog_density=0.80, fade_speed="fast"),
        lp=dict(density=0.85, intensity_scale=1.2, palette="magenta_only",
                visual_family="laser_burst", movement_speed=2.0,
                movement_range=1.2, fan_width_scale=0.5,
                burst_cluster=True, crosshatch=True,
                emission_zones=["overhead", "stage_deck"],
                beam_count_target=20, haze_dependency=0.85,
                movement_mechanics=["burst_outward", "fast_sweep",
                                    "crosshatch", "alternating_left_right"]),
        layer=dict(enabled=False),
        note="Style preset: magenta spike attack — angular violet/magenta needle bursts"),

    # ── red blue split layers ───────────────────────────────────────────────
    # Reference: red upper canopy + blue/white lower crossing — dual color zones
    "red_blue_split_layers": dict(
        top=dict(aggressiveness=0.65, smoothness=0.35, festival_scale_bias=0.75,
                 restraint_level=0.20, visual_density=0.75, palette="neutral"),
        bp=dict(global_scale=0.85, drop_scale=1.0),
        ap=dict(style="dark", fog_density=0.80, fade_speed="medium"),
        lp=dict(density=0.75, intensity_scale=1.1, palette="rgb",
                visual_family="crossbeam_laser", movement_speed=1.2,
                movement_range=1.0, fan_width_scale=0.8,
                burst_cluster=False, crosshatch=True,
                emission_zones=["overhead", "stage_deck"],
                beam_count_target=18, haze_dependency=0.85,
                movement_mechanics=["stacked_vertical_layers", "symmetrical_mirror",
                                    "center_converge", "alternating_left_right"]),
        layer=dict(enabled=True, upper_palette="laser_red", lower_palette="laser_blue",
                   upper_beam_count=6, lower_beam_count=6,
                   upper_spread_deg=50.0, lower_spread_deg=65.0),
        note="Style preset: red/blue dual-layer — upper red fans, lower blue crossing beams"),

    # ── white reveal stadium ────────────────────────────────────────────────
    # Reference: full white whiteout with layered moving-head shafts, no lasers
    "white_reveal_stadium": dict(
        top=dict(aggressiveness=0.55, smoothness=0.70, festival_scale_bias=0.95,
                 restraint_level=0.45, visual_density=0.80, palette="neutral"),
        bp=dict(global_scale=1.40, intro_scale=0.50, drop_scale=1.60,
                build_scale=1.10, breakdown_scale=0.40),
        ap=dict(style="festival", fog_density=0.90, fade_speed="slow"),
        lp=dict(enabled=False, density=0.0),
        layer=dict(enabled=False),
        note="Style preset: white stadium reveal — full white whiteout, no lasers, moving head stacks"),

    # ── amber room bath ─────────────────────────────────────────────────────
    # Reference: warm orange/amber radial wash filling entire room volume
    "amber_room_bath": dict(
        top=dict(aggressiveness=0.35, smoothness=0.75, festival_scale_bias=0.65,
                 restraint_level=0.55, visual_density=0.50, palette="warm"),
        bp=dict(global_scale=1.20, drop_scale=1.40, breakdown_scale=0.60),
        ap=dict(style="warm", fog_density=0.85, fade_speed="slow"),
        lp=dict(enabled=False, density=0.0),
        layer=dict(enabled=False),
        note="Style preset: amber room bath — warm orange wash immersion, no lasers, high haze"),
}

# Phrase triggers that map to each token
_TOKEN_TRIGGERS: dict[str, list[str]] = {
    "warehouse_blue_burst":     ["warehouse blue", "blue burst", "blue warehouse",
                                  "blue underground", "warehouse burst"],
    "festival_green_room_fan":  ["festival green", "green fan", "green room fill",
                                  "green room flare", "green flare", "green laser festival"],
    "magenta_spike_attack":     ["magenta spike", "purple spike", "violet spike",
                                  "magenta attack", "angular purple", "magenta burst"],
    "red_blue_split_layers":    ["red blue split", "dual layer", "two layer laser",
                                  "red and blue laser", "layered laser", "split color laser"],
    "white_reveal_stadium":     ["white reveal", "stadium reveal", "stadium white",
                                  "whiteout reveal", "white stadium", "full white show"],
    "amber_room_bath":          ["amber room", "warm bath", "orange room fill",
                                  "amber wash", "warm immersion", "golden room"],
}


def _apply_token(token_key: str, top: dict, bp: dict, mp: dict, sp: dict,
                  ap: dict, se: dict, lp: dict, layer: dict, notes: list[str]) -> bool:
    """Apply a named style token preset. Returns True if matched."""
    preset = _STYLE_TOKENS.get(token_key)
    if not preset:
        return False
    top.update(preset.get("top", {}))
    bp.update(preset.get("bp", {}))
    ap.update(preset.get("ap", {}))
    lp.update(preset.get("lp", {}))
    layer.update(preset.get("layer", {}))
    notes.append(preset.get("note", f"Style token applied: {token_key}"))
    return True


# ---------------------------------------------------------------------------
# Signal extractors
# ---------------------------------------------------------------------------

def _sig_style_tokens(t: str, top: dict, bp: dict, mp: dict, sp: dict,
                       ap: dict, se: dict, lp: dict, layer: dict, notes: list[str]) -> None:
    """Check all named style token triggers first — they take priority."""
    for token_key, triggers in _TOKEN_TRIGGERS.items():
        if _has(t, *triggers):
            _apply_token(token_key, top, bp, mp, sp, ap, se, lp, layer, notes)
            return  # apply at most one token per prompt


def _sig_global_feel(t: str, top: dict, notes: list[str]) -> None:
    if _has(t, "dark ", "darker", "dim ", "warehouse", "underground",
               "industrial", "gothic", "gloomy", "deep dark"):
        top["aggressiveness"] = _clamp(top["aggressiveness"] - 0.10)
        top["restraint_level"] = _clamp(top["restraint_level"] + 0.20)
        notes.append("Dark atmosphere applied")

    if _has(t, "aggressive", "intense", "hard ", "heavy", "punchy",
               "brutal", "violent", "high energy", "high-energy", "energetic"):
        top["aggressiveness"] = _clamp(top["aggressiveness"] + 0.30)
        top["smoothness"] = _clamp(top["smoothness"] - 0.20)
        notes.append("High aggressiveness applied")

    if _has(t, "smooth", "soft", "gentle", "flowing", "mellow",
               "relaxed", "laid-back", "laid back", "chill"):
        top["smoothness"] = _clamp(top["smoothness"] + 0.30)
        top["aggressiveness"] = _clamp(top["aggressiveness"] - 0.20)
        notes.append("Smooth / soft style applied")

    if _has(t, "festival", "massive", "epic", "stadium", "mainstage",
               "main stage", "huge", "grandiose", "big show"):
        top["festival_scale_bias"] = _clamp(top["festival_scale_bias"] + 0.35)
        top["visual_density"] = _clamp(top["visual_density"] + 0.20)
        notes.append("Festival scale bias increased")

    if _has(t, "minimal", "minimalist", "subtle", "restrained", "sparse",
               "simple ", "clean ", "stripped", "less is more"):
        top["restraint_level"] = _clamp(top["restraint_level"] + 0.35)
        top["visual_density"] = _clamp(top["visual_density"] - 0.30)
        notes.append("Minimal / sparse style applied")

    if _has(t, "cinematic", "film", "movie", "dramatic arc"):
        top["smoothness"] = _clamp(top["smoothness"] + 0.25)
        notes.append("Cinematic style applied")

    if _has(t, "busy", "dense", "full ", "packed"):
        top["visual_density"] = _clamp(top["visual_density"] + 0.25)
        top["restraint_level"] = _clamp(top["restraint_level"] - 0.20)
        notes.append("High visual density applied")


def _sig_palette(t: str, top: dict, notes: list[str]) -> None:
    if _has(t, "cool tone", "cold ", "icy ", "blue and purple",
               "blue tones", "cool blue", "cool palette", "blue/purple"):
        top["palette"] = "cool"
        notes.append("Cool palette applied")
    elif _has(t, "warm tone", "warm palette", "golden", "amber tone",
                 "warm lighting", "warm feel", "orange tone"):
        top["palette"] = "warm"
        notes.append("Warm palette applied")
    elif _has(t, "monochrome", "single color", "one color", "mono "):
        top["palette"] = "monochrome"
        notes.append("Monochrome palette applied")
    elif _has(t, " blue", " purple", " violet"):
        top["palette"] = "cool"
        notes.append("Cool palette inferred from color")
    elif _has(t, " amber", " orange", " warm"):
        top["palette"] = "warm"
        notes.append("Warm palette inferred from color")


def _sig_brightness(t: str, bp: dict, notes: list[str]) -> None:
    if _has(t, "brighter", "more bright", "higher brightness", "brighten"):
        for k in bp:
            bp[k] = _clamp(bp[k] + 0.25, 0.0, 2.0)
        notes.append("Global brightness increased")
    if _has(t, "dim ", "darker", "lower brightness", "dimmer"):
        for k in bp:
            bp[k] = _clamp(bp[k] - 0.25, 0.0, 2.0)
        notes.append("Global brightness reduced")


def _sig_movement(t: str, mp: dict, notes: list[str]) -> None:
    if _has(t, "no movement", "static show", "no motion", "disable movement"):
        mp["enabled"] = False
        notes.append("Movement disabled")
        return
    if _has(t, "more movement", "more motion", "faster sweep", "faster pan",
               "wild movement", "rapid movement"):
        mp["speed_scale"] = _clamp(mp["speed_scale"] + 0.40, 0.0, 3.0)
        mp["range_scale"] = _clamp(mp["range_scale"] + 0.30, 0.0, 2.0)
        notes.append("Movement speed and range increased")
    if _has(t, "less movement", "less motion", "slower movement", "minimal movement"):
        mp["speed_scale"] = _clamp(mp["speed_scale"] - 0.40, 0.0, 3.0)
        mp["range_scale"] = _clamp(mp["range_scale"] - 0.25, 0.0, 2.0)
        notes.append("Movement reduced")
    if _has(t, "slow drift", "very slow"):
        mp["speed_scale"] = _clamp(mp["speed_scale"] - 0.50, 0.0, 3.0)
        mp["transition_style"] = "fade"
        notes.append("Slow drift movement applied")
    if _has(t, "sharp movement", "snapping", "fast snap", "hard cut"):
        mp["transition_style"] = "snap"
        notes.append("Snap transitions applied")


def _sig_strobe(t: str, sp: dict, notes: list[str]) -> None:
    if _has(t, "no strobe", "remove strobe", "disable strobe", "without strobe"):
        sp["enabled"] = False
        notes.append("Strobe disabled")
        return
    if _has(t, "strobe only on drop", "strobe on drop", "drop strobe only"):
        sp["restrict_to_drops"] = True
        notes.append("Strobe restricted to drops")
    if _has(t, "more strobe", "heavy strobe", "brighter strobe", "harder strobe"):
        sp["intensity_scale"] = _clamp(sp["intensity_scale"] + 0.35, 0.0, 2.0)
        sp["rate_scale"] = _clamp(sp["rate_scale"] + 0.25, 0.0, 2.0)
        notes.append("Strobe intensity and rate increased")
    if _has(t, "less strobe", "fewer strobe", "reduce strobe", "softer flash"):
        sp["intensity_scale"] = _clamp(sp["intensity_scale"] - 0.35, 0.0, 2.0)
        sp["rate_scale"] = _clamp(sp["rate_scale"] - 0.25, 0.0, 2.0)
        notes.append("Strobe reduced")


def _sig_atmosphere(t: str, ap: dict, notes: list[str]) -> None:
    if _has(t, "dark atmosphere", "dark mood", "warehouse feel", "underground feel"):
        ap["style"] = "dark"
        ap["fog_density"] = _clamp(ap["fog_density"] + 0.25)
        notes.append("Dark atmosphere applied")
    elif _has(t, "warm atmosphere", "warm feel"):
        ap["style"] = "warm"
        notes.append("Warm atmosphere applied")
    elif _has(t, "cinematic feel", "cinematic atmosphere"):
        ap["style"] = "cinematic"
        ap["fade_speed"] = "slow"
        notes.append("Cinematic atmosphere applied")
    elif _has(t, "festival feel", "festival atmosphere"):
        ap["style"] = "festival"
        ap["fog_density"] = _clamp(ap["fog_density"] + 0.30)
        notes.append("Festival atmosphere applied")
    if _has(t, "more haze", "more fog", "foggy", "smoky", "heavy haze"):
        ap["fog_density"] = _clamp(ap["fog_density"] + 0.30)
        notes.append("Fog density increased")
    if _has(t, "slow fade", "slow transition", "gradual"):
        ap["fade_speed"] = "slow"
        notes.append("Slow fades applied")
    if _has(t, "fast fade", "fast transition", "quick cut"):
        ap["fade_speed"] = "fast"
        notes.append("Fast fades applied")


def _sig_section_emphasis(t: str, se: dict, notes: list[str]) -> None:
    if _has(t, "bigger drop", "more intense drop", "emphasize drop",
               "harder drop", "aggressive drop"):
        se["drop_weight"] = _clamp(se["drop_weight"] + 0.40, 0.0, 2.0)
        notes.append("Drop section emphasis increased")
    if _has(t, "darker breakdown", "atmospheric breakdown", "moody breakdown"):
        se["breakdown_weight"] = _clamp(se["breakdown_weight"] + 0.30, 0.0, 2.0)
        notes.append("Breakdown emphasis increased")
    if _has(t, "bigger build", "more intense build", "heavier build"):
        se["build_weight"] = _clamp(se["build_weight"] + 0.30, 0.0, 2.0)
        notes.append("Build emphasis increased")


def _sig_laser(t: str, lp: dict, layer: dict, ap: dict, notes: list[str]) -> None:
    # ── Disable ──────────────────────────────────────────────────────────────
    if _has(t, "no laser", "remove laser", "disable laser", "without laser"):
        lp["enabled"] = False
        notes.append("Lasers disabled")
        return

    # ── Restrict to drops ─────────────────────────────────────────────────
    if _has(t, "laser only on drop", "laser on drop", "drop laser only",
               "laser accent on drop", "laser accents only on"):
        lp["restrict_to_drops"] = True
        notes.append("Lasers restricted to drops")

    # ── Density / presence ────────────────────────────────────────────────
    if _has(t, "more laser", "prominent laser", "heavy laser", "laser forward",
               "laser heavy", "bigger laser"):
        lp["density"] = _clamp(lp["density"] + 0.25)
        lp["intensity_scale"] = _clamp(lp["intensity_scale"] + 0.30, 0.0, 2.0)
        lp["beam_count_target"] = min(48, lp.get("beam_count_target", 8) + 8)
        notes.append("Laser density and intensity increased")
    if _has(t, "less laser", "fewer laser", "reduce laser", "subtle laser"):
        lp["density"] = _clamp(lp["density"] - 0.30)
        lp["intensity_scale"] = _clamp(lp["intensity_scale"] - 0.25, 0.0, 2.0)
        lp["beam_count_target"] = max(2, lp.get("beam_count_target", 8) - 4)
        notes.append("Laser density reduced")

    # ── Fan width ─────────────────────────────────────────────────────────
    if _has(t, "wide fan", "wide laser", "room-wide laser", "broad laser",
               "spread laser", "full room fan"):
        lp["fan_width_scale"] = _clamp(lp["fan_width_scale"] + 0.50, 0.0, 2.0)
        lp["movement_mechanics"] = list(set(
            lp.get("movement_mechanics", []) + ["fan_open", "audience_rake"]))
        notes.append("Wide fan laser applied")
    if _has(t, "tight laser", "sharp laser", "narrow laser", "sharp accent", "needle"):
        lp["fan_width_scale"] = _clamp(lp["fan_width_scale"] - 0.40, 0.0, 2.0)
        lp["visual_family"] = "laser_burst"
        notes.append("Narrow needle-beam lasers applied")

    # ── Visual family ─────────────────────────────────────────────────────
    if _has(t, "laser burst", "burst laser", "explosive laser"):
        lp["visual_family"] = "laser_burst"
        lp["burst_cluster"] = True
        lp["movement_mechanics"] = list(set(
            lp.get("movement_mechanics", []) + ["burst_outward", "symmetrical_mirror"]))
        notes.append("Laser burst cluster family applied")
    if _has(t, "laser tunnel", "tunnel laser", "converging laser"):
        lp["visual_family"] = "laser_tunnel"
        lp["movement_mechanics"] = list(set(
            lp.get("movement_mechanics", []) + ["center_converge"]))
        notes.append("Laser tunnel / convergence applied")
    if _has(t, "laser sheet", "sheet laser", "flat laser"):
        lp["visual_family"] = "laser_sheet"
        lp["fan_width_scale"] = _clamp(lp.get("fan_width_scale", 1.0) + 0.60, 0.0, 2.0)
        notes.append("Laser sheet / plane applied")

    # ── Movement mechanics ────────────────────────────────────────────────
    if _has(t, "crosshatch", "cross hatch", "crisscross", "lattice laser"):
        lp["crosshatch"] = True
        mec = lp.get("movement_mechanics", [])
        if "crosshatch" not in mec:
            lp["movement_mechanics"] = mec + ["crosshatch"]
        notes.append("Crosshatch lattice enabled")
    if _has(t, "burst outward", "outward burst", "radial burst", "explosion laser"):
        lp["burst_cluster"] = True
        mec = lp.get("movement_mechanics", [])
        if "burst_outward" not in mec:
            lp["movement_mechanics"] = mec + ["burst_outward"]
        notes.append("Burst-outward pattern enabled")
    if _has(t, "center converge", "converge center", "converging beams",
               "inward burst"):
        mec = lp.get("movement_mechanics", [])
        if "center_converge" not in mec:
            lp["movement_mechanics"] = mec + ["center_converge"]
        notes.append("Center convergence enabled")
    if _has(t, "audience rake", "rake audience", "crowd rake", "over crowd"):
        mec = lp.get("movement_mechanics", [])
        if "audience_rake" not in mec:
            lp["movement_mechanics"] = mec + ["audience_rake"]
        lp["movement_range"] = _clamp(lp.get("movement_range", 1.0) + 0.30, 0.0, 2.0)
        notes.append("Audience rake enabled")
    if _has(t, "ceiling rake", "ceiling laser", "paint ceiling", "upper canopy"):
        mec = lp.get("movement_mechanics", [])
        if "ceiling_rake" not in mec:
            lp["movement_mechanics"] = mec + ["ceiling_rake"]
        lp["emission_zones"] = list(set(
            lp.get("emission_zones", ["overhead"]) + ["stage_deck"]))
        notes.append("Ceiling rake (upward floor lasers) enabled")
    if _has(t, "fan open", "opening fan", "expanding fan"):
        mec = lp.get("movement_mechanics", [])
        if "fan_open" not in mec:
            lp["movement_mechanics"] = mec + ["fan_open"]
        notes.append("Fan-open animation enabled")
    if _has(t, "alternating", "left right alternating", "side alternating"):
        mec = lp.get("movement_mechanics", [])
        if "alternating_left_right" not in mec:
            lp["movement_mechanics"] = mec + ["alternating_left_right"]
        notes.append("Alternating left-right pattern enabled")

    # ── Emission zones ────────────────────────────────────────────────────
    if _has(t, "floor laser", "ground laser", "stage floor laser",
               "laser from floor", "upward laser", "deck laser"):
        zones = lp.get("emission_zones", ["overhead"])
        if "stage_deck" not in zones:
            lp["emission_zones"] = zones + ["stage_deck"]
        lp["beam_count_target"] = min(48, lp.get("beam_count_target", 8) + 6)
        notes.append("Stage-deck (floor) laser zone added")
    if _has(t, "side laser", "laser from sides", "side-mounted laser"):
        zones = lp.get("emission_zones", ["overhead"])
        if "side" not in zones:
            lp["emission_zones"] = zones + ["side"]
        notes.append("Side laser emission zone added")
    if _has(t, "multi-origin", "multiple origins", "many source", "all zones"):
        lp["emission_zones"] = ["overhead", "stage_deck", "side"]
        lp["beam_count_target"] = min(48, lp.get("beam_count_target", 8) + 12)
        notes.append("All emission zones activated")

    # ── Dual-layer color separation ───────────────────────────────────────
    if _has(t, "dual layer", "two layer", "split color", "upper lower color",
               "red blue layer", "color separated layer"):
        layer["enabled"] = True
        notes.append("Dual-color layer separation enabled")
    if _has(t, "red upper", "red top layer"):
        layer["enabled"] = True
        layer["upper_palette"] = "laser_red"
        notes.append("Upper layer set to red")
    if _has(t, "blue lower", "blue bottom layer"):
        layer["enabled"] = True
        layer["lower_palette"] = "laser_blue"
        notes.append("Lower layer set to blue")

    # ── Beam count ─────────────────────────────────────────────────────────
    if _has(t, "high beam count", "many beams", "lots of beams", "dense beams"):
        lp["beam_count_target"] = min(48, lp.get("beam_count_target", 8) + 16)
        notes.append("High beam count requested")

    # ── Haze dependency ───────────────────────────────────────────────────
    if _has(t, "high haze", "heavy haze", "haze-dependent", "very hazy"):
        lp["haze_dependency"] = _clamp(lp.get("haze_dependency", 0.70) + 0.25)
        ap["fog_density"] = _clamp(ap.get("fog_density", 0.5) + 0.30)
        notes.append("High haze dependency applied")

    # ── Laser palette ─────────────────────────────────────────────────────
    if _has(t, "green laser", "green only laser"):
        lp["palette"] = "green_only"
        notes.append("Laser palette: green only")
    elif _has(t, "red laser", "red only laser"):
        lp["palette"] = "red_only"
        notes.append("Laser palette: red only")
    elif _has(t, "white laser"):
        lp["palette"] = "white_only"
        notes.append("Laser palette: white only")
    elif _has(t, "magenta laser", "pink laser", "violet laser", "purple laser"):
        lp["palette"] = "magenta_only"
        notes.append("Laser palette: magenta/violet")
    elif _has(t, "rgb laser", "full color laser", "colorful laser"):
        lp["palette"] = "rgb"
        notes.append("Laser palette: full RGB")
    elif _has(t, "cool laser", "blue laser", "cold laser", "cyan laser"):
        lp["palette"] = "cool"
        notes.append("Laser palette: cool (blue/cyan)")
    elif _has(t, "warm laser", "amber laser"):
        lp["palette"] = "warm"
        notes.append("Laser palette: warm (red/yellow)")

    # ── Movement speed ────────────────────────────────────────────────────
    if _has(t, "faster laser", "more laser movement", "aggressive laser movement"):
        lp["movement_speed"] = _clamp(lp.get("movement_speed", 1.0) + 0.40, 0.0, 3.0)
        notes.append("Laser movement speed increased")
    if _has(t, "slower laser", "static laser", "less laser movement"):
        lp["movement_speed"] = _clamp(lp.get("movement_speed", 1.0) - 0.40, 0.0, 3.0)
        notes.append("Laser movement reduced")

    # ── Graceful degradation ──────────────────────────────────────────────
    if _has(t, "pyro", "firework", "confetti", "co2 jet"):
        notes.append("NOTE: physical effects not supported — approximated with "
                     "high-intensity strobe + burst laser")


def _sig_advanced(
    t: str,
    adv_laser: dict,
    adv_light: dict,
    notes: list[str],
) -> None:
    """
    Extract signals for AdvancedLaserFields and AdvancedLightFields.
    These drive fine-grained frontend rendering — they never alter cue timing.
    """
    # ── Laser plane orientation ─────────────────────────────────────────────
    if _has(t, "horizontal laser", "horizontal sheet", "horizontal beam",
               "flat laser", "low horizontal"):
        adv_laser["laser_plane_orientation"] = "horizontal"
        notes.append("Laser plane: horizontal")
    elif _has(t, "diagonal laser", "angled laser", "angled beam", "diagonal beam"):
        adv_laser["laser_plane_orientation"] = "diagonal"
        notes.append("Laser plane: diagonal")
    elif _has(t, "vertical laser", "vertical beam", "vertical curtain",
                 "curtain laser"):
        adv_laser["laser_plane_orientation"] = "vertical"
        notes.append("Laser plane: vertical curtain")
    elif _has(t, "mixed plane", "multi-plane", "mixed direction"):
        adv_laser["laser_plane_orientation"] = "mixed"
        notes.append("Laser plane: mixed orientations")

    # ── Beam edge hardness ──────────────────────────────────────────────────
    if _has(t, "sharp beam", "hard edge", "knife edge", "crisp beam",
               "tight beam edge"):
        adv_laser["beam_edge_hardness"] = min(1.0, adv_laser["beam_edge_hardness"] + 0.25)
        notes.append("Beam edge hardness increased")
    if _has(t, "soft beam", "diffuse", "soft edge", "blurry beam", "hazy beam"):
        adv_laser["beam_edge_hardness"] = max(0.0, adv_laser["beam_edge_hardness"] - 0.30)
        notes.append("Beam edge softened")

    # ── Bloom ───────────────────────────────────────────────────────────────
    if _has(t, "more bloom", "more glow", "glowing beam", "heavy bloom",
               "intense glow"):
        adv_laser["bloom_radius_estimate"] = min(1.0, adv_laser["bloom_radius_estimate"] + 0.25)
        adv_light["bloom_radius_estimate"] = min(1.0, adv_light["bloom_radius_estimate"] + 0.20)
        notes.append("Bloom / glow radius increased")
    if _has(t, "less bloom", "no bloom", "less glow", "clean beam"):
        adv_laser["bloom_radius_estimate"] = max(0.0, adv_laser["bloom_radius_estimate"] - 0.20)
        notes.append("Bloom reduced")

    # ── Laser temporal behavior ─────────────────────────────────────────────
    if _has(t, "pulsing laser", "laser pulse", "pulsed beam", "blinking laser"):
        adv_laser["laser_temporal_behavior"] = "pulse"
        notes.append("Laser temporal: pulse")
    elif _has(t, "static hold", "hold laser", "laser freeze", "frozen beam"):
        adv_laser["laser_temporal_behavior"] = "hold"
        notes.append("Laser temporal: static hold")
    elif _has(t, "sweeping laser", "sweep laser", "scanning laser"):
        adv_laser["laser_temporal_behavior"] = "sweep"
        notes.append("Laser temporal: sweep")
    elif _has(t, "alternating laser", "laser alternate", "laser flicker alternate"):
        adv_laser["laser_temporal_behavior"] = "alternate"
        notes.append("Laser temporal: alternate")
    elif _has(t, "burst laser", "explosive laser", "sudden burst"):
        adv_laser["laser_temporal_behavior"] = "burst"
        notes.append("Laser temporal: burst")

    # ── Light temporal behavior ─────────────────────────────────────────────
    if _has(t, "fading light", "slow fade", "fade in fade out", "smooth light fade"):
        adv_light["light_temporal_behavior"] = "fade"
        notes.append("Light temporal: fade")
    elif _has(t, "pulsing light", "light pulse", "strobing effect"):
        adv_light["light_temporal_behavior"] = "pulse"
        notes.append("Light temporal: pulse")
    elif _has(t, "chasing light", "light chase", "running light", "chase effect"):
        adv_light["light_temporal_behavior"] = "chase"
        notes.append("Light temporal: chase")
    elif _has(t, "reveal effect", "dramatic reveal", "build up reveal", "white reveal"):
        adv_light["light_temporal_behavior"] = "reveal"
        notes.append("Light temporal: reveal")

    # ── Spatial zone routing ────────────────────────────────────────────────
    if _has(t, "mid stage", "middle stage", "mid-stage wash"):
        if "mid_stage" not in adv_laser["spatial_zone_usage"]:
            adv_laser["spatial_zone_usage"] = adv_laser["spatial_zone_usage"] + ["mid_stage"]
        if "mid_stage" not in adv_light["spatial_zone_usage"]:
            adv_light["spatial_zone_usage"] = adv_light["spatial_zone_usage"] + ["mid_stage"]
        notes.append("Mid-stage zone activated")
    if _has(t, "side emitter", "side laser", "side light", "flank laser"):
        if "side_emitters" not in adv_laser["spatial_zone_usage"]:
            adv_laser["spatial_zone_usage"] = adv_laser["spatial_zone_usage"] + ["side_emitters"]
        notes.append("Side emitter zone activated")
    if _has(t, "all zones", "full stage", "every zone", "all around"):
        adv_laser["spatial_zone_usage"] = [
            "upper_truss", "mid_stage", "floor_emitters", "side_emitters"]
        adv_light["spatial_zone_usage"] = [
            "upper_truss", "mid_stage", "floor_emitters", "side_emitters"]
        notes.append("All spatial zones activated")

    # ── Color separation mode ───────────────────────────────────────────────
    if _has(t, "upper lower color split", "upper lower split", "top bottom color"):
        adv_laser["color_separation_mode"] = "upper_lower_split"
        notes.append("Color separation: upper/lower split")
    elif _has(t, "left right color split", "left right split", "side color split"):
        adv_laser["color_separation_mode"] = "left_right_split"
        notes.append("Color separation: left/right split")
    elif _has(t, "mixed color", "full color mix", "color mixing"):
        adv_laser["color_separation_mode"] = "mixed"
        notes.append("Color separation: mixed")

    # ── Audience reveal strength ────────────────────────────────────────────
    if _has(t, "over the crowd", "over audience", "audience laser",
               "rake the crowd", "into the crowd"):
        adv_laser["audience_reveal_strength"] = min(
            1.0, adv_laser["audience_reveal_strength"] + 0.35)
        adv_light["audience_reveal_strength"] = min(
            1.0, adv_light["audience_reveal_strength"] + 0.25)
        notes.append("Audience reveal strength increased")

    # ── Movement transition speed ───────────────────────────────────────────
    if _has(t, "snap transition", "instant snap", "hard snap", "instant cut"):
        adv_laser["movement_transition_speed"] = "snap"
        adv_light["movement_transition_speed"] = "snap"
        notes.append("Transition speed: snap")
    elif _has(t, "fast transition", "quick transition"):
        adv_laser["movement_transition_speed"] = "fast"
        adv_light["movement_transition_speed"] = "fast"
        notes.append("Transition speed: fast")
    elif _has(t, "slow transition", "very slow transition", "gradual movement"):
        adv_laser["movement_transition_speed"] = "slow"
        adv_light["movement_transition_speed"] = "slow"
        notes.append("Transition speed: slow")

    # ── Screen (backdrop) visibility ────────────────────────────────────────
    if _has(t, "visible on screen", "backdrop visibility", "screen legible"):
        adv_laser["screen_visibility_strength"] = min(
            1.0, adv_laser["screen_visibility_strength"] + 0.30)
        notes.append("Screen/backdrop visibility increased")


# ---------------------------------------------------------------------------
# Build final models from working dicts
# ---------------------------------------------------------------------------

def _build_profile(top: dict, bp: dict, mp: dict, sp: dict, ap: dict,
                    se: dict, lp: dict, layer: dict,
                    adv_laser: dict, adv_light: dict,
                    prompt_source: str, notes: list[str]) -> StyleProfile:
    return StyleProfile(
        **top,
        brightness_profile = BrightnessProfile(**bp),
        movement_profile   = MovementProfile(**mp),
        strobe_profile     = StrobeProfile(**sp),
        atmosphere_profile = AtmosphereProfile(**ap),
        section_emphasis   = SectionEmphasis(**se),
        laser_profile      = LaserProfile(
            **{k: v for k, v in lp.items() if k != "layer_profile"},
            layer_profile  = LaserLayerProfile(**layer),
        ),
        advanced_laser = AdvancedLaserFields(**adv_laser),
        advanced_light = AdvancedLightFields(**adv_light),
        prompt_source  = prompt_source,
        notes          = notes,
    )


# ---------------------------------------------------------------------------
# Public API — initial generation
# ---------------------------------------------------------------------------

def parse_prompt(prompt: str) -> StyleProfile:
    """Convert a free-text initial-generation prompt into a full StyleProfile."""
    if not prompt or not prompt.strip():
        return StyleProfile(notes=["No prompt provided; using defaults"])

    t = prompt.lower().strip()
    top       = _default_top()
    bp        = _default_bp()
    mp        = _default_mp()
    sp        = _default_sp()
    ap        = _default_ap()
    se        = _default_se()
    lp        = _default_lp()
    layer     = _default_layer()
    adv_laser = _default_adv_laser()
    adv_light = _default_adv_light()
    notes: list[str] = []

    # Named style tokens take priority; if matched, skip generic signals for
    # conflicting categories (the token already sets them)
    token_matched = False
    for token_key, triggers in _TOKEN_TRIGGERS.items():
        if _has(t, *triggers):
            _apply_token(token_key, top, bp, mp, sp, ap, se, lp, layer, notes)
            token_matched = True
            break

    # Always run generic signals so user can combine tokens + adjustments
    # e.g. "festival green fan but less strobe"
    _sig_global_feel(t, top, notes)
    if not token_matched:
        _sig_palette(t, top, notes)
    _sig_brightness(t, bp, notes)
    _sig_movement(t, mp, notes)
    _sig_strobe(t, sp, notes)
    _sig_atmosphere(t, ap, notes)
    _sig_section_emphasis(t, se, notes)
    _sig_laser(t, lp, layer, ap, notes)
    _sig_advanced(t, adv_laser, adv_light, notes)

    if not notes:
        notes.append("No specific signals detected; using defaults")

    return _build_profile(top, bp, mp, sp, ap, se, lp, layer,
                          adv_laser, adv_light, prompt, notes)


# ---------------------------------------------------------------------------
# Public API — revision
# ---------------------------------------------------------------------------

def parse_revision(revision_prompt: str, current: StyleProfile) -> StylePatch:
    """Produce a StylePatch (sparse delta) from a revision prompt."""
    t = revision_prompt.lower().strip()
    patch = StylePatch()
    notes: list[str] = []
    changed: list[str] = []

    # Global feel
    if _has(t, "more aggressive", "more intense", "harder", "more punchy"):
        patch.aggressiveness = _clamp(current.aggressiveness + 0.25)
        changed.append("aggressiveness"); notes.append("Aggressiveness increased")
    if _has(t, "less aggressive", "gentler", "softer overall", "toned down"):
        patch.aggressiveness = _clamp(current.aggressiveness - 0.25)
        changed.append("aggressiveness"); notes.append("Aggressiveness reduced")
    if _has(t, "smoother", "smooth out", "smoother overall", "less chaos"):
        patch.smoothness = _clamp(current.smoothness + 0.30)
        patch.visual_density = _clamp(current.visual_density - 0.20)
        changed += ["smoothness", "visual_density"]; notes.append("Show smoothed")
    if _has(t, "more minimal", "more restrained", "strip back", "less busy"):
        patch.restraint_level = _clamp(current.restraint_level + 0.30)
        patch.visual_density = _clamp(current.visual_density - 0.25)
        changed += ["restraint_level", "visual_density"]; notes.append("Restrained")

    # Palette
    if not _has(t, "same palette"):
        if _has(t, "cooler palette", "more blue", "bluer"):
            patch.palette = "cool"; changed.append("palette")
            notes.append("Palette shifted to cool")
        elif _has(t, "warmer palette", "more amber", "warmer"):
            patch.palette = "warm"; changed.append("palette")
            notes.append("Palette shifted to warm")

    # Brightness
    if _has(t, "brighter overall", "more brightness"):
        patch.brightness_global_scale = _clamp(
            current.brightness_profile.global_scale + 0.25, 0.0, 2.0)
        changed.append("brightness"); notes.append("Brightness increased")
    if _has(t, "dimmer overall", "less bright", "reduce brightness"):
        patch.brightness_global_scale = _clamp(
            current.brightness_profile.global_scale - 0.25, 0.0, 2.0)
        changed.append("brightness"); notes.append("Brightness reduced")

    # Movement
    if _has(t, "add more movement", "more movement", "more motion"):
        patch.movement_speed = _clamp(current.movement_profile.speed_scale + 0.35, 0.0, 3.0)
        patch.movement_range = _clamp(current.movement_profile.range_scale + 0.25, 0.0, 2.0)
        changed += ["movement"]; notes.append("Movement increased")
    if _has(t, "less movement", "reduce movement"):
        patch.movement_speed = _clamp(current.movement_profile.speed_scale - 0.35, 0.0, 3.0)
        patch.movement_range = _clamp(current.movement_profile.range_scale - 0.25, 0.0, 2.0)
        changed += ["movement"]; notes.append("Movement reduced")

    # Strobe
    if _has(t, "no strobe", "remove strobe", "disable strobe"):
        patch.strobe_enabled = False; changed.append("strobe")
        notes.append("Strobe disabled")
    elif _has(t, "reduce strobe", "less strobe"):
        patch.strobe_intensity = _clamp(
            current.strobe_profile.intensity_scale - 0.35, 0.0, 2.0)
        changed.append("strobe"); notes.append("Strobe reduced")
    elif _has(t, "more strobe", "harder strobe"):
        patch.strobe_intensity = _clamp(
            current.strobe_profile.intensity_scale + 0.35, 0.0, 2.0)
        changed.append("strobe"); notes.append("Strobe increased")

    # Drop
    if _has(t, "more intense drop", "make the drop more intense",
               "harder drop", "bigger drop"):
        patch.drop_weight = _clamp(current.section_emphasis.drop_weight + 0.40, 0.0, 2.0)
        patch.brightness_drop_scale = _clamp(
            current.brightness_profile.drop_scale + 0.25, 0.0, 2.0)
        changed += ["drop"]; notes.append("Drop amplified")

    # Breakdown
    if _has(t, "darker breakdown", "more atmospheric breakdown"):
        patch.breakdown_weight = _clamp(
            current.section_emphasis.breakdown_weight + 0.30, 0.0, 2.0)
        patch.brightness_breakdown_scale = _clamp(
            current.brightness_profile.breakdown_scale - 0.15, 0.0, 2.0)
        changed += ["breakdown"]; notes.append("Breakdown darkened")

    # Laser — keep guard
    if _has(t, "keep the lasers", "but keep the lasers", "lasers prominent"):
        pass

    # Laser — off
    if _has(t, "no laser", "remove laser", "disable laser"):
        patch.laser_enabled = False; changed.append("laser")
        notes.append("Lasers disabled")
    elif not _has(t, "keep the lasers"):
        if _has(t, "more laser", "bigger laser", "laser forward"):
            patch.laser_density = _clamp(current.laser_profile.density + 0.25)
            patch.laser_intensity = _clamp(
                current.laser_profile.intensity_scale + 0.30, 0.0, 2.0)
            patch.laser_beam_count = min(48, current.laser_profile.beam_count_target + 8)
            changed += ["laser"]; notes.append("Laser presence increased")
        elif _has(t, "less laser", "reduce laser", "subtle laser"):
            patch.laser_density = _clamp(current.laser_profile.density - 0.30)
            patch.laser_intensity = _clamp(
                current.laser_profile.intensity_scale - 0.25, 0.0, 2.0)
            changed += ["laser"]; notes.append("Laser reduced")

    # Laser — visual family & mechanics
    if _has(t, "crosshatch", "lattice laser"):
        patch.laser_crosshatch = True; changed.append("laser.crosshatch")
        notes.append("Crosshatch pattern enabled")
    if _has(t, "burst", "burst laser", "explosive"):
        patch.laser_burst_cluster = True
        patch.laser_visual_family = "laser_burst"
        changed.append("laser.visual_family"); notes.append("Burst cluster enabled")
    if _has(t, "wide fan", "wider laser", "room-wide"):
        patch.laser_fan_width = _clamp(
            current.laser_profile.fan_width_scale + 0.40, 0.0, 2.0)
        changed.append("laser.fan_width"); notes.append("Fan width increased")
    if _has(t, "tighter laser", "tight accent", "sharp laser"):
        patch.laser_fan_width = _clamp(
            current.laser_profile.fan_width_scale - 0.30, 0.0, 2.0)
        changed.append("laser.fan_width"); notes.append("Lasers tightened")
    if _has(t, "laser on drop", "laser only on drop"):
        patch.laser_drops_only = True; changed.append("laser.drops_only")
        notes.append("Lasers restricted to drops")
    if _has(t, "dual layer", "add dual layer", "enable split color"):
        patch.laser_layer_enabled = True; changed.append("laser.layer")
        notes.append("Dual-layer color separation enabled")
    if _has(t, "add floor laser", "enable floor laser", "add deck laser"):
        patch.laser_emission_zones = list(set(
            current.laser_profile.emission_zones + ["stage_deck"]))
        changed.append("laser.emission_zones"); notes.append("Floor lasers activated")
    if _has(t, "add haze", "more fog", "increase haze"):
        patch.atmosphere_fog = _clamp(current.atmosphere_profile.fog_density + 0.25)
        changed.append("atmosphere.fog"); notes.append("Haze increased")
        patch.laser_haze_dependency = _clamp(
            current.laser_profile.haze_dependency + 0.20)

    # Physical effects degradation
    if _has(t, "pyro", "firework", "co2"):
        notes.append("NOTE: physical effects not supported — "
                     "approximated with strobe + burst laser")

    # Advanced laser fields
    cur_al = current.advanced_laser
    cur_ali = current.advanced_light
    if _has(t, "horizontal laser", "flat laser"):
        patch.adv_laser_plane = "horizontal"; changed.append("adv.laser_plane")
    elif _has(t, "diagonal laser", "angled laser"):
        patch.adv_laser_plane = "diagonal"; changed.append("adv.laser_plane")
    elif _has(t, "vertical laser", "curtain laser"):
        patch.adv_laser_plane = "vertical"; changed.append("adv.laser_plane")
    elif _has(t, "mixed plane"):
        patch.adv_laser_plane = "mixed"; changed.append("adv.laser_plane")

    if _has(t, "hard beam", "sharp beam", "knife edge"):
        patch.adv_laser_edge_hardness = min(1.0, cur_al.beam_edge_hardness + 0.25)
        changed.append("adv.beam_edge_hardness")
        notes.append("Beam edge hardness increased")
    if _has(t, "soft beam", "diffuse beam"):
        patch.adv_laser_edge_hardness = max(0.0, cur_al.beam_edge_hardness - 0.25)
        changed.append("adv.beam_edge_hardness")
        notes.append("Beam edge softened")

    if _has(t, "pulsing laser", "laser pulse"):
        patch.adv_laser_temporal = "pulse"
        changed.append("adv.laser_temporal"); notes.append("Laser temporal: pulse")
    elif _has(t, "hold laser", "static laser hold"):
        patch.adv_laser_temporal = "hold"
        changed.append("adv.laser_temporal"); notes.append("Laser temporal: hold")
    elif _has(t, "burst laser", "explosive laser"):
        patch.adv_laser_temporal = "burst"
        changed.append("adv.laser_temporal"); notes.append("Laser temporal: burst")

    if _has(t, "snap transition", "instant snap"):
        patch.adv_laser_transition_spd = "snap"
        patch.adv_light_transition_spd = "snap"
        changed.append("adv.transition_speed"); notes.append("Transition speed: snap")
    elif _has(t, "slow transition", "gradual movement"):
        patch.adv_laser_transition_spd = "slow"
        patch.adv_light_transition_spd = "slow"
        changed.append("adv.transition_speed"); notes.append("Transition speed: slow")

    if _has(t, "fading light", "light fade"):
        patch.adv_light_temporal = "fade"
        changed.append("adv.light_temporal"); notes.append("Light temporal: fade")
    elif _has(t, "chasing light", "chase effect"):
        patch.adv_light_temporal = "chase"
        changed.append("adv.light_temporal"); notes.append("Light temporal: chase")
    elif _has(t, "reveal effect", "dramatic reveal"):
        patch.adv_light_temporal = "reveal"
        changed.append("adv.light_temporal"); notes.append("Light temporal: reveal")

    if _has(t, "upper lower color split", "top bottom split"):
        patch.adv_laser_color_sep = "upper_lower_split"
        changed.append("adv.color_sep"); notes.append("Color sep: upper/lower")
    elif _has(t, "left right color split"):
        patch.adv_laser_color_sep = "left_right_split"
        changed.append("adv.color_sep"); notes.append("Color sep: left/right")

    if _has(t, "more bloom", "more glow"):
        patch.adv_laser_bloom = min(1.0, cur_al.bloom_radius_estimate + 0.25)
        patch.adv_light_bloom = min(1.0, cur_ali.bloom_radius_estimate + 0.20)
        changed.append("adv.bloom"); notes.append("Bloom increased")
    if _has(t, "less bloom", "no bloom"):
        patch.adv_laser_bloom = max(0.0, cur_al.bloom_radius_estimate - 0.20)
        changed.append("adv.bloom"); notes.append("Bloom reduced")

    if not changed:
        notes.append("No changes detected — existing style preserved")

    patch.changed_fields = changed
    patch.notes = notes
    return patch


# ---------------------------------------------------------------------------
# Apply a StylePatch onto a StyleProfile → new StyleProfile
# ---------------------------------------------------------------------------

def apply_patch(patch: StylePatch, current: StyleProfile,
                revision_prompt: str) -> StyleProfile:
    """Merge a StylePatch into the current StyleProfile. Original not mutated."""
    top = dict(aggressiveness=current.aggressiveness, smoothness=current.smoothness,
               festival_scale_bias=current.festival_scale_bias,
               restraint_level=current.restraint_level,
               visual_density=current.visual_density, palette=current.palette)
    bp = current.brightness_profile.model_dump()
    mp = current.movement_profile.model_dump()
    sp = current.strobe_profile.model_dump()
    ap = current.atmosphere_profile.model_dump()
    se = current.section_emphasis.model_dump()
    lp = current.laser_profile.model_dump(exclude={"layer_profile"})
    layer     = current.laser_profile.layer_profile.model_dump()
    adv_laser = current.advanced_laser.model_dump()
    adv_light = current.advanced_light.model_dump()

    for field in ("aggressiveness", "smoothness", "festival_scale_bias",
                  "restraint_level", "visual_density"):
        v = getattr(patch, field)
        if v is not None: top[field] = v
    if patch.palette is not None: top["palette"] = patch.palette

    if patch.brightness_global_scale    is not None: bp["global_scale"]    = patch.brightness_global_scale
    if patch.brightness_drop_scale      is not None: bp["drop_scale"]      = patch.brightness_drop_scale
    if patch.brightness_build_scale     is not None: bp["build_scale"]     = patch.brightness_build_scale
    if patch.brightness_breakdown_scale is not None: bp["breakdown_scale"] = patch.brightness_breakdown_scale
    if patch.brightness_intro_scale     is not None: bp["intro_scale"]     = patch.brightness_intro_scale

    if patch.movement_enabled is not None: mp["enabled"]     = patch.movement_enabled
    if patch.movement_speed   is not None: mp["speed_scale"] = patch.movement_speed
    if patch.movement_range   is not None: mp["range_scale"] = patch.movement_range

    if patch.strobe_enabled    is not None: sp["enabled"]           = patch.strobe_enabled
    if patch.strobe_intensity  is not None: sp["intensity_scale"]   = patch.strobe_intensity
    if patch.strobe_drops_only is not None: sp["restrict_to_drops"] = patch.strobe_drops_only

    if patch.atmosphere_style is not None: ap["style"]       = patch.atmosphere_style
    if patch.atmosphere_fog   is not None: ap["fog_density"] = patch.atmosphere_fog

    if patch.drop_weight      is not None: se["drop_weight"]      = patch.drop_weight
    if patch.build_weight     is not None: se["build_weight"]     = patch.build_weight
    if patch.breakdown_weight is not None: se["breakdown_weight"] = patch.breakdown_weight

    if patch.laser_enabled      is not None: lp["enabled"]           = patch.laser_enabled
    if patch.laser_density      is not None: lp["density"]           = patch.laser_density
    if patch.laser_intensity    is not None: lp["intensity_scale"]   = patch.laser_intensity
    if patch.laser_palette      is not None: lp["palette"]           = patch.laser_palette
    if patch.laser_movement     is not None: lp["movement_speed"]    = patch.laser_movement
    if patch.laser_range        is not None: lp["movement_range"]    = patch.laser_range
    if patch.laser_fan_width    is not None: lp["fan_width_scale"]   = patch.laser_fan_width
    if patch.laser_drops_only   is not None: lp["restrict_to_drops"] = patch.laser_drops_only
    if patch.laser_chase_intens is not None: lp["chase_intensity"]   = patch.laser_chase_intens
    if patch.laser_beam_count   is not None: lp["beam_count_target"] = patch.laser_beam_count
    if patch.laser_visual_family   is not None: lp["visual_family"]   = patch.laser_visual_family
    if patch.laser_burst_cluster   is not None: lp["burst_cluster"]   = patch.laser_burst_cluster
    if patch.laser_crosshatch      is not None: lp["crosshatch"]      = patch.laser_crosshatch
    if patch.laser_haze_dependency is not None: lp["haze_dependency"] = patch.laser_haze_dependency
    if patch.laser_emission_zones  is not None: lp["emission_zones"]  = patch.laser_emission_zones
    if patch.laser_layer_enabled   is not None: layer["enabled"]       = patch.laser_layer_enabled
    if patch.laser_layer_upper_pal is not None: layer["upper_palette"] = patch.laser_layer_upper_pal
    if patch.laser_layer_lower_pal is not None: layer["lower_palette"] = patch.laser_layer_lower_pal

    # Advanced laser field patches
    if patch.adv_laser_plane          is not None: adv_laser["laser_plane_orientation"]   = patch.adv_laser_plane
    if patch.adv_laser_open_angle     is not None: adv_laser["laser_open_angle_degrees"]  = patch.adv_laser_open_angle
    if patch.adv_laser_spatial_zones  is not None: adv_laser["spatial_zone_usage"]        = patch.adv_laser_spatial_zones
    if patch.adv_laser_edge_hardness  is not None: adv_laser["beam_edge_hardness"]        = patch.adv_laser_edge_hardness
    if patch.adv_laser_bloom          is not None: adv_laser["bloom_radius_estimate"]     = patch.adv_laser_bloom
    if patch.adv_laser_haze_density   is not None: adv_laser["haze_density_estimate"]     = patch.adv_laser_haze_density
    if patch.adv_laser_src_legibility is not None: adv_laser["source_legibility_score"]   = patch.adv_laser_src_legibility
    if patch.adv_laser_audience_rev   is not None: adv_laser["audience_reveal_strength"]  = patch.adv_laser_audience_rev
    if patch.adv_laser_screen_vis     is not None: adv_laser["screen_visibility_strength"]= patch.adv_laser_screen_vis
    if patch.adv_laser_temporal       is not None: adv_laser["laser_temporal_behavior"]   = patch.adv_laser_temporal
    if patch.adv_laser_transition_spd is not None: adv_laser["movement_transition_speed"] = patch.adv_laser_transition_spd
    if patch.adv_laser_color_sep      is not None: adv_laser["color_separation_mode"]     = patch.adv_laser_color_sep

    # Advanced light field patches
    if patch.adv_light_temporal       is not None: adv_light["light_temporal_behavior"]   = patch.adv_light_temporal
    if patch.adv_light_transition_spd is not None: adv_light["movement_transition_speed"] = patch.adv_light_transition_spd
    if patch.adv_light_spatial_zones  is not None: adv_light["spatial_zone_usage"]        = patch.adv_light_spatial_zones
    if patch.adv_light_bloom          is not None: adv_light["bloom_radius_estimate"]     = patch.adv_light_bloom
    if patch.adv_light_audience_rev   is not None: adv_light["audience_reveal_strength"]  = patch.adv_light_audience_rev

    combined_notes = list(current.notes) + patch.notes
    return _build_profile(top, bp, mp, sp, ap, se, lp, layer,
                          adv_laser, adv_light, revision_prompt, combined_notes)
