"""Reusable SSE streaming handler.

SseHandler wraps a RedisPubSub (or compatible) source and produces a
FastAPI StreamingResponse with proper SSE framing.

Frame format:
  Regular event:  data: {...}\\n\\n
  Named event:    event: <name>\\ndata: {...}\\n\\n
  Keepalive:      : keepalive\\n\\n

Usage (EP-03, EP-08, job progress — all share this):
    handler = SseHandler(pubsub, keepalive_interval=30.0)
    return handler.stream("sse:thread:{thread_id}")

Disconnect cleanup: when the ASGI server cancels the generator (client
disconnects), asyncio.CancelledError propagates into RedisPubSub.subscribe
which always runs its finally block — unsubscribing the Redis channel.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, Protocol

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

_KEEPALIVE_COMMENT = ": keepalive\n\n"

_DEFAULT_KEEPALIVE_INTERVAL = 30.0  # seconds


class _PubSubProto(Protocol):
    def subscribe(
        self,
        channel: str,
        max_messages: int | None = None,
        poll_interval: float = 0.05,
    ) -> AsyncGenerator[dict[str, Any], None]: ...


class SseHandler:
    """Converts a pub/sub source into a FastAPI StreamingResponse.

    Args:
        pubsub: RedisPubSub instance (or any compatible Protocol).
        keepalive_interval: seconds of idle time before emitting a keepalive comment.
    """

    def __init__(
        self,
        pubsub: _PubSubProto,
        keepalive_interval: float = _DEFAULT_KEEPALIVE_INTERVAL,
    ) -> None:
        self._pubsub = pubsub
        self._keepalive_interval = keepalive_interval

    # ------------------------------------------------------------------
    # Frame helpers (static — also used by controller module)
    # ------------------------------------------------------------------

    @staticmethod
    def data_frame(data: dict[str, Any], event: str | None = None) -> str:
        """Format a standard SSE data frame."""
        lines: list[str] = []
        if event:
            lines.append(f"event: {event}")
        lines.append(f"data: {json.dumps(data)}")
        lines.append("")  # blank line separator
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def keepalive_frame() -> str:
        return _KEEPALIVE_COMMENT

    # ------------------------------------------------------------------
    # Streaming generator
    # ------------------------------------------------------------------

    async def _generate(self, channel: str) -> AsyncIterator[str]:
        last_event_at = asyncio.get_event_loop().time()

        try:
            async for event in self._pubsub.subscribe(channel):
                now = asyncio.get_event_loop().time()
                if now - last_event_at >= self._keepalive_interval:
                    yield self.keepalive_frame()

                event_type = event.get("type")
                payload = event.get("payload", event)

                if event_type == "done":
                    yield self.data_frame(payload, event="done")
                    return
                elif event_type == "error":
                    yield self.data_frame(payload, event="error")
                    return
                else:
                    yield self.data_frame(event)

                last_event_at = asyncio.get_event_loop().time()

                # Check keepalive after each event too
                now = asyncio.get_event_loop().time()
                if now - last_event_at >= self._keepalive_interval:
                    yield self.keepalive_frame()
                    last_event_at = now

        except asyncio.CancelledError:
            logger.debug("SSE client disconnected from channel %s", channel)
            # CancelledError propagates — RedisPubSub.subscribe finally block handles unsubscribe

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stream(self, channel: str) -> StreamingResponse:
        """Return a StreamingResponse that streams SSE frames from *channel*."""
        return StreamingResponse(
            self._generate(channel),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
