"""In-memory ICache implementation — local dev and tests.

Not for production: state lives in the process, evicted on restart, no TTL-based
background eviction (expiration is checked lazily on get).
"""
from __future__ import annotations

import time

from app.domain.ports.cache import ICache


class InMemoryCacheAdapter(ICache):
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}

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
        self._store[key] = (value, time.monotonic() + ttl_seconds)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def close(self) -> None:
        # For parity with RedisCacheAdapter which owns a client.
        return None
