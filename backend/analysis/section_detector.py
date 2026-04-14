"""
section_detector.py

Responsibilities:
- Compute per-bar energy and onset density features.
- Label each bar with a section type using energy-based heuristics.
- Merge consecutive same-label bars into Section objects.

Labeling strategy (in order of precedence):

  1. intro  – leading bars where smoothed energy stays below the track median.
              Capped at 32 bars to avoid mislabeling long high-energy intros.
  2. outro  – trailing bars with the same low-energy criterion.
  3. drop   – middle bars where norm_energy > 0.65 AND norm_onset_density > 0.45.
              These are the densest, loudest moments.
  4. breakdown – middle bars where norm_energy < 0.35 (quiet valley between sections).
  5. build  – unlabeled middle bars that precede a drop within 8 bars (energy is
              rising toward the drop).
  6. drop   – any remaining unlabeled middle bar above the median (sustained energy).
  7. build  – any remaining unlabeled middle bar (catch-all for gaps).

This is intentionally simple. The rules are easy to tune by adjusting the
threshold constants at the top of this file.
"""

from __future__ import annotations

import librosa
import numpy as np

from backend.schemas.timeline import Bar, Section, SectionLabel


# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

_HOP_LENGTH = 512
_SMOOTHING_WINDOW = 4       # bars to convolve for energy smoothing
_INTRO_OUTRO_ENERGY = 1.10  # factor of median; bars below this qualify as intro/outro
_DROP_ENERGY_THRESH = 0.65  # normalized energy threshold for a drop
_DROP_ONSET_THRESH = 0.45   # normalized onset density threshold for a drop
_BREAKDOWN_ENERGY_THRESH = 0.35  # normalized energy threshold for a breakdown
_BUILD_LOOK_AHEAD = 8       # bars ahead to scan for an upcoming drop
_MAX_INTRO_BARS = 32
_MAX_OUTRO_BARS = 32


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_sections(y: np.ndarray, sr: int, bars: list[Bar]) -> list[Section]:
    """
    Label bars and return merged Section objects.

    Args:
        y    – mono audio array
        sr   – sample rate
        bars – list of Bar objects from bar_builder

    Returns:
        sections – list[Section] ordered by start time, no gaps, no overlaps
    """
    if not bars:
        return []

    bar_energy, bar_onset_density = _compute_bar_features(y, sr, bars)
    labels = _label_bars(bar_energy, bar_onset_density)

    return _merge_to_sections(bars, labels, bar_energy)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_bar_features(
    y: np.ndarray, sr: int, bars: list[Bar]
) -> tuple[np.ndarray, np.ndarray]:
    """
    For each bar compute:
      - mean RMS energy (raw amplitude, not dB)
      - onset density in onsets/second
    """
    # Frame-level RMS
    rms_frames = librosa.feature.rms(y=y, hop_length=_HOP_LENGTH)[0]
    frame_times = librosa.frames_to_time(
        np.arange(len(rms_frames)), sr=sr, hop_length=_HOP_LENGTH
    )

    # Onset times
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP_LENGTH)
    onset_times = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=_HOP_LENGTH, units="time"
    )

    bar_energy = np.zeros(len(bars), dtype=np.float32)
    bar_onset_density = np.zeros(len(bars), dtype=np.float32)

    for i, bar in enumerate(bars):
        bar_end = bar.time + bar.duration

        # Mean RMS within bar's time range
        mask = (frame_times >= bar.time) & (frame_times < bar_end)
        if mask.any():
            bar_energy[i] = float(rms_frames[mask].mean())

        # Onsets per second within bar
        bar_onsets = np.sum((onset_times >= bar.time) & (onset_times < bar_end))
        bar_onset_density[i] = float(bar_onsets) / max(bar.duration, 1e-3)

    return bar_energy, bar_onset_density


