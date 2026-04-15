"""
api/routes/export.py

POST /api/export

Accepts a CueOutputSchema and a format string, returns a downloadable file.

Supported formats:
  qlcplus  → .qxw XML workspace  (Content-Type: application/xml)
  artnet   → .json sequence file (Content-Type: application/json)
  sacn     → .json sequence file (Content-Type: application/json)
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from backend.lighting.dmx_formatter import cues_to_qlcplus_xml
from backend.schemas.cues import CueOutputSchema


router = APIRouter()


class ExportRequest(BaseModel):
    cues: CueOutputSchema
    format: str  # "qlcplus" | "artnet" | "sacn"


@router.post(
    "/export",
    summary="Export cue timeline as QLC+ workspace or DMX sequence file",
)
def export_cues(request: ExportRequest) -> Response:
    fmt = request.format.lower().strip()

    if fmt == "qlcplus":
        xml_str = cues_to_qlcplus_xml(request.cues)
        return Response(
            content=xml_str.encode("utf-8"),
            media_type="application/xml",
            headers={
                "Content-Disposition": 'attachment; filename="cueforge_show.qxw"'
            },
        )

    elif fmt in ("artnet", "sacn"):
        # Phase 1: return the raw cue sequence as JSON.
        # Phase 2 will add proper Art-Net / sACN packet framing.
        payload = {
            "format": fmt,
            "bpm": request.cues.bpm,
            "total_duration_sec": request.cues.total_duration_sec,
            "note": (
                f"Phase 1 export — raw cue timeline. "
                f"Art-Net / sACN packet framing will be added in Phase 2."
            ),
            "cues": [c.model_dump() for c in request.cues.cues],
        }
        filename = "artnet_cues.json" if fmt == "artnet" else "sacn_cues.json"
        return Response(
            content=json.dumps(payload, indent=2).encode("utf-8"),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    else:
        return Response(
            content=json.dumps({"error": f"Unknown format '{fmt}'. Use: qlcplus, artnet, sacn"}),
            media_type="application/json",
            status_code=422,
        )
