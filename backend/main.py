"""
main.py

FastAPI application entry point.

Run with:
    uvicorn backend.main:app --reload --port 8000

From the project root (the directory containing /backend).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.analyze import router as analyze_router
from backend.api.routes.export import router as export_router
from backend.api.routes.shows import router as shows_router
from backend.api.routes.templates import router as templates_router
from backend.api.routes.visualizer import router as visualizer_router

app = FastAPI(
    title="DJ Lighting — Phase 2",
    description=(
        "Audio analysis pipeline + deterministic lighting cue engine "
        "with prompt-based style customization and iterative show revision. "
        "Upload a track → optional style prompt → show payload → revise."
    ),
    version="0.2.0",
)

# Allow the frontend (served on any local port) to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/api")
app.include_router(templates_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(visualizer_router, prefix="/api")
app.include_router(shows_router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