def _label_bars(
    bar_energy: np.ndarray, bar_onset_density: np.ndarray
) -> list[SectionLabel]:
    """
    Apply heuristic rules to produce a section label for every bar.
    """
    n = len(bar_energy)
    e_min, e_max = bar_energy.min(), bar_energy.max()
    o_min, o_max = bar_onset_density.min(), bar_onset_density.max()

    # Normalize to [0, 1]
    norm_e = (bar_energy - e_min) / (e_max - e_min + 1e-8)
    norm_o = (bar_onset_density - o_min) / (o_max - o_min + 1e-8)

    # Smooth energy over a rolling window so single-bar spikes don't confuse labeling
    w = min(_SMOOTHING_WINDOW, n)
    smoothed_e = np.convolve(norm_e, np.ones(w) / w, mode="same")

    median_e = float(np.median(smoothed_e))

    labels: list[SectionLabel | None] = [None] * n

    # --- Step 1: Intro ---
    intro_end = 0
    for i in range(min(n, _MAX_INTRO_BARS)):
        if smoothed_e[i] < median_e * _INTRO_OUTRO_ENERGY:
            intro_end = i + 1
        else:
            break
    intro_end = max(intro_end, min(4, n))  # always assign at least 4 bars as intro
    for i in range(intro_end):
        labels[i] = "intro"

    # --- Step 2: Outro ---
    outro_start = n
    for i in range(n - 1, max(n - _MAX_OUTRO_BARS - 1, -1), -1):
        if smoothed_e[i] < median_e * _INTRO_OUTRO_ENERGY:
            outro_start = i
        else:
            break
    # Outro must start after intro ends and cover at least 4 bars
    outro_start = max(outro_start, intro_end)
    outro_start = min(outro_start, max(n - 4, intro_end))
    for i in range(outro_start, n):
        labels[i] = "outro"

    # --- Step 3: Drop (high energy + high onset density) ---
    for i in range(intro_end, outro_start):
        if smoothed_e[i] > _DROP_ENERGY_THRESH and norm_o[i] > _DROP_ONSET_THRESH:
            labels[i] = "drop"

    # --- Step 4: Breakdown (low energy valley in middle) ---
    for i in range(intro_end, outro_start):
        if labels[i] is None and smoothed_e[i] < _BREAKDOWN_ENERGY_THRESH:
            labels[i] = "breakdown"

    # --- Step 5: Build (unlabeled bars that precede a drop) ---
    for i in range(intro_end, outro_start):
        if labels[i] is not None:
            continue
        horizon = min(i + _BUILD_LOOK_AHEAD, outro_start)
        if any(labels[j] == "drop" for j in range(i, horizon)):
            labels[i] = "build"

    # --- Step 6 & 7: Fill remaining ---
    for i in range(intro_end, outro_start):
        if labels[i] is None:
            labels[i] = "drop" if smoothed_e[i] > median_e else "build"

    return labels  # type: ignore[return-value]  # all None replaced above


def _merge_to_sections(
    bars: list[Bar],
    labels: list[SectionLabel],
    bar_energy: np.ndarray,
) -> list[Section]:
    """
    Merge consecutive bars sharing the same label into Section objects.
    Energy stats are aggregated across each merged group.
    """
    if not bars:
        return []

    # Normalize raw energy once for the energy_mean/peak fields
    e_min, e_max = bar_energy.min(), bar_energy.max()
    norm_e = (bar_energy - e_min) / (e_max - e_min + 1e-8)

    sections: list[Section] = []
    current_label = labels[0]
    group_start = 0

    def _flush(group_start: int, group_end_exclusive: int, label: SectionLabel) -> None:
        group_bars = bars[group_start:group_end_exclusive]
        group_norm = norm_e[group_start:group_end_exclusive]

        start_time = group_bars[0].time
        end_time = group_bars[-1].time + group_bars[-1].duration

        sections.append(Section(
            label=label,
            start=round(start_time, 4),
            end=round(end_time, 4),
            bar_start=group_bars[0].index,
            bar_end=group_bars[-1].index + 1,   # exclusive
            energy_mean=round(float(group_norm.mean()), 4),
            energy_peak=round(float(group_norm.max()), 4),
        ))

    for i in range(1, len(labels)):
        if labels[i] != current_label:
            _flush(group_start, i, current_label)
            group_start = i
            current_label = labels[i]

    _flush(group_start, len(labels), current_label)

    return sections
