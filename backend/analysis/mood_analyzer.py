"""
analysis/mood_analyzer.py

Derives musical key, mode, and emotional profile from audio using
chromagram analysis and the Krumhansl-Schmuckler (1990) key profiles.

All librosa imports are deferred to function bodies to keep startup RAM low
(librosa + numba ≈ 600-800 MB; lazy-loading keeps cold-start below 150 MB).

Public API
----------
analyze_mood(y, sr, bpm) -> MoodResult dict
"""

from __future__ import annotations
import numpy as np

# ---------------------------------------------------------------------------
# Krumhansl-Schmuckler key profiles
# Each array is the expected pitch-class salience for that mode, starting on C.
# ---------------------------------------------------------------------------
_MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
    2.52, 5.19, 2.39, 3.66, 2.29, 2.88,
])
_MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
    2.54, 4.75, 3.98, 2.69, 3.34, 3.17,
])

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
               "F#", "G", "G#", "A", "A#", "B"]

# Emotion → palette key mapping (must match COLORS dict in rules.py)
_EMOTION_COLOR: dict[str, str] = {
    "euphoric":    "pure_white",
    "uplifting":   "warm_amber",
    "dark":        "deep_purple",
    "melancholic": "cool_blue",
    "intense":     "drop_red",
    "chill":       "breakdown_teal",
}

# Key index → color temperature bias for the visualizer (warm / cool / neutral)
# Follows loose circle-of-fifths associations used in stage lighting design.
_KEY_TEMPERATURE: dict[int, str] = {
    0:  "neutral",   # C
    1:  "cool",      # C#
    2:  "warm",      # D
    3:  "cool",      # D#
    4:  "warm",      # E
    5:  "neutral",   # F
    6:  "cool",      # F#
    7:  "warm",      # G
    8:  "cool",      # G#
    9:  "warm",      # A
    10: "neutral",   # A#
    11: "cool",      # B
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ks_correlate(chroma_mean: np.ndarray, profile: np.ndarray) -> np.ndarray:
    """Pearson correlation of chroma vector against all 12 cyclic rotations."""
    scores = np.zeros(12)
    for i in range(12):
        rotated = np.roll(profile, i)
        scores[i] = float(np.corrcoef(chroma_mean, rotated)[0, 1])
    return scores


def _classify_emotion(valence: float, energy: float) -> str:
    if valence > 0.60 and energy > 0.65:
        return "euphoric"
    if valence > 0.60 and energy <= 0.65:
        return "uplifting"
    if valence <= 0.40 and energy > 0.65:
        return "intense"
    if valence <= 0.40 and energy > 0.40:
        return "dark"
    if valence <= 0.40 and energy <= 0.40:
        return "melancholic"
    return "chill"   # mid-valence, mid-energy


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_mood(y: np.ndarray, sr: int, bpm: float) -> dict:
    """
    Analyse musical key, mode, and emotional profile of an audio clip.

    Parameters
    ----------
    y   : float32 mono audio array
    sr  : sample rate in Hz
    bpm : already-detected tempo (used for energy-normalisation context)

    Returns
    -------
    dict with keys:
      key_note      str   – e.g. "A", "F#"
      mode          str   – "major" | "minor"
      key_label     str   – e.g. "A minor"
      key_index     int   – chromatic pitch class [0-11], 0=C
      temperature   str   – "warm" | "cool" | "neutral"
      valence       float – [0, 1]  emotional positivity
      energy        float – [0, 1]  perceived energy level
      emotion       str   – one of six labels (see _classify_emotion)
      color_bias    str   – palette key from rules.COLORS for wash base color
    """
    import librosa  # lazy — do not move to module level

    # ── 1. Isolate harmonic content (suppress drums from chroma) ──────────
    y_harm = librosa.effects.harmonic(y, margin=4)

    # ── 2. Chromagram via CQT (better pitch resolution than STFT chroma) ─
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, bins_per_octave=36)
    chroma_mean = chroma.mean(axis=1)  # shape (12,)

    # ── 3. Krumhansl-Schmuckler key detection ────────────────────────────
    major_scores = _ks_correlate(chroma_mean, _MAJOR_PROFILE)
    minor_scores = _ks_correlate(chroma_mean, _MINOR_PROFILE)

    best_major = int(np.argmax(major_scores))
    best_minor = int(np.argmax(minor_scores))

    if major_scores[best_major] >= minor_scores[best_minor]:
        key_idx = best_major
        mode = "major"
    else:
        key_idx = best_minor
        mode = "minor"

    key_note  = _NOTE_NAMES[key_idx]
    key_label = f"{key_note} {mode}"

    # ── 4. Valence: mode + tempo both contribute ──────────────────────────
    base_valence   = 0.65 if mode == "major" else 0.35
    tempo_factor   = float(np.clip(bpm / 175.0, 0.0, 1.0))  # 175 BPM ceiling
    valence        = float(np.clip(base_valence * 0.70 + tempo_factor * 0.30, 0.0, 1.0))

    # ── 5. Energy: normalised RMS (empirically scaled to [0, 1]) ─────────
    rms    = float(np.sqrt(np.mean(y ** 2)))
    energy = float(np.clip(rms * 14.0, 0.0, 1.0))

    # ── 6. Emotion label + color bias ─────────────────────────────────────
    emotion    = _classify_emotion(valence, energy)
    color_bias = _EMOTION_COLOR.get(emotion, "cool_blue")
    temperature = _KEY_TEMPERATURE.get(key_idx, "neutral")

    return {
        "key_note":    key_note,
        "mode":        mode,
        "key_label":   key_label,
        "key_index":   key_idx,
        "temperature": temperature,
        "valence":     round(valence, 3),
        "energy":      round(energy, 3),
        "emotion":     emotion,
        "color_bias":  color_bias,
    }
