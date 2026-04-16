"""Redis cache adapter — implements ICache using redis-py async client.

Wraps redis.asyncio.Redis so replacing the library only touches this file.
Connection is lazy (created on first use) and shared within the adapter instance.
"""
from __future__ import annotations

import redis.asyncio as aioredis

from app.domain.ports.cache import ICache


class RedisCacheAdapter(ICache):
    def __init__(self, url: str) -> None:
        self._client: aioredis.Redis = aioredis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        value: str | None = await self._client.get(key)
        return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._client.setex(key, ttl_seconds, value)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def close(self) -> None:
        await self._client.aclose()
