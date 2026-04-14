"""
bar_builder.py

Responsibilities:
- Group detected beats into bars of 4 (4/4 time assumed for DJ/EDM tracks).
- Return Beat and Bar schema objects with all index cross-references populated.

The first beat in each bar gets beat_in_bar=0; subsequent beats are 1, 2, 3.
Any trailing beats that don't fill a complete bar are still grouped into a
partial bar (common at the end of a track).
"""

from __future__ import annotations

import numpy as np

from backend.schemas.timeline import Beat, Bar


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_bars(
    beat_times: np.ndarray,
    bpm: float,
    time_sig: int = 4,
) -> tuple[list[Beat], list[Bar]]:
    """
    Convert a flat beat-times array into Beat and Bar schema objects.

    Args:
        beat_times – array of beat onset times in seconds (from beat_tracker)
        bpm        – estimated tempo (used to compute bar duration fallback)
        time_sig   – beats per bar; 4 for 4/4 (only supported value in v1)

    Returns:
        beats – list[Beat], one per entry in beat_times
        bars  – list[Bar], grouped by time_sig beats each
    """
    beats: list[Beat] = []
    bars: list[Bar] = []

    beat_duration = 60.0 / bpm  # nominal duration of one beat in seconds

    n_beats = len(beat_times)
    bar_index = 0

    for bar_start_beat in range(0, n_beats, time_sig):
        bar_beat_indices = list(range(bar_start_beat, min(bar_start_beat + time_sig, n_beats)))

        # Create Beat objects for this bar
        for pos, global_beat_idx in enumerate(bar_beat_indices):
            beats.append(Beat(
                index=global_beat_idx,
                time=round(float(beat_times[global_beat_idx]), 4),
                bar_index=bar_index,
                beat_in_bar=pos,
            ))

        # Bar duration: use actual time span if we have 2+ beats, else infer from BPM
        bar_time = float(beat_times[bar_beat_indices[0]])
        if len(bar_beat_indices) >= 2:
            last_beat_time = float(beat_times[bar_beat_indices[-1]])
            bar_duration = (last_beat_time - bar_time) + beat_duration
        else:
            bar_duration = beat_duration * time_sig

        bars.append(Bar(
            index=bar_index,
            time=round(bar_time, 4),
            duration=round(bar_duration, 4),
            beat_indices=bar_beat_indices,
        ))

        bar_index += 1

    return beats, bars
