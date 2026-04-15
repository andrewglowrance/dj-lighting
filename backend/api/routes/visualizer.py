"""
api/routes/visualizer.py

GET /api/visualizer/{rig_id}

Returns the 3D stage layout for a given rig template.
Consumed by the in-browser lighting visualizer panel.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.lighting.stage_layout import get_layout

router = APIRouter()


@router.get(
    "/visualizer/{rig_id}",
    summary="Get 3D stage layout for a rig template",
)
def get_stage_layout(rig_id: str) -> JSONResponse:
    """
    Returns fixture positions, beam angles, stage dimensions, and truss positions
    for use by the frontend Three.js visualizer.
    """
    try:
        layout = get_layout(rig_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content=layout)
