"""
drop_detector.py

Responsibilities:
- Identify drop candidates from the labeled section list.
- Score each candidate on three independent signals:
    1. energy_delta   – RMS energy jump at the drop boundary (2s window)
    2. onset_density  – mean onset strength in first 2s after drop start
    3. spectral_flux  – peak in onset envelope right at the boundary
- Produce human-readable reason strings for each scoring factor.

Primary source: every section labeled "drop" generates one candidate at its
start time. This keeps detection deterministic and tied to the section labels
already computed.

Confidence formula:
    confidence = 0.50 * energy_score + 0.30 * onset_score + 0.20 * flux_score
where each component is clamped to [0, 1].
"""

from __future__ import annotations

import librosa
import numpy as np

from backend.schemas.timeline import Bar, DropCandidate, Section


_HOP_LENGTH = 512
_WINDOW_SEC = 2.0   # seconds on each side of boundary used for scoring


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_drop_candidates(
    y: np.ndarray,
    sr: int,
    sections: list[Section],
    bars: list[Bar],
) -> list[DropCandidate]:
    """
    Score every "drop" section boundary and return DropCandidate objects.

    Args:
        y        – mono audio array
        sr       – sample rate
        sections – list of Section objects from section_detector
        bars     – list of Bar objects (used to find bar_index for each drop)

    Returns:
        candidates – list[DropCandidate] sorted by confidence descending
    """
    if not sections:
        return []

    # Pre-compute frame-level features once
    rms_frames = librosa.feature.rms(y=y, hop_length=_HOP_LENGTH)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP_LENGTH)
    frame_times = librosa.frames_to_time(
        np.arange(len(rms_frames)), sr=sr, hop_length=_HOP_LENGTH
    )

    # Normalizers (avoid divide-by-zero)
    rms_max = float(rms_frames.max()) + 1e-8
    onset_max = float(onset_env.max()) + 1e-8

    # Build a bar-time lookup for fast bar_index resolution
    bar_starts = np.array([b.time for b in bars], dtype=np.float32)

    candidates: list[DropCandidate] = []
    drop_count = 0

    for section in sections:
        if section.label != "drop":
            continue

        drop_time = section.start
        drop_count += 1

        # Classify by order of occurrence
        drop_type = "main_drop" if drop_count == 1 else "re_drop"

        # --- Energy delta ---
        pre_mask = (frame_times >= max(0.0, drop_time - _WINDOW_SEC)) & (
            frame_times < drop_time
        )
        post_mask = (frame_times >= drop_time) & (
            frame_times < drop_time + _WINDOW_SEC
        )
        pre_energy = float(rms_frames[pre_mask].mean()) if pre_mask.any() else 0.0
        post_energy = float(rms_frames[post_mask].mean()) if post_mask.any() else 0.0
        energy_delta = post_energy - pre_energy

        # Normalize: how large is this delta relative to track peak energy?
        energy_score = float(np.clip(energy_delta / rms_max, 0.0, 1.0))

        # --- Onset density ---
        onset_score = float(
            np.clip(onset_env[post_mask].mean() / onset_max if post_mask.any() else 0.0, 0.0, 1.0)
        )

        # --- Spectral flux at boundary ---
        boundary_frame = int(np.argmin(np.abs(frame_times - drop_time)))
        flux_window = onset_env[
            max(0, boundary_frame - 3) : boundary_frame + 3
        ]
        flux_score = float(
            np.clip(flux_window.max() / onset_max if len(flux_window) > 0 else 0.0, 0.0, 1.0)
        )

        # --- Composite confidence ---
        confidence = 0.50 * energy_score + 0.30 * onset_score + 0.20 * flux_score

        # --- Reasons ---
        reasons: list[str] = []
        if energy_score > 0.4:
            reasons.append(f"energy_delta={energy_delta:.4f}")
        if onset_score > 0.4:
            reasons.append("high_onset_density")
        if flux_score > 0.5:
            reasons.append("spectral_flux_peak")
        if not reasons:
            reasons.append("section_boundary")

        # --- Bar index ---
        if len(bar_starts) > 0:
            bar_index = int(np.searchsorted(bar_starts, drop_time, side="right") - 1)
            bar_index = max(0, min(bar_index, len(bars) - 1))
        else:
            bar_index = 0

        candidates.append(DropCandidate(
            time=round(drop_time, 4),
            bar_index=bar_index,
            confidence=round(float(confidence), 3),
            type=drop_type,
            reasons=reasons,
            energy_delta=round(float(energy_delta), 6),
        ))

    # Strongest drop first
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates
