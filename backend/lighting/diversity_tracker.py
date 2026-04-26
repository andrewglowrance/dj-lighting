"""
lighting/diversity_tracker.py

Deterministic anti-repetition tracker for motion family selection.

Uses MD5-seeded selection (no random.random()) so the same track always
produces the same choreography given the same fingerprint.
"""

from __future__ import annotations

import hashlib
from collections import deque


class DiversityTracker:
    """
    Tracks recently used motion families, laser patterns, palettes, and
    spatial zones to penalise immediate reuse.

    All selection is deterministic — driven by MD5 hash of a fingerprint
    string rather than random.random().
    """

    def __init__(self, window_size: int = 4, fingerprint: str = "default") -> None:
        self._window_size = window_size
        self._fingerprint = fingerprint
        self._selection_counter: int = 0

        self.recent_motion_families: deque[str] = deque(maxlen=window_size)
        self.recent_laser_patterns: deque[str] = deque(maxlen=window_size)
        self.recent_palettes: deque[str] = deque(maxlen=window_size)
        self.recent_spatial_zones: deque[frozenset[str]] = deque(maxlen=window_size)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_section(
        self,
        motion_family: str,
        laser_pattern: str | None = None,
        palette: str | None = None,
        spatial_zones: set[str] | None = None,
    ) -> None:
        """Record the selections made for one section."""
        self.recent_motion_families.append(motion_family)
        if laser_pattern is not None:
            self.recent_laser_patterns.append(laser_pattern)
        if palette is not None:
            self.recent_palettes.append(palette)
        if spatial_zones is not None:
            self.recent_spatial_zones.append(frozenset(spatial_zones))

    # ------------------------------------------------------------------
    # Penalty computation
    # ------------------------------------------------------------------

    def motion_penalty(self, family: str) -> float:
        """
        Return a penalty in [0.0, 1.0] based on how recently this family was used.

        Age 0 (most recent) → 1.00
        Age 1               → 0.75
        Age 2               → 0.50
        Age 3               → 0.25
        Not found           → 0.00
        """
        history = list(self.recent_motion_families)
        # Most recent is at the end; age 0 = history[-1]
        for age, entry in enumerate(reversed(history)):
            if entry == family:
                penalty_map = {0: 1.00, 1: 0.75, 2: 0.50, 3: 0.25}
                return penalty_map.get(age, 0.0)
        return 0.0

    def zone_penalty(self, zones: set[str]) -> float:
        """
        Return a penalty in [0.0, 1.0] based on how recently this zone combo was used.

        Uses the same age-based decay as motion_penalty.
        """
        target = frozenset(zones)
        history = list(self.recent_spatial_zones)
        for age, entry in enumerate(reversed(history)):
            if entry == target:
                penalty_map = {0: 1.00, 1: 0.75, 2: 0.50, 3: 0.25}
                return penalty_map.get(age, 0.0)
        return 0.0

    # ------------------------------------------------------------------
    # Deterministic selection
    # ------------------------------------------------------------------

    def select_motion(
        self,
        candidates: list[str],
        base_weights: list[float] | None = None,
        section_index: int = 0,
        role: str = "main",
    ) -> str:
        """
        Deterministically select a motion family from candidates.

        Applies diversity penalty:
            adjusted_weight = max(0.01, base_weight * (1 - 0.80 * penalty))

        Selection uses MD5 hash for a float in [0, 1) which is mapped via
        cumulative weight distribution.  No random.random() used.

        Increments _selection_counter for hash uniqueness across calls.
        """
        if not candidates:
            return "slow_drift"  # safe fallback

        n = len(candidates)
        if base_weights is None:
            weights = [1.0] * n
        else:
            # Pad or truncate to match candidates length
            weights = list(base_weights[:n])
            while len(weights) < n:
                weights.append(1.0)

        # Apply diversity penalties
        adjusted: list[float] = []
        for name, w in zip(candidates, weights):
            penalty = self.motion_penalty(name)
            adj = max(0.01, w * (1.0 - 0.80 * penalty))
            adjusted.append(adj)

        # Compute cumulative distribution
        total = sum(adjusted)
        cumulative: list[float] = []
        running = 0.0
        for w in adjusted:
            running += w / total
            cumulative.append(running)

        # Deterministic float in [0, 1) via MD5
        hash_key = (
            f"{self._fingerprint}|{section_index}|{role}|{self._selection_counter}"
        )
        digest = hashlib.md5(hash_key.encode()).hexdigest()
        # Use first 8 hex chars → integer in [0, 16^8 - 1]
        hash_int = int(digest[:8], 16)
        rand_float = hash_int / (16 ** 8)  # in [0, 1)

        self._selection_counter += 1

        # Pick via cumulative distribution
        for name, threshold in zip(candidates, cumulative):
            if rand_float < threshold:
                return name

        # Fallback: last candidate
        return candidates[-1]

    # ------------------------------------------------------------------
    # Debugging
    # ------------------------------------------------------------------

    def history_report(self) -> dict:
        """Return all recent history for debugging."""
        return {
            "recent_motion_families": list(self.recent_motion_families),
            "recent_laser_patterns": list(self.recent_laser_patterns),
            "recent_palettes": list(self.recent_palettes),
            "recent_spatial_zones": [list(z) for z in self.recent_spatial_zones],
            "selection_counter": self._selection_counter,
            "fingerprint": self._fingerprint,
        }
