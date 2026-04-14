"""
lighting/rig_loader.py

Loads, validates, and exposes rig template JSON files.

Templates live in  <project_root>/rig_templates/*.json
This module resolves that path relative to its own location so it works
regardless of where uvicorn is launched from.

Public API:
    get_template(rig_id: str) -> RigTemplate
    list_templates() -> list[TemplateSummary]
    get_constraints(rig_id: str) -> TemplateConstraints
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# backend/lighting/rig_loader.py  →  ../../rig_templates/
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "rig_templates"


# ---------------------------------------------------------------------------
# Typed constraint model
# ---------------------------------------------------------------------------

@dataclass
class TemplateConstraints:
    """
    Constraints the cue engine must respect for a given rig.
    All fields correspond to the "constraints" block in the JSON.
    """
    movement_enable: bool = True
    max_simultaneous_moving_heads: int = 4
    strobe_max_rate_hz: float = 20.0
    strobe_blackout_during_movement: bool = False
    max_color_zones: int = 4
    fog_enabled: bool = False
    haze_enabled: bool = False
    simultaneous_full_strobe_and_movement: bool = True
    # cue types the engine must silently drop for this rig
    drop_cue_types: list[str] = field(default_factory=list)
    # fixture groups with zero fixtures (engine drops cues targeting only these)
    empty_groups: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Template summary (returned by /api/templates list endpoint)
# ---------------------------------------------------------------------------

@dataclass
class TemplateSummary:
    id: str
    name: str
    description: str
    channel_budget: int
    fixture_counts: dict[str, int]   # group_name -> fixture_count
    constraints_summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Full template (returned when a specific template is requested)
# ---------------------------------------------------------------------------

@dataclass
class RigTemplate:
    id: str
    name: str
    description: str
    universe: int
    channel_budget: int
    fixture_groups: dict[str, Any]    # raw group dicts from JSON
    auxiliary: dict[str, Any]
    constraints: TemplateConstraints
    dmx_channel_map: dict[str, str]
    cue_rendering: dict[str, str]
    raw: dict[str, Any]               # full JSON for pass-through to frontend


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_templates() -> list[TemplateSummary]:
    """Return a summary of every available rig template, alphabetically by id."""
    summaries = []
    for path in sorted(_TEMPLATES_DIR.glob("*.json")):
        raw = _load_json(path)
        summaries.append(_to_summary(raw))
    return summaries


def get_template(rig_id: str) -> RigTemplate:
    """
    Load and return a fully parsed RigTemplate for the given rig_id.

    Raises:
        FileNotFoundError – if no template with that id exists
        ValueError        – if the JSON is missing required fields
    """
    path = _TEMPLATES_DIR / f"{rig_id}.json"
    if not path.exists():
        available = [p.stem for p in _TEMPLATES_DIR.glob("*.json")]
        raise FileNotFoundError(
            f"Rig template '{rig_id}' not found. Available: {available}"
        )
    raw = _load_json(path)
    return _to_template(raw)


def get_constraints(rig_id: str) -> TemplateConstraints:
    """Convenience shortcut — load template and return only its constraints."""
    return get_template(rig_id).constraints


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_constraints(raw: dict) -> TemplateConstraints:
    """
    Parse the 'constraints' block from a raw template dict.
    Computes empty_groups from fixture_groups entries with fixture_count == 0.
    """
    c = raw.get("constraints", {})
    groups = raw.get("fixture_groups", {})
    empty_groups = [
        name for name, g in groups.items()
        if g.get("fixture_count", 0) == 0
    ]
    return TemplateConstraints(
        movement_enable=c.get("movement_enable", True),
        max_simultaneous_moving_heads=c.get("max_simultaneous_moving_heads", 4),
        strobe_max_rate_hz=c.get("strobe_max_rate_hz", 20.0),
        strobe_blackout_during_movement=c.get("strobe_blackout_during_movement", False),
        max_color_zones=c.get("max_color_zones", 4),
        fog_enabled=c.get("fog_enabled", False),
        haze_enabled=c.get("haze_enabled", False),
        simultaneous_full_strobe_and_movement=c.get(
            "simultaneous_full_strobe_and_movement", True
        ),
        drop_cue_types=c.get("drop_cue_types", []),
        empty_groups=empty_groups,
    )


def _to_summary(raw: dict) -> TemplateSummary:
    groups = raw.get("fixture_groups", {})
    fixture_counts = {
        name: g.get("fixture_count", 0) for name, g in groups.items()
    }
    constraints = raw.get("constraints", {})
    return TemplateSummary(
        id=raw["id"],
        name=raw["name"],
        description=raw["description"],
        channel_budget=raw.get("channel_budget", 0),
        fixture_counts=fixture_counts,
        constraints_summary={
            "movement_enable":    constraints.get("movement_enable", True),
            "max_color_zones":    constraints.get("max_color_zones", 1),
            "strobe_max_rate_hz": constraints.get("strobe_max_rate_hz", 20),
            "haze_enabled":       constraints.get("haze_enabled", False),
            "fog_enabled":        constraints.get("fog_enabled", False),
        },
    )


def _to_template(raw: dict) -> RigTemplate:
    return RigTemplate(
        id=raw["id"],
        name=raw["name"],
        description=raw["description"],
        universe=raw.get("universe", 1),
        channel_budget=raw.get("channel_budget", 512),
        fixture_groups=raw.get("fixture_groups", {}),
        auxiliary=raw.get("auxiliary", {}),
        constraints=_parse_constraints(raw),
        dmx_channel_map=raw.get("dmx_channel_map", {}),
        cue_rendering=raw.get("cue_rendering", {}),
        raw=raw,
    )
