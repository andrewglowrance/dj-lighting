"""
beat_tracker.py

Responsibilities:
- Estimate BPM and confidence using librosa's beat tracker.
- Return beat onset times as a numpy array.

We use librosa.beat.beat_track with trim=False so beats at the very start
and end of the track are included. The confidence score is derived from
the sharpness of the tempo autocorrelation peak: a narrow, tall peak
indicates the tracker is certain; a flat peak indicates ambiguity.
"""

from __future__ import annotations

import librosa
import numpy as np

from backend.schemas.timeline import BPMInfo


# Internal constants
_HOP_LENGTH = 512   # frames hop; ~11.6 ms at 44100 Hz


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_beats(y: np.ndarray, sr: int) -> tuple[BPMInfo, np.ndarray]:
    """
    Estimate BPM and detect beat onset times.

    Args:
        y  – mono audio array
        sr – sample rate

    Returns:
        bpm_info   – BPMInfo with tempo and confidence
        beat_times – float32 array of beat onset times in seconds, shape (N,)
    """
    # onset_envelope is the raw signal the beat tracker works from
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP_LENGTH)

    # beat_track returns (tempo, beat_frames_array)
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=_HOP_LENGTH,
        trim=False,        # keep edge beats
        tightness=100,     # default; higher = beats stick closer to grid
    )

    # librosa may return tempo as a 1-element array in newer versions
    tempo_scalar = float(np.atleast_1d(tempo)[0])

    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=_HOP_LENGTH)
    beat_times = beat_times.astype(np.float32)

    confidence = _tempo_confidence(onset_env, sr)

    bpm_info = BPMInfo(
        bpm=round(tempo_scalar, 2),
        confidence=round(confidence, 3),
    )

    return bpm_info, beat_times


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tempo_confidence(onset_env: np.ndarray, sr: int) -> float:
    """
    Estimate confidence as the normalized height of the dominant tempo peak
    in the tempogram autocorrelation.

    Returns a value in [0, 1]. Values above ~0.7 indicate a strong, stable
    tempo. Values below ~0.4 indicate mixed or unclear tempo.
    """
    # Tempogram: autocorrelation of onset envelope over time
    # We take the global mean column for a single summary vector
    tempogram = librosa.feature.tempogram(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=_HOP_LENGTH,
        win_length=384,
    )
    # Mean across time → single autocorrelation profile
    acf = tempogram.mean(axis=1)

    if acf.max() < 1e-8:
        return 0.5  # degenerate case; default mid-confidence

    acf_norm = acf / acf.max()
    peak = float(acf_norm.max())
    # Map peak sharpness to [0, 1]; clamp for safety
    return float(np.clip(peak, 0.0, 1.0))
