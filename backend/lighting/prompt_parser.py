"""
lighting/prompt_parser.py

Deterministic, keyword-based prompt → StyleProfile / StylePatch converter.

Design goals:
  - No LLM dependency — purely rule-based so output is inspectable and testable.
  - Every change is recorded in the notes list for frontend display.
  - Initial generation: parse_prompt() → full StyleProfile (from defaults).
  - Revision:           parse_revision() → StylePatch (delta only).

Signal matching strategy:
  Each category has a set of trigger phrases (any-match) and optional
  suppressor phrases (negation).  Matched signals mutate a working config
  dict; the final dict is used to construct the Pydantic models.

Clamp helper: _clamp(value, lo, hi) ensures fields stay in range.
"""

from __future__ import annotations

from backend.schemas.style import (
    AtmosphereProfile,
    BrightnessProfile,
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
    """True if any phrase appears in text."""
    return any(p in text for p in phrases)


def _has_all(text: str, *phrases: str) -> bool:
    """True if ALL phrases appear in text."""
    return all(p in text for p in phrases)


def _modifier(text: str) -> float:
    """
    Scan for amplifying / diminishing modifiers near a keyword.
    Returns a signed delta to apply to a [0,1] scale.
    """
    if _has(text, "very ", "extremely ", "super ", "massive ", "brutal ", "maximum "):
        return 0.35
    if _has(text, "more ", "more\n", "bigger ", "higher ", "heavier ", "stronger "):
        return 0.20
    if _has(text, "slightly ", "a bit ", "a little ", "somewhat "):
        return 0.10
    if _has(text, "less ", "fewer ", "reduce ", "lower ", "softer ", "lighter "):
        return -0.20
    if _has(text, "much less ", "way less ", "significantly less ", "minimal "):
        return -0.35
    return 0.0


# ---------------------------------------------------------------------------
# Default working dicts (mirrors StyleProfile field defaults)
# ---------------------------------------------------------------------------

def _default_top() -> dict:
    return dict(
        aggressiveness=0.50,
        smoothness=0.50,
        festival_scale_bias=0.50,
        restraint_level=0.30,
        visual_density=0.70,
        palette="auto",
    )


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
    return dict(enabled=True, density=0.70, intensity_scale=1.0,
                palette="auto", movement_speed=1.0, movement_range=1.0,
                fan_width_scale=1.0, restrict_to_drops=False,
                chase_intensity=1.0)


# ---------------------------------------------------------------------------
# Signal extractors — each receives the working dicts and mutates them
# ---------------------------------------------------------------------------

def _sig_global_feel(t: str, top: dict, notes: list[str]) -> None:
    # Dark / moody / underground
    if _has(t, "dark ", "darker", "dim ", "warehouse", "underground",
               "industrial", "gothic", "gloomy"):
        top["aggressiveness"] = _clamp(top["aggressiveness"] - 0.10)
        top["restraint_level"] = _clamp(top["restraint_level"] + 0.20)
        notes.append("Dark atmosphere: reduced aggressiveness, higher restraint")

    # Intense / aggressive
    if _has(t, "aggressive", "intense", "hard ", "heavy", "punchy",
               "brutal", "violent", "high energy", "high-energy", "energetic"):
        top["aggressiveness"] = _clamp(top["aggressiveness"] + 0.30)
        top["smoothness"] = _clamp(top["smoothness"] - 0.20)
        notes.append("High aggressiveness mode applied")

    # Smooth / soft / gentle
    if _has(t, "smooth", "soft", "gentle", "flowing", "mellow",
               "relaxed", "laid-back", "laid back", "chill"):
        top["smoothness"] = _clamp(top["smoothness"] + 0.30)
        top["aggressiveness"] = _clamp(top["aggressiveness"] - 0.20)
        notes.append("Smooth / soft style applied")

    # Festival / epic / huge
    if _has(t, "festival", "massive", "epic", "stadium", "mainstage",
               "main stage", "huge", "grandiose"):
        top["festival_scale_bias"] = _clamp(top["festival_scale_bias"] + 0.35)
        top["visual_density"] = _clamp(top["visual_density"] + 0.20)
        notes.append("Festival scale bias increased")

    # Minimal / sparse / restrained
    if _has(t, "minimal", "minimalist", "subtle", "restrained", "sparse",
               "simple ", "clean ", "stripped"):
        top["restraint_level"] = _clamp(top["restraint_level"] + 0.35)
        top["visual_density"] = _clamp(top["visual_density"] - 0.30)
        notes.append("Minimal / sparse style applied")

    # Cinematic
    if _has(t, "cinematic", "film", "movie", "dramatic arc"):
        top["smoothness"] = _clamp(top["smoothness"] + 0.25)
        top["festival_scale_bias"] = _clamp(top["festival_scale_bias"] - 0.10)
        notes.append("Cinematic style: smoother transitions")

    # Busy / dense
    if _has(t, "busy", "dense", "full ", "packed", "saturated show"):
        top["visual_density"] = _clamp(top["visual_density"] + 0.25)
        top["restraint_level"] = _clamp(top["restraint_level"] - 0.20)
        notes.append("High visual density applied")


def _sig_palette(t: str, top: dict, notes: list[str]) -> None:
    # Cool / blue / purple
    if _has(t, "cool tone", "cold ", "icy ", "blue and purple",
               "blue tones", "cool blue", "cool palette", "blue/purple", "violet"):
        top["palette"] = "cool"
        notes.append("Cool color palette selected")
    # Warm / amber / orange
    elif _has(t, "warm tone", "warm palette", "golden", "amber", "orange tone",
                 "warm lighting", "warm feel"):
        top["palette"] = "warm"
        notes.append("Warm color palette selected")
    # Monochrome
    elif _has(t, "monochrome", "single color", "one color", "mono "):
        top["palette"] = "monochrome"
        notes.append("Monochrome palette selected")
    # Explicit color hints (lower priority — don't override explicit palette words)
    elif _has(t, " blue", " purple"):
        top["palette"] = "cool"
        notes.append("Cool palette inferred from color mention")
    elif _has(t, " amber", " orange", " red tone"):
        top["palette"] = "warm"
        notes.append("Warm palette inferred from color mention")


def _sig_brightness(t: str, bp: dict, notes: list[str]) -> None:
    if _has(t, "brighter", "more bright", "higher brightness", "brighten"):
        delta = 0.25
        for k in ("global_scale", "intro_scale", "build_scale",
                  "drop_scale", "breakdown_scale", "outro_scale"):
            bp[k] = _clamp(bp[k] + delta, 0.0, 2.0)
        notes.append("Global brightness increased")

    if _has(t, "dim ", "darker", "lower brightness", "dimmer"):
        delta = -0.25
        for k in ("global_scale", "intro_scale", "build_scale",
                  "drop_scale", "breakdown_scale", "outro_scale"):
            bp[k] = _clamp(bp[k] + delta, 0.0, 2.0)
        notes.append("Global brightness reduced")


def _sig_movement(t: str, mp: dict, notes: list[str]) -> None:
    disabled = _has(t, "no movement", "static show", "no motion", "disable movement",
                       "no sweep", "without movement")
    if disabled:
        mp["enabled"] = False
        notes.append("Movement disabled")
        return

    if _has(t, "more movement", "more motion", "faster sweep", "faster pan",
               "wild movement", "more sweep", "fast movement", "rapid movement"):
        mp["speed_scale"] = _clamp(mp["speed_scale"] + 0.40, 0.0, 3.0)
        mp["range_scale"] = _clamp(mp["range_scale"] + 0.30, 0.0, 2.0)
        notes.append("Movement speed and range increased")

    if _has(t, "less movement", "less motion", "slower movement", "subtle movement",
               "minimal movement", "reduce movement"):
        mp["speed_scale"] = _clamp(mp["speed_scale"] - 0.40, 0.0, 3.0)
        mp["range_scale"] = _clamp(mp["range_scale"] - 0.25, 0.0, 2.0)
        notes.append("Movement speed and range reduced")

    if _has(t, "slow drift", "slow movement", "very slow"):
        mp["speed_scale"] = _clamp(mp["speed_scale"] - 0.50, 0.0, 3.0)
        mp["transition_style"] = "fade"
        notes.append("Slow drift movement applied")

    if _has(t, "sharp movement", "hard cut movement", "snapping", "fast snap"):
        mp["transition_style"] = "snap"
        notes.append("Snap movement transitions applied")

    if _has(t, "smooth transition", "soft transition", "gentle transition"):
        mp["transition_style"] = "fade"
        notes.append("Fade movement transitions applied")


def _sig_strobe(t: str, sp: dict, notes: list[str]) -> None:
    # Disable
    if _has(t, "no strobe", "remove strobe", "disable strobe", "without strobe"):
        sp["enabled"] = False
        notes.append("Strobe disabled")
        return

    # Restrict to drops
    if _has(t, "strobe only on drop", "strobe on drop", "drop strobe only",
               "strobe at drop"):
        sp["restrict_to_drops"] = True
        notes.append("Strobe restricted to drop sections")

    # More strobe
    if _has(t, "more strobe", "heavy strobe", "brighter strobe",
               "harder strobe", "bigger flash", "more flash"):
        sp["intensity_scale"] = _clamp(sp["intensity_scale"] + 0.35, 0.0, 2.0)
        sp["rate_scale"] = _clamp(sp["rate_scale"] + 0.25, 0.0, 2.0)
        notes.append("Strobe intensity and rate increased")

    # Less strobe
    if _has(t, "less strobe", "fewer strobe", "reduce strobe",
               "lighter strobe", "softer flash", "minimal strobe"):
        sp["intensity_scale"] = _clamp(sp["intensity_scale"] - 0.35, 0.0, 2.0)
        sp["rate_scale"] = _clamp(sp["rate_scale"] - 0.25, 0.0, 2.0)
        notes.append("Strobe intensity and rate reduced")


def _sig_atmosphere(t: str, ap: dict, notes: list[str]) -> None:
    if _has(t, "dark atmosphere", "dark mood", "warehouse feel", "underground feel"):
        ap["style"] = "dark"
        ap["fog_density"] = _clamp(ap["fog_density"] + 0.20)
        notes.append("Dark atmosphere style applied")
    elif _has(t, "warm atmosphere", "warm feel", "warm mood"):
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

    if _has(t, "more haze", "more fog", "foggy", "smoky"):
        ap["fog_density"] = _clamp(ap["fog_density"] + 0.30)
        notes.append("Fog density increased")

    if _has(t, "slow fade", "slow transition", "gradual"):
        ap["fade_speed"] = "slow"
        notes.append("Slow fade speed applied")

    if _has(t, "fast fade", "fast transition", "quick transition"):
        ap["fade_speed"] = "fast"
        notes.append("Fast fade speed applied")


def _sig_section_emphasis(t: str, se: dict, notes: list[str]) -> None:
    # Drop emphasis
    if _has(t, "bigger drop", "more intense drop", "emphasize drop",
               "harder drop", "aggressive drop", "drop more intense"):
        se["drop_weight"] = _clamp(se["drop_weight"] + 0.40, 0.0, 2.0)
        notes.append("Drop section emphasis increased")

    # Breakdown emphasis
    if _has(t, "darker breakdown", "atmospheric breakdown",
               "moody breakdown", "deep breakdown"):
        se["breakdown_weight"] = _clamp(se["breakdown_weight"] + 0.30, 0.0, 2.0)
        notes.append("Breakdown section emphasis increased")

    # Build emphasis
    if _has(t, "bigger build", "more intense build", "heavier build",
               "tighter build", "more anticipation"):
        se["build_weight"] = _clamp(se["build_weight"] + 0.30, 0.0, 2.0)
        notes.append("Build section emphasis increased")


def _sig_laser(t: str, lp: dict, notes: list[str]) -> None:
    # Disable
    if _has(t, "no laser", "remove laser", "disable laser", "without laser"):
        lp["enabled"] = False
        notes.append("Lasers disabled")
        return

    # Restrict to drops
    if _has(t, "laser only on drop", "laser on drop", "drop laser only",
               "laser accent on drop", "laser at drop", "laser accents only on"):
        lp["restrict_to_drops"] = True
        notes.append("Lasers restricted to drop sections")

    # More laser
    if _has(t, "more laser", "prominent laser", "heavy laser",
               "laser heavy", "bigger laser", "laser forward",
               "laser prominent", "bold laser"):
        lp["density"] = _clamp(lp["density"] + 0.25)
        lp["intensity_scale"] = _clamp(lp["intensity_scale"] + 0.30, 0.0, 2.0)
        notes.append("Laser density and intensity increased")

    # Less laser
    if _has(t, "less laser", "fewer laser", "reduce laser",
               "subtle laser", "minimal laser", "lighter laser"):
        lp["density"] = _clamp(lp["density"] - 0.30)
        lp["intensity_scale"] = _clamp(lp["intensity_scale"] - 0.25, 0.0, 2.0)
        notes.append("Laser density and intensity reduced")

    # Fan / spread
    if _has(t, "wide fan", "wide laser", "wide beam", "broad laser", "spread laser"):
        lp["fan_width_scale"] = _clamp(lp["fan_width_scale"] + 0.40, 0.0, 2.0)
        notes.append("Laser fan width increased")

    if _has(t, "tight laser", "sharp laser", "narrow laser",
               "sharp accent", "tight beam"):
        lp["fan_width_scale"] = _clamp(lp["fan_width_scale"] - 0.30, 0.0, 2.0)
        notes.append("Laser fan width reduced (tighter beams)")

    # Movement
    if _has(t, "faster laser", "more laser movement", "aggressive laser movement"):
        lp["movement_speed"] = _clamp(lp["movement_speed"] + 0.40, 0.0, 3.0)
        notes.append("Laser movement speed increased")

    if _has(t, "slower laser", "slower laser movement", "less laser movement",
               "static laser"):
        lp["movement_speed"] = _clamp(lp["movement_speed"] - 0.40, 0.0, 3.0)
        notes.append("Laser movement speed reduced")

    # Explicit palette
    if _has(t, "green laser", "green only laser"):
        lp["palette"] = "green_only"
        notes.append("Laser palette: green only")
    elif _has(t, "red laser", "red only laser"):
        lp["palette"] = "red_only"
        notes.append("Laser palette: red only")
    elif _has(t, "white laser", "white only laser"):
        lp["palette"] = "white_only"
        notes.append("Laser palette: white only")
    elif _has(t, "rgb laser", "full color laser", "colorful laser"):
        lp["palette"] = "rgb"
        notes.append("Laser palette: full RGB")
    elif _has(t, "cool laser", "blue laser", "cold laser"):
        lp["palette"] = "cool"
        notes.append("Laser palette: cool (blue/cyan)")
    elif _has(t, "warm laser", "amber laser", "red/yellow laser"):
        lp["palette"] = "warm"
        notes.append("Laser palette: warm (red/yellow)")

    # Graceful degradation — unsupported requests
    if _has(t, "pyro", "firework", "confetti", "co2 jet", "water"):
        notes.append(
            "NOTE: pyrotechnics / physical effects not supported — "
            "approximated with high-intensity strobe + laser burst"
        )


# ---------------------------------------------------------------------------
# Public API — initial generation
# ---------------------------------------------------------------------------

def parse_prompt(prompt: str) -> StyleProfile:
    """
    Convert a free-text initial-generation prompt into a full StyleProfile.
    Starts from default values and applies all matched signals.
    """
    if not prompt or not prompt.strip():
        return StyleProfile(notes=["No prompt provided; using defaults"])

    t = prompt.lower().strip()
    top  = _default_top()
    bp   = _default_bp()
    mp   = _default_mp()
    sp   = _default_sp()
    ap   = _default_ap()
    se   = _default_se()
    lp   = _default_lp()
    notes: list[str] = []

    _sig_global_feel(t, top, notes)
    _sig_palette(t, top, notes)
    _sig_brightness(t, bp, notes)
    _sig_movement(t, mp, notes)
    _sig_strobe(t, sp, notes)
    _sig_atmosphere(t, ap, notes)
    _sig_section_emphasis(t, se, notes)
    _sig_laser(t, lp, notes)

    if not notes:
        notes.append("No specific signals detected; using defaults")

    return StyleProfile(
        **top,
        brightness_profile=BrightnessProfile(**bp),
        movement_profile=MovementProfile(**mp),
        strobe_profile=StrobeProfile(**sp),
        atmosphere_profile=AtmosphereProfile(**ap),
        section_emphasis=SectionEmphasis(**se),
        laser_profile=LaserProfile(**lp),
        prompt_source=prompt,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Public API — revision
# ---------------------------------------------------------------------------

def parse_revision(revision_prompt: str, current: StyleProfile) -> StylePatch:
    """
    Produce a StylePatch (sparse delta) from a revision prompt applied on top
    of the current StyleProfile.  Only fields that should change are set;
    all others are None (meaning "keep current value").
    """
    t = revision_prompt.lower().strip()
    patch = StylePatch()
    notes: list[str] = []
    changed: list[str] = []

    # ── Global feel ────────────────────────────────────────────────────────
    if _has(t, "more aggressive", "more intense", "harder", "more punchy",
               "heavier overall"):
        patch.aggressiveness = _clamp(current.aggressiveness + 0.25)
        changed.append("aggressiveness")
        notes.append("Aggressiveness increased")

    if _has(t, "less aggressive", "gentler", "softer overall",
               "more gentle", "toned down"):
        patch.aggressiveness = _clamp(current.aggressiveness - 0.25)
        changed.append("aggressiveness")
        notes.append("Aggressiveness reduced")

    if _has(t, "smoother", "more smooth", "slow everything", "smooth out",
               "smoother overall", "less chaos", "less chaotic"):
        patch.smoothness = _clamp(current.smoothness + 0.30)
        patch.visual_density = _clamp(current.visual_density - 0.20)
        changed += ["smoothness", "visual_density"]
        notes.append("Show smoothed out")

    if _has(t, "more minimal", "more restrained", "strip back",
               "less busy", "cleaner"):
        patch.restraint_level = _clamp(current.restraint_level + 0.30)
        patch.visual_density = _clamp(current.visual_density - 0.25)
        changed += ["restraint_level", "visual_density"]
        notes.append("Restrained further")

    if _has(t, "more density", "busier", "more visual", "add more"):
        patch.visual_density = _clamp(current.visual_density + 0.25)
        changed.append("visual_density")
        notes.append("Visual density increased")

    # ── Palette ────────────────────────────────────────────────────────────
    if _has(t, "same palette"):
        pass  # explicit "keep palette" — do nothing
    elif _has(t, "cooler palette", "more blue", "bluer", "more purple"):
        patch.palette = "cool"
        changed.append("palette")
        notes.append("Palette shifted to cool")
    elif _has(t, "warmer palette", "more amber", "more orange", "warmer"):
        patch.palette = "warm"
        changed.append("palette")
        notes.append("Palette shifted to warm")

    # ── Brightness ────────────────────────────────────────────────────────
    if _has(t, "brighter overall", "more brightness", "turn up brightness"):
        patch.brightness_global_scale = _clamp(
            current.brightness_profile.global_scale + 0.25, 0.0, 2.0)
        changed.append("brightness.global_scale")
        notes.append("Global brightness increased")

    if _has(t, "dimmer overall", "less bright", "turn down brightness",
               "reduce brightness"):
        patch.brightness_global_scale = _clamp(
            current.brightness_profile.global_scale - 0.25, 0.0, 2.0)
        changed.append("brightness.global_scale")
        notes.append("Global brightness reduced")

    # ── Movement ──────────────────────────────────────────────────────────
    if _has(t, "keep the same palette but add more movement",
               "add more movement", "more movement", "more motion"):
        patch.movement_speed = _clamp(
            current.movement_profile.speed_scale + 0.35, 0.0, 3.0)
        patch.movement_range = _clamp(
            current.movement_profile.range_scale + 0.25, 0.0, 2.0)
        changed += ["movement.speed_scale", "movement.range_scale"]
        notes.append("Movement speed and range increased")

    if _has(t, "less movement", "reduce movement", "less motion"):
        patch.movement_speed = _clamp(
            current.movement_profile.speed_scale - 0.35, 0.0, 3.0)
        patch.movement_range = _clamp(
            current.movement_profile.range_scale - 0.25, 0.0, 2.0)
        changed += ["movement.speed_scale", "movement.range_scale"]
        notes.append("Movement reduced")

    # ── Strobe ────────────────────────────────────────────────────────────
    if _has(t, "reduce strobe", "less strobe", "fewer strobe",
               "remove strobe", "no strobe"):
        if _has(t, "no strobe", "remove strobe", "disable strobe"):
            patch.strobe_enabled = False
            notes.append("Strobe disabled")
        else:
            patch.strobe_intensity = _clamp(
                current.strobe_profile.intensity_scale - 0.35, 0.0, 2.0)
            notes.append("Strobe intensity reduced")
        changed.append("strobe")

    if _has(t, "more strobe", "harder strobe", "brighter strobe"):
        patch.strobe_intensity = _clamp(
            current.strobe_profile.intensity_scale + 0.35, 0.0, 2.0)
        changed.append("strobe.intensity_scale")
        notes.append("Strobe intensity increased")

    # ── Drop section ──────────────────────────────────────────────────────
    if _has(t, "more intense drop", "make the drop more intense",
               "harder drop", "bigger drop", "drop more aggressive"):
        patch.drop_weight = _clamp(
            current.section_emphasis.drop_weight + 0.40, 0.0, 2.0)
        patch.brightness_drop_scale = _clamp(
            current.brightness_profile.drop_scale + 0.25, 0.0, 2.0)
        changed += ["section_emphasis.drop_weight", "brightness.drop_scale"]
        notes.append("Drop intensity amplified")

    # ── Breakdown section ─────────────────────────────────────────────────
    if _has(t, "darker breakdown", "more atmospheric breakdown",
               "make the breakdown darker", "more moody breakdown"):
        patch.breakdown_weight = _clamp(
            current.section_emphasis.breakdown_weight + 0.30, 0.0, 2.0)
        patch.brightness_breakdown_scale = _clamp(
            current.brightness_profile.breakdown_scale - 0.15, 0.0, 2.0)
        changed += ["section_emphasis.breakdown_weight", "brightness.breakdown_scale"]
        notes.append("Breakdown darkened and made more atmospheric")

    # ── Laser ─────────────────────────────────────────────────────────────
    if _has(t, "keep the lasers", "keep lasers prominent",
               "but keep the lasers", "lasers prominent"):
        pass  # explicit keep — leave laser fields as None

    if _has(t, "no laser", "remove laser", "disable laser"):
        patch.laser_enabled = False
        changed.append("laser.enabled")
        notes.append("Lasers disabled")

    elif _has(t, "more laser", "laser more prominent", "add more laser",
                 "bigger laser", "laser forward"):
        patch.laser_density = _clamp(current.laser_profile.density + 0.25)
        patch.laser_intensity = _clamp(
            current.laser_profile.intensity_scale + 0.30, 0.0, 2.0)
        changed += ["laser.density", "laser.intensity_scale"]
        notes.append("Laser presence increased")

    elif _has(t, "less laser", "fewer laser", "reduce laser",
                 "subtle laser", "minimal laser"):
        if not _has(t, "keep the lasers"):
            patch.laser_density = _clamp(current.laser_profile.density - 0.30)
            patch.laser_intensity = _clamp(
                current.laser_profile.intensity_scale - 0.25, 0.0, 2.0)
            changed += ["laser.density", "laser.intensity_scale"]
            notes.append("Laser presence reduced")

    if _has(t, "laser accent", "tighter laser", "sharp laser",
               "tight laser accent"):
        patch.laser_fan_width = _clamp(
            current.laser_profile.fan_width_scale - 0.30, 0.0, 2.0)
        changed.append("laser.fan_width_scale")
        notes.append("Laser beams tightened for accents")

    if _has(t, "laser on drop", "laser only on drop",
               "laser accents only on", "restrict laser to drop"):
        patch.laser_drops_only = True
        changed.append("laser.restrict_to_drops")
        notes.append("Lasers restricted to drop sections")

    if _has(t, "wide laser", "wider laser fan", "spread laser"):
        patch.laser_fan_width = _clamp(
            current.laser_profile.fan_width_scale + 0.35, 0.0, 2.0)
        changed.append("laser.fan_width_scale")
        notes.append("Laser fan width increased")

    # Graceful degradation
    if _has(t, "pyro", "firework", "confetti", "co2"):
        notes.append(
            "NOTE: physical effects not supported — "
            "approximated with enhanced strobe + laser burst at drop"
        )

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
    """
    Merge a StylePatch into the current StyleProfile.
    Returns a brand-new StyleProfile; the original is not mutated.
    Only non-None patch fields are applied.
    """
    # Snapshot current sub-profile dicts
    top = dict(
        aggressiveness      = current.aggressiveness,
        smoothness          = current.smoothness,
        festival_scale_bias = current.festival_scale_bias,
        restraint_level     = current.restraint_level,
        visual_density      = current.visual_density,
        palette             = current.palette,
    )
    bp = current.brightness_profile.model_dump()
    mp = current.movement_profile.model_dump()
    sp = current.strobe_profile.model_dump()
    ap = current.atmosphere_profile.model_dump()
    se = current.section_emphasis.model_dump()
    lp = current.laser_profile.model_dump()

    # Apply top-level scalars
    for field in ("aggressiveness", "smoothness", "festival_scale_bias",
                  "restraint_level", "visual_density"):
        v = getattr(patch, field)
        if v is not None:
            top[field] = v

    if patch.palette is not None:
        top["palette"] = patch.palette

    # Brightness
    if patch.brightness_global_scale    is not None: bp["global_scale"]    = patch.brightness_global_scale
    if patch.brightness_drop_scale      is not None: bp["drop_scale"]      = patch.brightness_drop_scale
    if patch.brightness_build_scale     is not None: bp["build_scale"]     = patch.brightness_build_scale
    if patch.brightness_breakdown_scale is not None: bp["breakdown_scale"] = patch.brightness_breakdown_scale
    if patch.brightness_intro_scale     is not None: bp["intro_scale"]     = patch.brightness_intro_scale

    # Movement
    if patch.movement_enabled is not None: mp["enabled"]      = patch.movement_enabled
    if patch.movement_speed   is not None: mp["speed_scale"]  = patch.movement_speed
    if patch.movement_range   is not None: mp["range_scale"]  = patch.movement_range

    # Strobe
    if patch.strobe_enabled    is not None: sp["enabled"]           = patch.strobe_enabled
    if patch.strobe_intensity  is not None: sp["intensity_scale"]   = patch.strobe_intensity
    if patch.strobe_drops_only is not None: sp["restrict_to_drops"] = patch.strobe_drops_only

    # Atmosphere
    if patch.atmosphere_style is not None: ap["style"]       = patch.atmosphere_style
    if patch.atmosphere_fog   is not None: ap["fog_density"] = patch.atmosphere_fog

    # Section emphasis
    if patch.drop_weight      is not None: se["drop_weight"]       = patch.drop_weight
    if patch.build_weight     is not None: se["build_weight"]      = patch.build_weight
    if patch.breakdown_weight is not None: se["breakdown_weight"]  = patch.breakdown_weight

    # Laser
    if patch.laser_enabled      is not None: lp["enabled"]           = patch.laser_enabled
    if patch.laser_density      is not None: lp["density"]           = patch.laser_density
    if patch.laser_intensity    is not None: lp["intensity_scale"]   = patch.laser_intensity
    if patch.laser_palette      is not None: lp["palette"]           = patch.laser_palette
    if patch.laser_movement     is not None: lp["movement_speed"]    = patch.laser_movement
    if patch.laser_range        is not None: lp["movement_range"]    = patch.laser_range
    if patch.laser_fan_width    is not None: lp["fan_width_scale"]   = patch.laser_fan_width
    if patch.laser_drops_only   is not None: lp["restrict_to_drops"] = patch.laser_drops_only
    if patch.laser_chase_intens is not None: lp["chase_intensity"]   = patch.laser_chase_intens

    # Accumulate notes from all revisions
    combined_notes = list(current.notes) + patch.notes

    return StyleProfile(
        **top,
        brightness_profile = BrightnessProfile(**bp),
        movement_profile   = MovementProfile(**mp),
        strobe_profile     = StrobeProfile(**sp),
        atmosphere_profile = AtmosphereProfile(**ap),
        section_emphasis   = SectionEmphasis(**se),
        laser_profile      = LaserProfile(**lp),
        prompt_source      = revision_prompt,
        notes              = combined_notes,
    )
