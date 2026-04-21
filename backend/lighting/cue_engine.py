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
from backend.schemas.cues import Cue, CueOutputSchema
from backend.schemas.timeline import Beat, Bar, Section, TimelineSchema

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

    # Pre-build fast lookup structures
    bar_map: dict[int, Bar] = {b.index: b for b in timeline.bars}
    beat_map: dict[int, Beat] = {b.index: b for b in timeline.beats}

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
                cues.append(_make_cue(
                    id=next_id(),
                    time=section.start,
                    duration=_duration(),
                    cue_type=cue_type,
                    section=section.label,
                    trigger=trigger,
                    target_groups=target_groups,
                    params=_resolve_params(params_template, beat_idx=0, n_beats=1, bar_idx=0, n_bars=1),
                ))

            # ----------------------------------------------------------
            elif trigger == "beat":
                for i, beat in enumerate(section_beats):
                    cues.append(_make_cue(
                        id=next_id(),
                        time=beat.time,
                        duration=_duration(),
                        cue_type=cue_type,
                        section=section.label,
                        trigger=trigger,
                        target_groups=target_groups,
                        params=_resolve_params(params_template, beat_idx=i, n_beats=n_beats),
                    ))

            # ----------------------------------------------------------
            elif trigger == "beat_2_4":
                for beat in section_beats:
                    if beat.beat_in_bar in (1, 3):
                        cues.append(_make_cue(
                            id=next_id(),
                            time=beat.time,
                            duration=_duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=_resolve_params(params_template),
                        ))

            # ----------------------------------------------------------
            elif trigger == "bar_beat_1":
                for j, bar in enumerate(section_bars):
                    cues.append(_make_cue(
                        id=next_id(),
                        time=bar.time,
                        duration=_duration(),
                        cue_type=cue_type,
                        section=section.label,
                        trigger=trigger,
                        target_groups=target_groups,
                        params=_resolve_params(params_template, bar_idx=j, n_bars=n_bars),
                    ))

            # ----------------------------------------------------------
            elif trigger == "bar_2_beat_1":
                for j, bar in enumerate(section_bars):
                    if j % 2 == 0:
                        cues.append(_make_cue(
                            id=next_id(),
                            time=bar.time,
                            duration=_duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=_resolve_params(
                                params_template,
                                bar_idx=j,
                                n_bars=n_bars,
                                cycle_idx=j // 2,
                                cycle_list=DROP_COLOR_CYCLE,
                            ),
                        ))

            # ----------------------------------------------------------
            elif trigger == "bar_4_beat_1":
                for j, bar in enumerate(section_bars):
                    if j % 4 == 0:
                        cues.append(_make_cue(
                            id=next_id(),
                            time=bar.time,
                            duration=_duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=_resolve_params(
                                params_template,
                                bar_idx=j,
                                n_bars=n_bars,
                                cycle_idx=j // 4,
                                cycle_list=BUILD_COLOR_CYCLE,
                            ),
                        ))

            # ----------------------------------------------------------
            elif trigger == "build_last4":
                # Strobe hits on beat 0 and beat 2 of the last 4 bars
                last4_start_idx = section_bars[-4].index if n_bars >= 4 else (
                    section_bars[0].index if section_bars else 0
                )
                for beat in section_beats:
                    if beat.bar_index >= last4_start_idx and beat.beat_in_bar in (0, 2):
                        cues.append(_make_cue(
                            id=next_id(),
                            time=beat.time,
                            duration=_duration(),
                            cue_type=cue_type,
                            section=section.label,
                            trigger=trigger,
                            target_groups=target_groups,
                            params=_resolve_params(params_template),
                        ))

            # ----------------------------------------------------------
            elif trigger == "pre_drop":
                # Last beat of the section
                if section_beats:
                    last_beat = section_beats[-1]
                    cues.append(_make_cue(
                        id=next_id(),
                        time=last_beat.time,
                        duration=_duration(),
                        cue_type=cue_type,
                        section=section.label,
                        trigger=trigger,
                        target_groups=target_groups,
                        params=_resolve_params(params_template),
                    ))

    # Sort by time, then by cue_id as a stable tiebreaker
    cues.sort(key=lambda c: (c.time, c.id))

    # Apply rig constraints if a template was supplied
    if template is not None:
        cues = _apply_constraints(cues, template)

    return CueOutputSchema(
        bpm=timeline.bpm.bpm,
        total_duration_sec=timeline.metadata.duration_sec,
        total_cues=len(cues),
        cues=cues,
    )


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
