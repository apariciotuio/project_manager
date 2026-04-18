"""Redis pub/sub wrapper for SSE channel management.

publish(channel, message) — serializes to JSON and publishes.
subscribe(channel, max_messages) — async iterator that yields deserialized dicts.

The `max_messages` parameter is used only in tests to bound the iteration;
in production the iterator runs until the caller's generator is closed
(GeneratorExit / asyncio.CancelledError).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Protocol


class _RedisProto(Protocol):
    def pubsub(self) -> Any: ...
    async def publish(self, channel: str, message: str) -> None: ...


class RedisPubSub:
    def __init__(self, redis: _RedisProto) -> None:
        self._redis = redis

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        payload = {**message, "channel": channel}
        await self._redis.publish(channel, json.dumps(payload))

    async def subscribe(
        self,
        channel: str,
        max_messages: int | None = None,
        poll_interval: float = 0.05,
    ) -> AsyncIterator[dict[str, Any]]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        count = 0
        try:
            while max_messages is None or count < max_messages:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=poll_interval
                )
                if msg is not None and msg.get("type") == "message":
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    try:
                        yield json.loads(data)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    count += 1
                elif max_messages is not None:
                    # No message yet — tiny sleep to avoid busy-loop in tests
                    await asyncio.sleep(poll_interval)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
