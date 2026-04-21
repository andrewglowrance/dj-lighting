"""
lighting/show_store.py

Simple in-memory show store keyed by UUID show_id.

Limitations (acceptable for MVP on Railway free tier):
  - Shows are lost on server restart.
  - Max 50 shows are retained (oldest evicted first) to prevent unbounded
    memory growth on a 512 MB free-tier instance.
  - Not thread-safe beyond Python's GIL; fine for single-worker Uvicorn.

Usage:
    from backend.lighting.show_store import show_store
    show_store.save(show)
    show = show_store.get(show_id)   # None if not found
    show_store.delete(show_id)
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from backend.schemas.show import Show

_MAX_SHOWS = 50


class ShowStore:
    """OrderedDict-backed LRU-like store for Show objects."""

    def __init__(self, max_size: int = _MAX_SHOWS) -> None:
        self._store: OrderedDict[str, Show] = OrderedDict()
        self._max = max_size

    # ------------------------------------------------------------------

    def generate_id(self) -> str:
        return str(uuid.uuid4())

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------

    def save(self, show: Show) -> Show:
        """Insert or update a show.  Evicts the oldest entry if over capacity."""
        if show.show_id in self._store:
            # Move to end (most recently used)
            self._store.move_to_end(show.show_id)
        self._store[show.show_id] = show
        if len(self._store) > self._max:
            self._store.popitem(last=False)  # evict oldest
        return show

    def get(self, show_id: str) -> Show | None:
        show = self._store.get(show_id)
        if show:
            self._store.move_to_end(show_id)
        return show

    def delete(self, show_id: str) -> bool:
        if show_id in self._store:
            del self._store[show_id]
            return True
        return False

    def list_ids(self) -> list[str]:
        return list(reversed(self._store.keys()))   # newest first

    def count(self) -> int:
        return len(self._store)


# Module-level singleton
show_store = ShowStore()
