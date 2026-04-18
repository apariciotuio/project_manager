"""In-memory ICache implementation — local dev and tests.

Not for production: state lives in the process, evicted on restart, no TTL-based
background eviction (expiration is checked lazily on get). Bounded by
`MAX_ENTRIES` with FIFO eviction so long-running dev servers can't OOM.
"""
from __future__ import annotations

import time
from collections import OrderedDict

from app.domain.ports.cache import ICache

MAX_ENTRIES = 10_000


class InMemoryCacheAdapter(ICache):
    def __init__(self) -> None:
        # OrderedDict keeps insertion order so we can evict the oldest entry
        # when the cap is hit.
        self._store: OrderedDict[str, tuple[str, float]] = OrderedDict()

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.monotonic() + ttl_seconds)
        while len(self._store) > MAX_ENTRIES:
            self._store.popitem(last=False)  # evict oldest

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def close(self) -> None:
        # No-op: in-memory store has no external connection to close.
        return None

    def clear(self) -> None:
        """Reset state — for test isolation only."""
        self._store.clear()
