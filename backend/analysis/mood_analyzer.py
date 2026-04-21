"""
analysis/mood_analyzer.py

Derives musical key, mode, and emotional profile from audio using
chromagram analysis and the Krumhansl-Schmuckler (1990) key profiles.

Also extracts per-beat note data (dominant pitch, chroma intensity, onset
strength, RMS energy, estimated tone duration) for note-responsive lighting.

All librosa imports are deferred to function bodies to keep startup RAM low
(librosa + numba ≈ 600-800 MB; lazy-loading keeps cold-start below 150 MB).

Public API
----------
analyze_mood(y, sr, bpm)              -> MoodResult dict
extract_beat_notes(y, sr, beat_times) -> list[dict]  (one entry per beat)
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


# ---------------------------------------------------------------------------
# Key-relative hue mapping tables
# ---------------------------------------------------------------------------

# For each of the 12 chromatic scale degrees relative to the tonic,
# the hue offset applied to the key's base hue (in [0, 1] = full wheel).
# Design principle: harmonically close intervals (P5=7, M3=4) stay near
# the tonic hue; the tritone (6) gets the largest shift; semitones drift
# slightly so adjacent melody notes look similar, not wildly different.
_DEGREE_HUE_SHIFT: list[float] = [
    0.00,   # 0  Tonic         — anchor, no shift
    0.07,   # 1  min2          — tiny warm drift
    0.12,   # 2  Maj2          — small warm drift
   -0.10,   # 3  min3          — slight cool shift (darker)
    0.16,   # 4  Maj3          — warm, consonant chord tone
    0.21,   # 5  P4            — moderate warm
    0.38,   # 6  Tritone       — furthest from tonic (complementary-ish)
    0.04,   # 7  P5            — very close to tonic, slightly warm
   -0.16,   # 8  min6          — cool/dark
    0.19,   # 9  Maj6          — analogous warm
   -0.06,   # 10 min7          — slightly cool
    0.09,   # 11 Maj7          — small warm, leading tone
]

# Tonal stability per degree: 1 = fully settled, lower = more tension/colour.
# Used to scale tonal_brightness so unstable notes look dimmer/cooler.
_DEGREE_STABILITY: list[float] = [
    1.00,   # 0  Tonic
    0.58,   # 1  min2
    0.80,   # 2  Maj2
    0.84,   # 3  min3
    0.90,   # 4  Maj3
    0.82,   # 5  P4
    0.55,   # 6  Tritone
    0.95,   # 7  P5
    0.76,   # 8  min6
    0.86,   # 9  Maj6
    0.72,   # 10 min7
    0.74,   # 11 Maj7
]

# Key index (0–11, C=0) → base hue [0, 1].
# Distributed around the circle-of-fifths so keys a fifth apart share
# similar hues (warm keys: G, D, A; cool keys: Bb, Eb, Ab; neutral: C, F).
_KEY_BASE_HUE: list[float] = [
    0.00,   # C  — red anchor
    0.57,   # C# — cyan-blue
    0.08,   # D  — orange-red
    0.65,   # D# — blue-violet
    0.14,   # E  — orange
    0.42,   # F  — green-cyan
    0.72,   # F# — violet
    0.20,   # G  — yellow-green
    0.50,   # G# — cyan
    0.28,   # A  — green
    0.78,   # A# — purple
    0.35,   # B  — teal-green
]


def _smooth_hues(
    raw_hues: list[float],
    alpha: float = 0.35,
) -> list[float]:
    """
    Exponential moving average on circular hue values.
    alpha: weight of new value (0=fully smooth, 1=no smoothing).
    Handles the 0/1 wraparound by tracking the shortest arc each step.
    """
    if not raw_hues:
        return []
    smoothed = [raw_hues[0]]
    for h in raw_hues[1:]:
        prev = smoothed[-1]
        diff = h - prev
        # Choose the shorter arc around the hue circle
        if diff > 0.5:
            diff -= 1.0
        elif diff < -0.5:
            diff += 1.0
        smoothed.append(prev + alpha * diff)
    return smoothed


# ---------------------------------------------------------------------------
# Per-beat note extraction
# ---------------------------------------------------------------------------

_HOP_LENGTH = 512  # librosa default hop length used throughout


def extract_beat_notes(
    y: np.ndarray,
    sr: int,
    beat_times: np.ndarray,
    key_index: int = 0,
) -> list[dict]:
    """
    For each beat, extract the dominant chromatic note, its intensity, onset
    salience, normalised RMS energy, and an estimate of how many consecutive
    beats share the same dominant pitch class (tone duration).

    Additionally computes three fields that drive smooth, key-coherent color:
        key_relative_degree  – scale degree relative to song key (0–11)
        smoothed_hue         – EMA-smoothed hue [0, 1] for wash color
        tonal_brightness     – harmonic stability × chroma clarity [0, 1]

    All heavy computation uses the same hop_length as the rest of the pipeline
    (512) so frame indices are consistent.

    Parameters
    ----------
    y          : float32 mono audio array
    sr         : sample rate
    beat_times : 1-D float array of beat onset times in seconds
    key_index  : chromatic pitch class of the detected key (0 = C, …, 11 = B)

    Returns
    -------
    list[dict] — one dict per beat with keys:
        beat_index           int    global beat index (matches Beat.index)
        dominant_note_index  int    chromatic pitch class 0-11  (0 = C)
        chroma_intensity     float  [0, 1]  strength of the dominant pitch
        onset_strength       float  [0, 1]  normalised onset salience
        rms_energy           float  [0, 1]  normalised RMS at this beat
        tone_duration_beats  float  estimated beats the note persists (≥ 1)
        key_relative_degree  int    scale degree vs. key tonic (0–11)
        smoothed_hue         float  [0, 1] EMA-smoothed HSL hue for color
        tonal_brightness     float  [0, 1] harmonic stability × chroma clarity
    """
    import librosa  # lazy — do not move to module level

    if len(beat_times) == 0:
        return []

    # Isolate harmonic content (removes transients from chroma)
    y_harm = librosa.effects.harmonic(y, margin=4)

    # CQT chromagram — 12 pitch classes, full octave resolution
    chroma = librosa.feature.chroma_cqt(
        y=y_harm, sr=sr, bins_per_octave=36, hop_length=_HOP_LENGTH
    )  # shape: (12, n_frames)

    # Onset strength envelope
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP_LENGTH)
    onset_max = max(float(onset_env.max()), 1e-6)

    # RMS energy envelope
    rms = librosa.feature.rms(y=y, hop_length=_HOP_LENGTH)[0]
    rms_max = max(float(rms.max()), 1e-6)

    n_frames = chroma.shape[1]
    n_beats = len(beat_times)

    # Convert beat times → frame indices (clipped to valid range)
    beat_frames = np.clip(
        librosa.time_to_frames(beat_times, sr=sr, hop_length=_HOP_LENGTH),
        0,
        n_frames - 1,
    ).astype(int)

    result: list[dict] = []

    for i in range(n_beats):
        frame = int(beat_frames[i])

        # Window: this beat's frame up to (but not including) the next beat's frame
        if i < n_beats - 1:
            next_frame = int(beat_frames[i + 1])
        else:
            # Last beat: use a half-second window
            next_frame = min(frame + max(1, int(0.5 * sr / _HOP_LENGTH)), n_frames)
        next_frame = max(next_frame, frame + 1)

        # ── Dominant pitch class ─────────────────────────────────────────────
        ch_window = chroma[:, frame:next_frame]      # (12, window)
        chroma_mean = ch_window.mean(axis=1)          # (12,)

        dominant_idx = int(chroma_mean.argmax())
        chroma_peak = float(chroma_mean[dominant_idx])
        # Normalise: typical chroma peak ≈ 0.4–0.8; clip to [0, 1]
        chroma_intensity = float(np.clip(chroma_peak / 0.75, 0.0, 1.0))

        # ── Onset strength ───────────────────────────────────────────────────
        env_idx = min(frame, len(onset_env) - 1)
        onset_strength = float(np.clip(onset_env[env_idx] / onset_max, 0.0, 1.0))

        # ── RMS energy ───────────────────────────────────────────────────────
        rms_idx = min(frame, len(rms) - 1)
        rms_norm = float(np.clip(rms[rms_idx] / rms_max, 0.0, 1.0))

        # ── Tone duration: consecutive beats sharing the same dominant note ──
        tone_dur = 1.0
        for j in range(i + 1, min(i + 8, n_beats)):
            f_j = int(beat_frames[j])
            f_next = int(beat_frames[j + 1]) if j < n_beats - 1 else min(
                f_j + max(1, int(0.5 * sr / _HOP_LENGTH)), n_frames)
            f_next = max(f_next, f_j + 1)
            ch_j = chroma[:, f_j:f_next].mean(axis=1)
            if int(ch_j.argmax()) == dominant_idx:
                tone_dur += 1.0
            else:
                break

        result.append({
            "beat_index":          i,
            "dominant_note_index": dominant_idx,
            "chroma_intensity":    round(chroma_intensity, 3),
            "onset_strength":      round(onset_strength, 3),
            "rms_energy":          round(rms_norm, 3),
            "tone_duration_beats": round(tone_dur, 1),
        })

    # ── Key-relative hue + EMA smoothing ────────────────────────────────────
    ki = int(key_index) % 12
    base_hue = _KEY_BASE_HUE[ki]

    # Raw per-beat hue from key-relative degree
    raw_hues: list[float] = []
    for d in result:
        degree = (d["dominant_note_index"] - ki) % 12
        raw_hues.append(base_hue + _DEGREE_HUE_SHIFT[degree])

    # EMA-smooth so melodic motion drifts rather than jumping
    smoothed = _smooth_hues(raw_hues, alpha=0.35)

    # Attach new fields to each entry
    for i, d in enumerate(result):
        degree = (d["dominant_note_index"] - ki) % 12
        stability = _DEGREE_STABILITY[degree]
        tonal_brightness = float(np.clip(
            stability * (0.55 + 0.45 * d["chroma_intensity"]), 0.0, 1.0))
        d["key_relative_degree"] = degree
        d["smoothed_hue"]        = round(float(smoothed[i]) % 1.0, 4)
        d["tonal_brightness"]    = round(tonal_brightness, 3)

    return result
