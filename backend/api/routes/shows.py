"""
api/routes/shows.py

POST /api/shows                   – generate a new show (analyze + style + cues)
GET  /api/shows/{show_id}         – retrieve an existing show
POST /api/shows/{show_id}/revise  – apply a revision prompt to an existing show
GET  /api/shows                   – list all stored show summaries

This is the primary entry point for the frontend from the moment a user
uploads a file.  The older /analyze-track and /cues endpoints remain intact
for backward compatibility.
"""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.analysis.pipeline import analyze_track
from backend.lighting.cue_engine import generate_cues
from backend.lighting.prompt_parser import apply_patch, parse_prompt, parse_revision
from backend.lighting.rig_loader import get_template
from backend.lighting.show_store import show_store
from backend.lighting.stage_layout import get_layout
from backend.lighting.style_engine import apply_style
from backend.schemas.style import EnvironmentRenderingProfile
from backend.schemas.show import (
    RevisionMeta,
    RevisionRequest,
    RevisionResult,
    Show,
    ShowResponse,
    ShowSummary,
    VisualizationPlan,
)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".aiff", ".aif", ".ogg", ".m4a"}
_MAX_FILE_BYTES = 200 * 1024 * 1024   # 200 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_show_response(show: Show) -> dict:
    return ShowResponse(
        show_id          = show.show_id,
        created_at       = show.created_at,
        rig_id           = show.rig_id,
        creation_prompt  = show.creation_prompt,
        revision_count   = len(show.revision_history),
        style_profile    = show.style_profile,
        original_style   = show.original_style,
        viz_plan         = show.viz_plan,
        revision_history = show.revision_history,
    ).model_dump()


def _make_viz_plan(
    rig_id: str,
    styled_cues,
    style_profile,
    timeline,
    env_profile: EnvironmentRenderingProfile | None = None,
) -> VisualizationPlan:
    layout = get_layout(rig_id)
    return VisualizationPlan(
        rig_id              = rig_id,
        bpm                 = timeline.bpm.bpm,
        total_duration_sec  = timeline.metadata.duration_sec,
        cues                = styled_cues,
        layout              = layout,
        style_profile       = style_profile,
        mood                = timeline.mood,
        environment_profile = env_profile or EnvironmentRenderingProfile(),
    )


# ---------------------------------------------------------------------------
# POST /api/shows  — create a new show
# ---------------------------------------------------------------------------

@router.post(
    "/shows",
    summary="Upload audio + optional prompt → full show payload",
)
async def create_show(
    file:   UploadFile = File(..., description="Audio file (mp3/wav/flac/aiff/ogg/m4a)"),
    rig_id: str        = Form(..., description="Rig template id (small_club | festival_lite | mobile_dj)"),
    prompt: str | None = Form(None, description="Optional natural-language style prompt"),
) -> JSONResponse:
    """
    Full pipeline in one call:
      1. Validate and buffer the uploaded audio file.
      2. Run the audio analysis pipeline (beat tracking, sections, mood).
      3. Load the rig template and generate raw cues.
      4. Parse the optional prompt into a StyleProfile.
      5. Apply the style engine to produce styled cues.
      6. Build and persist the Show.
      7. Return the ShowResponse payload.
    """
    # ── 1. Validate file ────────────────────────────────────────────────────
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. "
                   f"Accepted: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds 200 MB limit ({len(content) // 1024 // 1024} MB received)",
        )

    # ── 2. Audio analysis ───────────────────────────────────────────────────
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            timeline = analyze_track(tmp_path)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Audio analysis failed: {exc}",
            ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # ── 3. Load rig + generate raw cues ────────────────────────────────────
    try:
        template = get_template(rig_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        raw_cues = generate_cues(timeline, template=template)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Cue generation failed: {exc}",
        ) from exc

    # ── 4. Parse prompt → StyleProfile ─────────────────────────────────────
    style_profile = parse_prompt(prompt or "")

    # ── 5. Apply style engine ───────────────────────────────────────────────
    styled_cues = apply_style(raw_cues, style_profile, timeline)

    # ── 6. Build and persist ────────────────────────────────────────────────
    show_id    = show_store.generate_id()
    created_at = show_store.now_iso()
    viz_plan   = _make_viz_plan(rig_id, styled_cues, style_profile, timeline)

    show = Show(
        show_id          = show_id,
        created_at       = created_at,
        rig_id           = rig_id,
        timeline         = timeline,
        raw_cues         = raw_cues,
        styled_cues      = styled_cues,
        style_profile    = style_profile,
        original_style   = style_profile.model_copy(deep=True),
        viz_plan         = viz_plan,
        creation_prompt  = prompt,
        revision_history = [],
    )
    show_store.save(show)

    return JSONResponse(content=_build_show_response(show))


# ---------------------------------------------------------------------------
# GET /api/shows  — list all stored shows
# ---------------------------------------------------------------------------

