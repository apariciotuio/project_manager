"""ICache port — domain-level interface for a simple key-value cache.

Intentionally minimal. Domain services only need get/set/delete.
InMemoryCacheAdapter is the sole implementation. For tests, use FakeCache from tests/fakes/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ICache(ABC):
    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Return cached value or None if absent/expired."""

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Set a value with TTL. Overwrites if key exists."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a key (no-op if absent)."""
