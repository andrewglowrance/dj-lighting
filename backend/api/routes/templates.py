"""
api/routes/templates.py

GET  /api/templates          – list all available rig templates (summaries)
GET  /api/templates/{rig_id} – full template JSON for one rig
POST /api/cues               – generate cue timeline from a TimelineSchema + rig selection
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.lighting.cue_engine import generate_cues
from backend.lighting.rig_loader import get_template, list_templates
from backend.schemas.timeline import TimelineSchema


router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/templates
# ---------------------------------------------------------------------------

@router.get(
    "/templates",
    summary="List all available rig templates",
)
def list_rig_templates() -> JSONResponse:
    """Return a summary list of every rig template (id, name, fixture_counts, constraints)."""
    summaries = list_templates()
    return JSONResponse(content=[
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "channel_budget": s.channel_budget,
            "fixture_counts": s.fixture_counts,
            "constraints_summary": s.constraints_summary,
        }
        for s in summaries
    ])


# ---------------------------------------------------------------------------
# GET /api/templates/{rig_id}
# ---------------------------------------------------------------------------

@router.get(
    "/templates/{rig_id}",
    summary="Get full rig template definition",
)
def get_rig_template(rig_id: str) -> JSONResponse:
    """Return the complete JSON definition for a single rig template."""
    try:
        template = get_template(rig_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content=template.raw)


# ---------------------------------------------------------------------------
# POST /api/cues
# ---------------------------------------------------------------------------

class CueRequest(BaseModel):
    timeline: TimelineSchema
    rig: str  # one of: small_club | festival_lite | mobile_dj


@router.post(
    "/cues",
    summary="Generate deterministic lighting cues from a timeline + rig selection",
)
def generate_cue_timeline(request: CueRequest) -> JSONResponse:
    """
    Accepts a TimelineSchema (from /analyze-track) and a rig template id.
    Returns a CueOutputSchema with all cues filtered and adapted to the rig's constraints.
    """
    try:
        template = get_template(request.rig)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        cue_output = generate_cues(request.timeline, template=template)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Cue generation failed: {exc}",
        ) from exc

    return JSONResponse(content=cue_output.model_dump())
