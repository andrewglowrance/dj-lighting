"""
lighting/cue_engine.py

Deterministic cue generator.

Entry point: generate_cues(timeline: TimelineSchema, template=None) → CueOutputSchema

The engine walks the section list from rules.SECTION_RULES.
For each section it iterates the rule list and, depending on the trigger type,
emits one or more Cue objects. No randomness. Same input always produces the
same output.

When a RigTemplate is supplied, a constraint-filtering pass runs after
generation to drop or adapt cues that the rig cannot execute:

    - Cues whose cue_type is in constraints.drop_cue_types are removed.
    - Cues targeting only empty groups (fixture_count == 0) are removed,
      unless the group declares a fallback_group.
    - movement_enable cues are dropped when constraints.movement_enable=False.
    - strobe_hit cues have their duration floored to 1/strobe_max_rate_hz.

Trigger types handled:
    section_start   – one cue at section.start
    beat            – one cue per beat in the section
    beat_2_4        – one cue per beat where beat_in_bar ∈ {1, 3}
    bar_beat_1      – one cue per bar (on beat 0 of each bar)
    bar_2_beat_1    – one cue on beat 0 of every 2nd bar in the section
    bar_4_beat_1    – one cue on beat 0 of every 4th bar in the section
    build_last4     – one cue on beat 0 and beat 2 of the last 4 bars of a build
    pre_drop        – one cue on the very last beat of the section

Special parameter flags resolved at runtime:
    _ramp=True          – intensity is lerped from intensity_start to intensity_end
                          based on the beat's position within the section
    _linear_fade=True   – intensity is lerped per bar from intensity_start to intensity_end
    _drop_cycle         – color is taken from DROP_COLOR_CYCLE indexed by bar pair counter
    _build_cycle        – color is taken from BUILD_COLOR_CYCLE indexed by 4-bar counter
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from backend.lighting.rules import (
    BUILD_COLOR_CYCLE,
    DROP_COLOR_CYCLE,
    SECTION_RULES,
)
from backend.lighting.motion_vocabulary import MOTION_VOCABULARY, get_motions_for_section
from backend.lighting.beat_choreographer import plan_section, PhrasePlan
from backend.lighting.diversity_tracker import DiversityTracker
from backend.lighting.reference_dataset import (
    get_influential_segments,
    get_section_realism_priors,
    get_motion_family_bias,
)
from backend.schemas.cues import Cue, CueOutputSchema
from backend.schemas.timeline import Beat, Bar, BeatNote, Section, TimelineSchema

# Maps chromatic pitch-class index 0-11 to the note-color key in COLORS
_NOTE_COLOR_KEYS: list[str] = [
    "note_C", "note_Cs", "note_D", "note_Ds",
    "note_E", "note_F",  "note_Fs","note_G",
    "note_Gs","note_A",  "note_As","note_B",
]

# Global brightness multiplier applied as a final post-processing pass.
# Value of 1.5 raises every cue's intensity by 50 % (capped at 1.0).
# Change here to tune overall show luminosity without touching per-rule values.
_GLOBAL_INTENSITY_SCALE: float = 1.5

if TYPE_CHECKING:
    from backend.lighting.rig_loader import RigTemplate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cues(
    timeline: TimelineSchema,
    template: "RigTemplate | None" = None,
) -> CueOutputSchema:
    """
    Walk the timeline and emit deterministic lighting cues.

    Args:
        timeline – validated TimelineSchema from the analysis pipeline
        template – optional RigTemplate; when provided, constraint filtering
                   is applied after generation.

    Returns:
        CueOutputSchema – ordered by time ascending, constraints applied
    """
    beat_duration = 60.0 / timeline.bpm.bpm

    # BPM normaliser — used to scale laser speed / movement throughout the show
    bpm_s = _bpm_scale(timeline.bpm.bpm)

    # Build a stable fingerprint from BPM + duration for deterministic diversity selection
    import hashlib as _hl
    _fp = _hl.md5(
        f"{timeline.bpm.bpm:.1f}|{timeline.metadata.duration_sec:.1f}".encode()
    ).hexdigest()[:12]
    tracker = DiversityTracker(window_size=4, fingerprint=_fp)

    # Per-section choreography log (attached to output for debugging)
    section_choreography: list[dict] = []

    # Pre-build fast lookup structures
    bar_map: dict[int, Bar] = {b.index: b for b in timeline.bars}
    beat_map: dict[int, Beat] = {b.index: b for b in timeline.beats}

    # Note lookup: beat_index → BeatNote (empty dict = note-responsive rules fall back)
    beat_note_map: dict[int, BeatNote] = {
        bn.beat_index: bn for bn in (timeline.beat_notes or [])
    }

    cues: list[Cue] = []
    cue_counter = 0

    def next_id() -> str:
        nonlocal cue_counter
        cue_counter += 1
        return f"cue_{cue_counter:04d}"

    for section in timeline.sections:
        rules = SECTION_RULES.get(section.label, [])
        if not rules:
            continue

        # Section-level energy — used for macro scaling (spread, beam count, etc.)
        section_energy: float = float(section.energy_mean)

        # --- Reference-driven motion selection for this section ---
        _candidates = get_motions_for_section(section.label, section_energy, top_k=8)
        _bias = get_motion_family_bias(section.label, section_energy, _candidates)
        _motion_family = tracker.select_motion(
            _candidates,
            base_weights=_bias,
            section_index=section.bar_start,
            role="main",
        )
        _motion = MOTION_VOCABULARY.get(_motion_family)

        # Record for diversity tracking (prevents immediate reuse)
        tracker.record_section(
            motion_family=_motion_family,
            laser_pattern=(_motion.laser_params.get("cue_type") if _motion else None),
            spatial_zones=(set(_motion.primary_zones) if _motion else None),
        )

        # Realism priors for this section (attached to output + used by frontend)
        _realism = get_section_realism_priors(section.label, section_energy)

        # Beats and bars that fall within this section's time range
        section_beats = [
            b for b in timeline.beats if section.start <= b.time < section.end
        ]
        section_bars = [
            b for b in timeline.bars
            if section.bar_start <= b.index < section.bar_end
        ]

        n_beats = len(section_beats)
        n_bars = len(section_bars)

        # Level 2 + 3: phrase plan for bar-level variety and beat-level modulation
        _phrase_plan = plan_section(
            section_label  = section.label,
            motion_family  = _motion_family,
            section_energy = section_energy,
            n_bars         = n_bars,
            fingerprint    = _fp,
            section_index  = section.bar_start,
        )

        # Log for output (includes phrase schedule)
        section_choreography.append({
            "section_label":          section.label,
            "bar_start":              section.bar_start,
            "bar_end":                section.bar_end,
            "motion_family":          _motion_family,
            "section_energy":         round(section_energy, 3),
            "phrase_length_bars":     _phrase_plan.phrase_length_bars,
            "dominant_beat_behavior": _phrase_plan.dominant_beat_behavior,
            "realism_priors":         _realism,
            "candidates":             _candidates[:4],
            "phrase_schedule": [
                {
                    "phrase_index":    ps.phrase_index,
                    "bar_start":       ps.bar_start,
                    "bar_end":         ps.bar_end,
                    "motion_variant":  ps.motion_variant,
                    "beat_behavior":   ps.beat_behavior,
                    "direction":       ps.direction,
                    "color_key":       ps.color_key,
                    "spread_scale":    ps.spread_scale,
                    "density_scale":   ps.density_scale,
                    "zone_emphasis":   ps.zone_emphasis,
                    "variation_reason": ps.variation_reason,
                }
                for ps in _phrase_plan.phrases
            ],
        })

        for rule in rules:
            trigger = rule["trigger"]
            cue_type = rule["cue_type"]
            target_groups = rule["target_groups"]
            params_template = rule["params"]

            def _duration(beat_t: float = beat_duration) -> float:
                """Resolve duration from rule spec, in seconds."""
                if rule.get("fill_section"):
                    return max(section.end - section.start, 0.1)
                if "duration_sec" in rule:
                    return float(rule["duration_sec"])
                beats = rule.get("duration_beats", 1.0)
                return float(beats) * beat_t

            # ----------------------------------------------------------
            if trigger == "section_start":
                resolved = _resolve_params(
                    params_template, beat_idx=0, n_beats=1, bar_idx=0, n_bars=1)
                # Apply motion vocabulary override if vocabulary defines this cue type
                if _motion:
                    if cue_type == "movement_enable" and _motion.movement_params:
                        resolved = {**resolved, **_motion.movement_params}
                    elif cue_type in ("laser_static", "laser_scan", "laser_chase") and _motion.laser_params:
                        vocab_laser = _motion.laser_params
                        vocab_cue_type = vocab_laser.get("cue_type", "")
                        if vocab_cue_type == cue_type or not vocab_cue_type:
                            resolved = {**resolved, **{k: v for k, v in vocab_laser.items() if k != "cue_type"}}
                # Always inject motion_family into params so frontend can use it
                resolved["motion_family"] = _motion_family
                resolved = _apply_energy_scale(
                    resolved, cue_type, bpm_s, section_energy, section_energy)
                cues.append(_make_cue(
                    id=next_id(),
                    time=section.start,
                    duration=_duration(),
                    cue_type=cue_type,
                    section=section.label,
                    trigger=trigger,
                    target_groups=target_groups,
                    params=resolved,
                ))

            # ----------------------------------------------------------
            elif trigger == "beat":
                for i, beat in enumerate(section_beats):
                    resolved = _resolve_params(
                        params_template, beat_idx=i, n_beats=n_beats)
                    beat_note = beat_note_map.get(beat.index)
                    resolved, dur_override = _apply_note_color(
                        resolved, rule, beat_note, beat_duration)
                    beat_energy = (
                        beat_note.rms_energy if beat_note else section_energy)
                    resolved = _apply_energy_scale(
                        resolved, cue_type, bpm_s, section_energy, beat_energy)
                    # Level 3: beat modulation from phrase plan
                    _bar_idx_in_sect = max(0, beat.bar_index - section.bar_start)
                    _beat_mod = _phrase_plan.get_beat_modulation(
                        beat.beat_in_bar, _bar_idx_in_sect, beat_energy)
                    resolved = _apply_beat_modulation(resolved, _beat_mod, cue_type)
                    cues.append(_make_cue(
                        id=next_id(),
                        time=beat.time,
                        duration=dur_override if dur_override is not None else _duration(),
                        cue_type=cue_type,
                        section=section.label,
                        trigger=trigger,
                        target_groups=target_groups,
                        params=resolved,
                    ))

            # ----------------------------------------------------------
            elif trigger == "beat_2_4":
                for beat in section_beats:
                    if beat.beat_in_bar in (1, 3):
                        resolved = _resolve_params(params_template)
                        beat_note = beat_note_map.get(beat.index)
                        resolved, dur_override = _apply_note_color(
                            resolved, rule, beat_note, beat_duration)
                        beat_energy = (
                            beat_note.rms_energy if beat_note else section_energy)
                        resolved = _apply_energy_scale(
                            resolved, cue_type, bpm_s, section_energy, beat_energy)
                        cues.append(_make_cue(
                            id=next_id(),
                            time=beat.time,
                            duration=dur_override if dur_override is not None else _duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=resolved,
                        ))

            # ----------------------------------------------------------
            elif trigger == "bar_beat_1":
                for j, bar in enumerate(section_bars):
                    resolved = _resolve_params(
                        params_template, bar_idx=j, n_bars=n_bars)
                    # Use the bar's downbeat note (first beat of this bar)
                    first_beat_idx = bar.beat_indices[0] if bar.beat_indices else None
                    beat_note = (
                        beat_note_map.get(first_beat_idx)
                        if first_beat_idx is not None else None
                    )
                    resolved, dur_override = _apply_note_color(
                        resolved, rule, beat_note, beat_duration)
                    beat_energy = (
                        beat_note.rms_energy if beat_note else section_energy)
                    resolved = _apply_energy_scale(
                        resolved, cue_type, bpm_s, section_energy, beat_energy)
                    # Level 2: phrase-level param override (geometry rotation per 2/4/8 bars)
                    if cue_type in ("laser_static", "laser_scan", "laser_chase"):
                        resolved = _phrase_plan.get_laser_override(j, resolved)
                    elif cue_type == "movement_enable":
                        resolved = _phrase_plan.get_movement_override(j, resolved)
                    cues.append(_make_cue(
                        id=next_id(),
                        time=bar.time,
                        duration=dur_override if dur_override is not None else _duration(),
                        cue_type=cue_type,
                        section=section.label,
                        trigger=trigger,
                        target_groups=target_groups,
                        params=resolved,
                    ))

            # ----------------------------------------------------------
            elif trigger == "bar_2_beat_1":
                for j, bar in enumerate(section_bars):
                    if j % 2 == 0:
                        resolved = _resolve_params(
                            params_template,
                            bar_idx=j,
                            n_bars=n_bars,
                            cycle_idx=j // 2,
                            cycle_list=DROP_COLOR_CYCLE,
                        )
                        first_beat_idx = bar.beat_indices[0] if bar.beat_indices else None
                        beat_note = (
                            beat_note_map.get(first_beat_idx)
                            if first_beat_idx is not None else None
                        )
                        resolved, dur_override = _apply_note_color(
                            resolved, rule, beat_note, beat_duration)
                        beat_energy = (
                            beat_note.rms_energy if beat_note else section_energy)
                        resolved = _apply_energy_scale(
                            resolved, cue_type, bpm_s, section_energy, beat_energy)
                        if cue_type in ("laser_static", "laser_scan", "laser_chase"):
                            bar_idx_in_sect = max(0, bar.index - section.bar_start)
                            resolved = _phrase_plan.get_laser_override(bar_idx_in_sect, resolved)
                        cues.append(_make_cue(
                            id=next_id(),
                            time=bar.time,
                            duration=dur_override if dur_override is not None else _duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=resolved,
                        ))

            # ----------------------------------------------------------
            elif trigger == "bar_4_beat_1":
                for j, bar in enumerate(section_bars):
                    if j % 4 == 0:
                        resolved = _resolve_params(
                            params_template,
                            bar_idx=j,
                            n_bars=n_bars,
                            cycle_idx=j // 4,
                            cycle_list=BUILD_COLOR_CYCLE,
                        )
                        # Apply motion vocabulary override for movement_enable
                        if _motion and cue_type == "movement_enable" and _motion.movement_params:
                            resolved = {**resolved, **_motion.movement_params}
                        resolved["motion_family"] = _motion_family
                        resolved = _apply_energy_scale(
                            resolved, cue_type, bpm_s, section_energy, section_energy)
                        if cue_type in ("laser_static", "laser_scan", "laser_chase"):
                            bar_idx_in_sect = max(0, bar.index - section.bar_start)
                            resolved = _phrase_plan.get_laser_override(bar_idx_in_sect, resolved)
                        elif cue_type == "movement_enable":
                            bar_idx_in_sect = max(0, bar.index - section.bar_start)
                            resolved = _phrase_plan.get_movement_override(bar_idx_in_sect, resolved)
                        cues.append(_make_cue(
                            id=next_id(),
                            time=bar.time,
                            duration=_duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=resolved,
                        ))

            # ----------------------------------------------------------
            elif trigger == "build_last4":
                # Strobe hits on beat 0 and beat 2 of the last 4 bars
                last4_start_idx = section_bars[-4].index if n_bars >= 4 else (
                    section_bars[0].index if section_bars else 0
                )
                for beat in section_beats:
                    if beat.bar_index >= last4_start_idx and beat.beat_in_bar in (0, 2):
                        beat_note = beat_note_map.get(beat.index)
                        beat_energy = (
                            beat_note.rms_energy if beat_note else section_energy)
                        resolved = _resolve_params(params_template)
                        resolved = _apply_energy_scale(
                            resolved, cue_type, bpm_s, section_energy, beat_energy)
                        cues.append(_make_cue(
                            id=next_id(),
                            time=beat.time,
                            duration=_duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=resolved,
                        ))

            # ----------------------------------------------------------
            elif trigger == "pre_drop":
                # Last beat of the section
                if section_beats:
                    last_beat = section_beats[-1]
                    beat_note = beat_note_map.get(last_beat.index)
                    beat_energy = (
                        beat_note.rms_energy if beat_note else section_energy)
                    resolved = _resolve_params(params_template)
                    resolved = _apply_energy_scale(
                        resolved, cue_type, bpm_s, section_energy, beat_energy)
                    cues.append(_make_cue(
                        id=next_id(),
                        time=last_beat.time,
                        duration=_duration(),
                        cue_type=cue_type,
                        section=section.label,
                        trigger=trigger,
                        target_groups=target_groups,
                        params=resolved,
                    ))

    # Sort by time, then by cue_id as a stable tiebreaker
    cues.sort(key=lambda c: (c.time, c.id))

    # Apply rig constraints if a template was supplied
    if template is not None:
        cues = _apply_constraints(cues, template)

    # Global brightness boost: lift every intensity field by _GLOBAL_INTENSITY_SCALE
    # (capped at 1.0). Applied after all per-cue energy scaling so the boost is
    # additive on top of the music-reactive values rather than competing with them.
    cues = [_apply_global_brightness(c, _GLOBAL_INTENSITY_SCALE) for c in cues]

    # Build sorted beat_times and bar_times arrays from the timeline.
    # These give the frontend exact onset timestamps for frame-precise sync via
    # requestAnimationFrame — eliminates the need to derive timing from BPM.
    beat_times: list[float] = sorted(b.time for b in timeline.beats)
    # bar_times: only beat_in_bar == 0 (downbeat of each bar)
    bar_times: list[float] = sorted(
        b.time for b in timeline.beats if b.beat_in_bar == 0
    )

    # Build per-fixture laser animation preset from the stage layout.
    # This pre-computes pan/tilt ranges with right-unit phase inversion so the
    # frontend needs zero geometric reasoning — just interpolate the numbers.
    laser_preset = _build_laser_preset(template)

    return CueOutputSchema(
        bpm=timeline.bpm.bpm,
        total_duration_sec=timeline.metadata.duration_sec,
        total_cues=len(cues),
        cues=cues,
        brightness_multiplier=_GLOBAL_INTENSITY_SCALE,
        audience_fill=True,
        section_choreography=section_choreography,
        beat_times=beat_times,
        bar_times=bar_times,
        no_floor_projection=True,
        laser_animation_preset=laser_preset,
    )


def _build_laser_preset(template: "RigTemplate | None") -> dict:
    """
    Build the laser_animation_preset from the rig template's stage layout.

    For each laser_rgb fixture, produces:
      origin          [x, y, z]    – fixture mount position
      aim_center      [x, y, z]    – normalised base aim (Y=0, horizontal)
      pan_range_deg   [min, max]   – horizontal sweep range in degrees
                                     RIGHT units: range is inverted ([max, min])
                                     so they mirror the LEFT unit exactly.
      tilt_range_deg  [min, max]   – vertical sweep range in degrees
      phase_offset_deg int         – 0 for left/center, 180 for right
      sweep_role      str          – "left" | "right" | "center"
      beam_length     float        – metres before beam fades to transparent
      scan_angle      float        – total horizontal sweep width in degrees
    """
    if template is None:
        return {}

    try:
        from backend.lighting.stage_layout import get_layout
        layout = get_layout(template.id)
    except Exception:
        return {}

    fixtures_out: list[dict] = []
    for f in layout.get("fixtures", []):
        if f.get("type") != "laser_rgb":
            continue

        scan_angle   = float(f.get("scan_angle",   45))
        tilt_range   = float(f.get("tilt_range_deg", 25))
        beam_length  = float(f.get("beam_length",  10))
        role         = f.get("sweep_role", "center")
        phase_offset = int(f.get("sweep_phase_offset_deg", 0))
        aim          = f.get("aim", [0.0, 0.0, 1.0])

        half_pan  = scan_angle / 2.0
        half_tilt = tilt_range  / 2.0

        # Right units: invert the pan range so their sweep mirrors the left unit.
        # When left is at +30°, right is at -30° → symmetrical V / X shape.
        if role == "right":
            pan_range = [half_pan, -half_pan]   # sweeps inward
        else:
            pan_range = [-half_pan, half_pan]   # sweeps outward / center

        fixtures_out.append({
            "id":              f["id"],
            "sweep_role":      role,
            "origin":          f.get("position", [0, 0, 0]),
            "aim_center":      aim,
            "pan_range_deg":   pan_range,
            "tilt_range_deg":  [-half_tilt, half_tilt],
            "phase_offset_deg":phase_offset,
            "beam_length":     beam_length,
            "scan_angle":      scan_angle,
            "scan_axes":       f.get("scan_axes", ["horizontal"]),
        })

    return {
        "mode":        "bilateral_sync",
        "description": (
            "Drive all laser fixtures from a single shared phase oscillator. "
            "LEFT units use pan_range_deg as-is. "
            "RIGHT units have pan_range_deg already inverted so they mirror LEFT. "
            "CENTER units follow LEFT. "
            "pan_angle = lerp(pan_range_deg[0], pan_range_deg[1], (sin(t*freq*2π + phase_offset_rad)+1)/2)"
        ),
        "fixtures":    fixtures_out,
    }


# ---------------------------------------------------------------------------
# Constraint filtering
# ---------------------------------------------------------------------------

def _apply_constraints(cues: list[Cue], template: "RigTemplate") -> list[Cue]:
    """
    Filter and adapt the cue list to match the rig template's constraints.

    Rules applied in order:
      1. Drop cues whose cue_type is in constraints.drop_cue_types.
      2. Drop movement_enable cues if constraints.movement_enable is False.
      3. Drop cues whose target_groups are ALL empty (fixture_count == 0)
         and have no declared fallback_group.
      4. Reroute cues targeting an empty group to its fallback_group when
         a fallback_group is declared in the JSON.
      5. For strobe_hit cues: floor duration to 1/strobe_max_rate_hz so the
         strobe burst never violates the rig's max flash rate.
    """
    from backend.lighting.rig_loader import TemplateConstraints

    constraints: TemplateConstraints = template.constraints
    groups: dict = template.fixture_groups

    # Build a lookup: group_name -> fallback_group (or None)
    fallback_map: dict[str, str | None] = {
        name: g.get("fallback_group")
        for name, g in groups.items()
    }

    min_strobe_duration = 1.0 / max(constraints.strobe_max_rate_hz, 1.0)

    filtered: list[Cue] = []

    for cue in cues:
        # Rule 1: explicit drop_cue_types list
        if cue.cue_type in constraints.drop_cue_types:
            continue

        # Rule 2: movement_enable globally disabled
        if cue.cue_type == "movement_enable" and not constraints.movement_enable:
            continue

        # Rules 3 & 4: group availability
        resolved_groups = _resolve_groups(
            cue.target_groups, groups, fallback_map, constraints.empty_groups
        )
        if not resolved_groups:
            # All target groups are empty with no fallback → drop cue
            continue

        # Rule 5: strobe duration floor
        duration = cue.duration
        if cue.cue_type == "strobe_hit":
            duration = max(duration, min_strobe_duration)

        # Rebuild the cue only if something changed
        if resolved_groups != list(cue.target_groups) or duration != cue.duration:
            cue = Cue(
                id=cue.id,
                time=cue.time,
                duration=round(duration, 4),
                cue_type=cue.cue_type,
                section=cue.section,
                trigger=cue.trigger,
                target_groups=resolved_groups,
                parameters=cue.parameters,
            )

        filtered.append(cue)

    return filtered


def _resolve_groups(
    requested: list[str],
    groups: dict,
    fallback_map: dict[str, str | None],
    empty_groups: list[str],
) -> list[str]:
    """
    For each requested group:
      - If it has fixtures → keep it.
      - If it's empty and has a fallback → substitute the fallback.
      - If it's empty with no fallback → omit it.
    Returns the de-duplicated resolved list, or [] if nothing survives.
    """
    resolved: list[str] = []
    seen: set[str] = set()

    for group in requested:
        if group not in empty_groups:
            # Group has fixtures; keep as-is
            if group not in seen:
                resolved.append(group)
                seen.add(group)
        else:
            # Empty group — try fallback
            fallback = fallback_map.get(group)
            if fallback and fallback not in seen and fallback not in empty_groups:
                resolved.append(fallback)
                seen.add(fallback)
            # else: omit

    return resolved


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_global_brightness(cue: Cue, scale: float) -> Cue:
    """
    Multiply every intensity-related field in cue.parameters by *scale*,
    capped at 1.0. Returns the original cue object unchanged if no intensity
    fields are present (avoids needless object creation).

    Fields scaled:
        intensity, intensity_start, intensity_end, target_intensity
    """
    _INTENSITY_KEYS = ("intensity", "intensity_start", "intensity_end", "target_intensity")
    params = cue.parameters
    if not any(k in params for k in _INTENSITY_KEYS):
        return cue

    updated: dict = dict(params)
    for k in _INTENSITY_KEYS:
        if k in updated:
            updated[k] = round(min(1.0, float(updated[k]) * scale), 3)

    return cue.model_copy(update={"parameters": updated})


def _bpm_scale(bpm: float) -> float:
    """
    Normalise BPM against a 120 BPM baseline.

    Returns a multiplier in [0.4, 2.5]:
        80 BPM  → 0.67  (slower, more restrained)
       120 BPM  → 1.00  (reference)
       150 BPM  → 1.25
       180 BPM  → 1.50  (very fast, highly energetic)
    """
    return float(min(max(bpm / 120.0, 0.4), 2.5))


def _apply_energy_scale(
    params: dict,
    cue_type: str,
    bpm_s: float,
    section_energy: float,
    beat_energy: float,
) -> dict:
    """
    Scale cue parameters by BPM and musical energy so the show responds
    dynamically to the song's intensity.

    bpm_s          – _bpm_scale(bpm): BPM / 120.0 in [0.4, 2.5]
    section_energy – section.energy_mean  [0, 1]  (macro loudness of the section)
    beat_energy    – beat rms_energy or section_energy fallback  [0, 1]

    Strategy by cue type:
      movement_enable  → speed   scales with BPM × section energy
      laser_scan       → speed   scales with BPM × beat energy;
                          spread_deg and fan_count expand with section energy
      laser_static     → spread_deg and fan_count expand with section energy
      laser_chase      → step_beats shortens with BPM (faster stepping at high BPM);
                          beam_count increases with section energy
      wash / pulse     → intensity scales with beat energy (skip if note_dynamic)
      strobe_hit       → intensity scales with beat energy (skip if note_dynamic)

    note_dynamic intensity is already scaled by _apply_note_color; skip to avoid
    double-scaling. Laser/movement speed is ALWAYS scaled so the whole show
    responds to tempo even during note-colored passages.
    """
    p = dict(params)
    is_note = (p.get("color") == "note_dynamic")

    if cue_type == "movement_enable":
        if "speed" in p:
            spd = float(p["speed"]) * bpm_s * (0.55 + 0.45 * section_energy)
            p["speed"] = round(min(1.0, spd), 3)

    elif cue_type == "laser_scan":
        if "speed" in p:
            spd = float(p["speed"]) * bpm_s * (0.50 + 0.50 * beat_energy)
            p["speed"] = round(min(1.0, spd), 3)
        if "spread_deg" in p:
            p["spread_deg"] = round(
                float(p["spread_deg"]) * (0.55 + 0.45 * section_energy), 1)
        if "fan_count" in p:
            p["fan_count"] = max(1, min(8,
                int(p["fan_count"]) + int(section_energy * 2.0)))

    elif cue_type == "laser_static":
        if "spread_deg" in p:
            p["spread_deg"] = round(
                float(p["spread_deg"]) * (0.50 + 0.50 * section_energy), 1)
        if "fan_count" in p:
            p["fan_count"] = max(1, min(8,
                int(p["fan_count"]) + int(section_energy * 3.0)))

    elif cue_type == "laser_chase":
        if "step_beats" in p:
            # Faster BPM → shorter step interval (more rapid color cycling)
            p["step_beats"] = round(max(0.125, float(p["step_beats"]) / bpm_s), 3)
        if "beam_count" in p:
            p["beam_count"] = max(2, min(12,
                int(p["beam_count"]) + int(section_energy * 4.0)))

    elif cue_type in ("wash", "pulse") and not is_note:
        e_mult = 0.35 + 0.65 * beat_energy
        for k in ("intensity", "intensity_start", "intensity_end"):
            if k in p:
                p[k] = round(min(1.0, float(p[k]) * e_mult), 3)

    elif cue_type == "strobe_hit" and not is_note:
        e_mult = 0.25 + 0.75 * beat_energy
        if "intensity" in p:
            p["intensity"] = round(min(1.0, float(p["intensity"]) * e_mult), 3)

    return p


def _apply_beat_modulation(params: dict, mod: dict, cue_type: str) -> dict:
    """
    Apply beat-level modulation to cue parameters.

    Scales intensity fields by mod['intensity_mod'] and spread_deg by
    mod['spread_mod']. Also injects beat metadata for the frontend.

    Skips intensity scaling for note_dynamic cues (already handled by
    _apply_note_color).
    """
    p = dict(params)
    is_note = (p.get("color") == "note_dynamic")

    intensity_mod = float(mod.get("intensity_mod", 1.0))
    spread_mod    = float(mod.get("spread_mod", 1.0))

    # Scale intensity (skip if note_dynamic)
    if not is_note and intensity_mod != 1.0:
        for k in ("intensity", "intensity_start", "intensity_end"):
            if k in p:
                p[k] = round(min(1.0, float(p[k]) * intensity_mod), 3)

    # Scale spread for laser cues
    if cue_type in ("laser_static", "laser_scan") and spread_mod != 1.0:
        if "spread_deg" in p:
            p["spread_deg"] = round(
                max(3.0, min(120.0, float(p["spread_deg"]) * spread_mod)), 1)

    # Inject beat metadata (renderer uses these for direction/animation hints)
    for meta_key in ("beat_behavior", "phrase_index", "motion_variant", "direction"):
        if meta_key in mod:
            p[meta_key] = mod[meta_key]

    return p


def _apply_note_color(
    params: dict,
    rule: dict,
    beat_note: "BeatNote | None",
    beat_t: float,
) -> tuple[dict, float | None]:
    """
    If the rule carries use_note_color=True and a BeatNote is available:

      • Sets color = "note_dynamic" (sentinel understood by the frontend).
      • Adds note_hue and note_brightness to params so the renderer can build
        a smooth HSL color that stays in the key's color family.
      • Scales intensity by RMS energy × tonal brightness so loud/stable notes
        glow at full brightness while soft/unstable notes dim naturally.

    The smoothed_hue field in BeatNote is already EMA-filtered across the
    melody, so consecutive notes in the same phrase share similar hues instead
    of jumping across the color wheel.

    If use_tone_duration=True, also returns a duration override equal to
    tone_duration_beats × beat_t so the wash cue sustains as long as the note.

    Returns (updated_params, duration_override_or_None).
    """
    if not rule.get("use_note_color") or beat_note is None:
        return params, None

    p = dict(params)

    # Dynamic color: frontend uses note_hue + note_brightness to build HSL
    p["color"]            = "note_dynamic"
    p["note_hue"]         = beat_note.smoothed_hue        # [0, 1] EMA-smoothed
    p["note_brightness"]  = beat_note.tonal_brightness     # [0, 1] stability × clarity

    # Intensity envelope:
    #   rms_energy [0,1] → overall loudness
    #   tonal_brightness → harmonic stability of this note
    # Range: ≈ 0.25 (very soft + unstable) → 1.0 (full energy + stable tonic)
    energy_scale  = 0.40 + 0.60 * beat_note.rms_energy
    tonal_scale   = 0.65 + 0.35 * beat_note.tonal_brightness
    combined      = energy_scale * tonal_scale

    if "intensity" in p:
        p["intensity"] = round(min(1.0, float(p["intensity"]) * combined), 3)
    if "intensity_start" in p:
        p["intensity_start"] = round(
            min(1.0, float(p["intensity_start"]) * combined), 3)
    if "intensity_end" in p:
        p["intensity_end"] = round(
            min(1.0, float(p["intensity_end"]) * combined), 3)

    # Tone-length duration override
    dur_override: float | None = None
    if rule.get("use_tone_duration"):
        dur_override = max(beat_t * 0.5, beat_note.tone_duration_beats * beat_t)

    return p, dur_override


def _make_cue(
    id: str,
    time: float,
    duration: float,
    cue_type: str,
    section: str,
    trigger: str,
    target_groups: list[str],
    params: dict,
) -> Cue:
    return Cue(
        id=id,
        time=round(time, 4),
        duration=round(max(duration, 0.01), 4),  # floor at 10ms
        cue_type=cue_type,
        section=section,
        trigger=trigger,
        target_groups=target_groups,
        parameters=params,
    )


def _resolve_params(
    template: dict,
    beat_idx: int = 0,
    n_beats: int = 1,
    bar_idx: int = 0,
    n_bars: int = 1,
    cycle_idx: int = 0,
    cycle_list: list[str] | None = None,
) -> dict:
    """
    Copy the params template and resolve any dynamic placeholder values.

    Dynamic placeholders:
        _ramp=True         – replace 'intensity' with lerped value
        _linear_fade=True  – replace 'intensity' with lerped value per bar
        _drop_cycle        – replace color with DROP_COLOR_CYCLE[cycle_idx % len]
        _build_cycle       – replace color with BUILD_COLOR_CYCLE[cycle_idx % len]
    """
    p = copy.copy(template)

    # Ramp: lerp intensity from intensity_start to intensity_end per beat
    if p.pop("_ramp", False):
        progress = beat_idx / max(n_beats - 1, 1)
        i_start = p.pop("intensity_start", 0.0)
        i_end = p.pop("intensity_end", 1.0)
        p["intensity"] = round(i_start + (i_end - i_start) * progress, 3)

    # Linear fade per bar
    if p.pop("_linear_fade", False):
        progress = bar_idx / max(n_bars - 1, 1)
        i_start = p.pop("intensity_start", 0.4)
        i_end = p.pop("intensity_end", 0.0)
        p["intensity"] = round(max(i_start + (i_end - i_start) * progress, 0.0), 3)

    # Dynamic color cycle resolution
    if p.get("color") == "_drop_cycle":
        colors = cycle_list if cycle_list else DROP_COLOR_CYCLE
        p["color"] = colors[cycle_idx % len(colors)]

    if p.get("color") == "_build_cycle":
        colors = cycle_list if cycle_list else BUILD_COLOR_CYCLE
        p["color"] = colors[cycle_idx % len(colors)]

    return p
