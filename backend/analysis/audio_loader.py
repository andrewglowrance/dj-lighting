"""
audio_loader.py

Responsibilities:
- Load an audio file from disk into a mono float32 numpy array.
- Extract basic track metadata (duration, sample rate).

We preserve the native sample rate rather than resampling, which keeps
downstream librosa calls accurate. All analysis modules accept (y, sr)
as their first two arguments so the loaded audio flows through unchanged.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import librosa
import numpy as np
import soundfile as sf

from backend.schemas.timeline import TrackMetadata


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_audio(filepath: str) -> tuple[np.ndarray, int]:
    """
    Load audio file to a mono float32 array at native sample rate.

    Uses soundfile for WAV/FLAC (fast, no resampling) and falls back to
    librosa's audioread backend for MP3 and other compressed formats.

    Returns:
        y  – mono float32 ndarray, amplitude range approximately [-1, 1]
        sr – sample rate in Hz
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext in (".wav", ".flac", ".aiff", ".aif"):
        # soundfile is fastest for uncompressed formats
        y, sr = sf.read(filepath, dtype="float32", always_2d=False)
        if y.ndim == 2:
            # mix down to mono
            y = y.mean(axis=1)
    else:
        # librosa handles MP3 via audioread; converts to mono automatically
        y, sr = librosa.load(filepath, sr=None, mono=True, dtype=np.float32)

    # Safety: ensure finite values only (damaged files can have NaN/inf)
    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)

    return y, int(sr)


def get_metadata(filepath: str, y: np.ndarray, sr: int) -> TrackMetadata:
    """
    Build a TrackMetadata object from the loaded audio array.

    Args:
        filepath – original upload path (used for filename only)
        y        – mono audio array from load_audio()
        sr       – sample rate from load_audio()
    """
    duration_sec = float(len(y)) / sr
    filename = os.path.basename(filepath)
    analyzed_at = datetime.now(timezone.utc).isoformat()

    return TrackMetadata(
        filename=filename,
        duration_sec=round(duration_sec, 4),
        sample_rate=sr,
        analyzed_at=analyzed_at,
    )
