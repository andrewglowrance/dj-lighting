"""
pipeline.py

Single public entry point for Phase 1 audio analysis.

Call analyze_track(filepath) → TimelineSchema.

Execution order:
  1. audio_loader.load_audio            – load file to float32 array
  2. audio_loader.get_metadata          – filename, duration, sample_rate
  3. beat_tracker.detect_beats          – BPM, confidence, beat_times array
  4. bar_builder.build_bars             – Beat and Bar schema objects
  5. section_detector.detect_sections   – Section objects with labels
  6. drop_detector.find_drop_candidates – DropCandidate objects
  7. mood_analyzer.analyze_mood         – key, mode, emotion, color_bias
  8. Assemble and return TimelineSchema

This module intentionally contains no analysis logic; it only wires modules
together. Keep it that way so each stage can be tested in isolation.
"""

from __future__ import annotations

from backend.analysis.audio_loader import get_metadata, load_audio
from backend.analysis.bar_builder import build_bars
from backend.analysis.beat_tracker import detect_beats
from backend.analysis.drop_detector import find_drop_candidates
from backend.analysis.mood_analyzer import analyze_mood, extract_beat_notes
from backend.analysis.section_detector import detect_sections
from backend.schemas.timeline import BeatNote, MoodAnalysis, TimelineSchema


def analyze_track(filepath: str) -> TimelineSchema:
    """
    Run the full Phase 1 analysis pipeline on a single audio file.

    Args:
        filepath – absolute or relative path to the audio file on disk

    Returns:
        TimelineSchema – validated Pydantic model ready to serialize to JSON

    Raises:
        Exception – any librosa/soundfile error propagates up; the API layer
                    catches and converts to HTTP 422.
    """
    # 1 & 2 – load audio + metadata
    y, sr = load_audio(filepath)
    metadata = get_metadata(filepath, y, sr)

    # 3 – beat tracking
    bpm_info, beat_times = detect_beats(y, sr)

    # 4 – bars and structured beat objects
    beats, bars = build_bars(beat_times, bpm=bpm_info.bpm)

    # 5 – section labeling
    sections = detect_sections(y, sr, bars)

    # 6 – drop candidates
    drop_candidates = find_drop_candidates(y, sr, sections, bars)

    # 7 – mood / key / emotion analysis
    mood_raw = analyze_mood(y, sr, bpm=bpm_info.bpm)
    mood = MoodAnalysis(**mood_raw)

    # 8 – per-beat note extraction (dominant pitch, energy, tone duration,
    #      key-relative degree, smoothed hue, tonal brightness)
    _NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
                   "F#", "G", "G#", "A", "A#", "B"]
    beat_note_dicts = extract_beat_notes(
        y, sr, beat_times, key_index=mood_raw["key_index"])
    beat_notes = [
        BeatNote(
            dominant_note=_NOTE_NAMES[d["dominant_note_index"]],
            **d,
        )
        for d in beat_note_dicts
    ]

    # 9 – assemble
    return TimelineSchema(
        metadata=metadata,
        bpm=bpm_info,
        beats=beats,
        bars=bars,
        sections=sections,
        drop_candidates=drop_candidates,
        mood=mood,
        beat_notes=beat_notes,
    )
