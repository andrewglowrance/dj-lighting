"""
api/routes/analyze.py

POST /analyze-track

Accepts a multipart file upload, saves it to a temp file, runs the analysis
pipeline, and returns the TimelineSchema as JSON.

Allowed formats: .mp3, .wav, .flac, .aiff, .aif
Max file size: 200 MB (enforced by the file size check below)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.analysis.pipeline import analyze_track
from backend.schemas.timeline import TimelineSchema


router = APIRouter()

_ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".aiff", ".aif"}
_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB


@router.post(
    "/analyze-track",
    response_model=TimelineSchema,
    summary="Analyze an audio file and return a beat/section timeline",
    response_description="TimelineSchema JSON",
)
async def analyze_track_endpoint(file: UploadFile) -> JSONResponse:
    """
    Upload an audio file and receive a full analysis timeline.

    The pipeline runs synchronously in the request thread.
    For files longer than ~10 minutes expect a 10-20 second response time.
    """
    # --- Validate extension ---
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    # --- Read into memory to check size, then write to temp file ---
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // (1024*1024)} MB). Max 200 MB.",
        )

    # Write to a named temp file so librosa/soundfile can open it by path.
    # delete=False so we can pass the path to the pipeline; we clean up in finally.
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        timeline = analyze_track(tmp_path)
        # Return the validated model as JSON
        return JSONResponse(content=timeline.model_dump())

    except Exception as exc:
        # Surface analysis errors as 422 so the frontend can display them
        raise HTTPException(
            status_code=422,
            detail=f"Analysis failed: {exc}",
        ) from exc

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