@router.get(
    "/shows",
    summary="List all stored show summaries",
)
def list_shows() -> JSONResponse:
    summaries = []
    for sid in show_store.list_ids():
        s = show_store.get(sid)
        if s:
            summaries.append(ShowSummary(
                show_id        = s.show_id,
                rig_id         = s.rig_id,
                created_at     = s.created_at,
                creation_prompt= s.creation_prompt,
                revision_count = len(s.revision_history),
                bpm            = s.timeline.bpm.bpm,
                duration_sec   = s.timeline.metadata.duration_sec,
                emotion        = s.timeline.mood.emotion,
                key_label      = s.timeline.mood.key_label,
            ).model_dump())
    return JSONResponse(content=summaries)


# ---------------------------------------------------------------------------
# GET /api/shows/{show_id}  — retrieve a single show
# ---------------------------------------------------------------------------

@router.get(
    "/shows/{show_id}",
    summary="Retrieve an existing show by ID",
)
def get_show(show_id: str) -> JSONResponse:
    show = show_store.get(show_id)
    if show is None:
        raise HTTPException(
            status_code=404,
            detail=f"Show '{show_id}' not found. It may have been evicted "
                   "from the in-memory store after a server restart.",
        )
    return JSONResponse(content=_build_show_response(show))


# ---------------------------------------------------------------------------
# POST /api/shows/{show_id}/revise  — apply a revision prompt
# ---------------------------------------------------------------------------

@router.post(
    "/shows/{show_id}/revise",
    summary="Apply a revision prompt to an existing show",
)
def revise_show(show_id: str, body: RevisionRequest) -> JSONResponse:
    """
    Revision flow:
      1. Load the existing show from the store.
      2. Parse the revision_prompt into a StylePatch (sparse delta).
      3. Apply the patch to the current StyleProfile → new StyleProfile.
      4. Re-run the style engine on the original raw_cues (never the styled cues).
      5. Rebuild the VisualizationPlan and append a RevisionMeta entry.
      6. Persist the updated show and return a RevisionResult.
    """
    show = show_store.get(show_id)
    if show is None:
        raise HTTPException(
            status_code=404,
            detail=f"Show '{show_id}' not found.",
        )

    # ── 2. Parse revision prompt ────────────────────────────────────────────
    patch = parse_revision(body.revision_prompt, show.style_profile)

    # ── 3. Apply patch → new StyleProfile ──────────────────────────────────
    new_profile = apply_patch(patch, show.style_profile, body.revision_prompt)

    # ── 4. Re-style from raw_cues (preserves original music timing) ─────────
    new_styled = apply_style(show.raw_cues, new_profile, show.timeline)

    # ── 5. Build updated viz plan and revision record ───────────────────────
    new_viz = _make_viz_plan(show.rig_id, new_styled, new_profile, show.timeline)

    revision_num = len(show.revision_history) + 1
    meta = RevisionMeta(
        revision_number = revision_num,
        prompt          = body.revision_prompt,
        patch           = patch,
        notes           = patch.notes,
    )

    # ── 6. Persist ─────────────────────────────────────────────────────────
    updated_show = Show(
        show_id          = show.show_id,
        created_at       = show.created_at,
        rig_id           = show.rig_id,
        timeline         = show.timeline,
        raw_cues         = show.raw_cues,          # never changes
        styled_cues      = new_styled,
        style_profile    = new_profile,
        original_style   = show.original_style,    # never changes
        viz_plan         = new_viz,
        creation_prompt  = show.creation_prompt,
        revision_history = [*show.revision_history, meta],
    )
    show_store.save(updated_show)

    result = RevisionResult(
        show_id               = show_id,
        revision_number       = revision_num,
        revision_prompt       = body.revision_prompt,
        patch                 = patch,
        updated_style_profile = new_profile,
        updated_viz_plan      = new_viz,
        notes                 = patch.notes,
    )
    return JSONResponse(content=result.model_dump())


# ---------------------------------------------------------------------------
# POST /api/shows/{show_id}/reset  — revert to original style
# ---------------------------------------------------------------------------

@router.post(
    "/shows/{show_id}/reset",
    summary="Reset show to its original generated style (discard all revisions)",
)
def reset_show(show_id: str) -> JSONResponse:
    show = show_store.get(show_id)
    if show is None:
        raise HTTPException(status_code=404, detail=f"Show '{show_id}' not found.")

    # Re-apply original style to raw cues
    original_styled = apply_style(show.raw_cues, show.original_style, show.timeline)
    original_viz    = _make_viz_plan(
        show.rig_id, original_styled, show.original_style, show.timeline)

    reset_show = Show(
        show_id          = show.show_id,
        created_at       = show.created_at,
        rig_id           = show.rig_id,
        timeline         = show.timeline,
        raw_cues         = show.raw_cues,
        styled_cues      = original_styled,
        style_profile    = show.original_style.model_copy(deep=True),
        original_style   = show.original_style,
        viz_plan         = original_viz,
        creation_prompt  = show.creation_prompt,
        revision_history = [],     # cleared
    )
    show_store.save(reset_show)

    return JSONResponse(content=_build_show_response(reset_show))
