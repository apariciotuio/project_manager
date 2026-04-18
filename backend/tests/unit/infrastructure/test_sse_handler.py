"""RED tests for SseHandler and ChannelRegistry.

SseHandler:
  - Returns StreamingResponse with media_type text/event-stream
  - Formats data frames correctly: data: {...}\\n\\n
  - Sends event: done frame and stops
  - Sends event: error frame and stops
  - Sends keepalive comment `: keepalive\\n\\n` when idle exceeds interval
  - Unsubscribes Redis on disconnect (CancelledError)

ChannelRegistry:
  - job channel maps to sse:job:{job_id}
  - conversation channel maps to sse:thread:{thread_id}
  - user notification channel maps to sse:user:{user_id}
  - workspace presence channel maps to sse:presence:{workspace_id}
  - workspace_id scoping is embedded in prefix when provided
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Fake pub/sub for SseHandler tests
# ---------------------------------------------------------------------------


class FakePubSub:
    """Drives SseHandler with a pre-loaded event queue."""

    def __init__(self, events: list[dict[str, Any]], *, raise_cancel: bool = False) -> None:
        self._events = events
        self._raise_cancel = raise_cancel
        self.unsubscribed_channels: list[str] = []

    async def subscribe(
        self,
        channel: str,
        max_messages: int | None = None,
        poll_interval: float = 0.05,
    ) -> AsyncIterator[dict[str, Any]]:
        self.unsubscribed_channels  # just access to ensure attribute exists
        for event in self._events:
            if self._raise_cancel:
                raise asyncio.CancelledError
            yield event
        # signal done — caller must handle exhausted iterator


# ---------------------------------------------------------------------------
# ChannelRegistry tests (pure, no imports of real module yet)
# ---------------------------------------------------------------------------


def test_channel_registry_job_channel() -> None:
    from app.infrastructure.sse.channel_registry import ChannelRegistry

    reg = ChannelRegistry()
    assert reg.job("abc-123") == "sse:job:abc-123"


def test_channel_registry_conversation_channel() -> None:
    from app.infrastructure.sse.channel_registry import ChannelRegistry

    thread_id = uuid4()
    reg = ChannelRegistry()
    assert reg.conversation(thread_id) == f"sse:thread:{thread_id}"


def test_channel_registry_user_notification_channel() -> None:
    from app.infrastructure.sse.channel_registry import ChannelRegistry

    user_id = uuid4()
    reg = ChannelRegistry()
    assert reg.user_notifications(user_id) == f"sse:user:{user_id}"


def test_channel_registry_presence_channel() -> None:
    from app.infrastructure.sse.channel_registry import ChannelRegistry

    workspace_id = uuid4()
    reg = ChannelRegistry()
    assert reg.presence(workspace_id) == f"sse:presence:{workspace_id}"


def test_channel_registry_workspace_scoped_job_channel() -> None:
    """workspace_id is embedded for multi-tenant isolation when provided."""
    from app.infrastructure.sse.channel_registry import ChannelRegistry

    workspace_id = uuid4()
    reg = ChannelRegistry(workspace_id=workspace_id)
    assert reg.job("job-42") == f"sse:ws:{workspace_id}:job:job-42"


# ---------------------------------------------------------------------------
# SseHandler tests
# ---------------------------------------------------------------------------


def _make_app_with_sse_handler(
    events: list[dict[str, Any]], *, keepalive_interval: float = 60.0
) -> FastAPI:
    """Build a minimal FastAPI app that uses SseHandler for a single route."""
    from app.infrastructure.sse.sse_handler import SseHandler

    app = FastAPI()

    class _FakePubSubForHandler:
        async def subscribe(
            self,
            channel: str,
            max_messages: int | None = None,
            poll_interval: float = 0.05,
        ) -> AsyncIterator[dict[str, Any]]:
            for event in events:
                yield event

    handler = SseHandler(_FakePubSubForHandler(), keepalive_interval=keepalive_interval)  # type: ignore[arg-type]

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return handler.stream("sse:test:channel")

    return app


def test_sse_handler_returns_streaming_response_media_type() -> None:
    from app.infrastructure.sse.sse_handler import SseHandler

    class _NullPubSub:
        async def subscribe(self, channel: str, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
            return
            yield  # make it an async generator

    handler = SseHandler(_NullPubSub(), keepalive_interval=999.0)  # type: ignore[arg-type]
    resp = handler.stream("sse:test:ch")
    assert isinstance(resp, StreamingResponse)
    assert resp.media_type == "text/event-stream"


def test_sse_handler_streams_data_frame_format() -> None:
    """Each non-terminal event is formatted as: data: {...}\\n\\n"""
    events = [
        {"type": "progress", "payload": {"pct": 50}, "channel": "sse:job:1"},
    ]
    app = _make_app_with_sse_handler(events)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/stream")
    assert resp.status_code == 200
    body = resp.text
    assert "data: " in body
    # Parse first data frame
    for line in body.splitlines():
        if line.startswith("data: "):
            parsed = json.loads(line[len("data: ") :])
            assert parsed["type"] == "progress"
            break
    else:
        pytest.fail("No data: frame found in SSE stream")


def test_sse_handler_done_frame_uses_event_field() -> None:
    """event: done frame is: event: done\\ndata: {...}\\n\\n"""
    events = [
        {"type": "done", "payload": {"message_id": "msg-uuid-99"}, "channel": "sse:job:1"},
    ]
    app = _make_app_with_sse_handler(events)
    client = TestClient(app)
    resp = client.get("/stream")
    body = resp.text
    assert "event: done" in body
    # Extract payload from data line following event: done
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line == "event: done":
            data_line = lines[i + 1]
            parsed = json.loads(data_line[len("data: ") :])
            assert parsed["message_id"] == "msg-uuid-99"
            break
    else:
        pytest.fail("event: done frame not found")


def test_sse_handler_error_frame_uses_event_field() -> None:
    """event: error frame is: event: error\\ndata: {...}\\n\\n"""
    events = [
        {"type": "error", "payload": {"message": "timeout"}, "channel": "sse:job:2"},
    ]
    app = _make_app_with_sse_handler(events)
    client = TestClient(app)
    resp = client.get("/stream")
    body = resp.text
    assert "event: error" in body


def test_sse_handler_no_cache_headers() -> None:
    """StreamingResponse includes Cache-Control: no-cache and X-Accel-Buffering: no."""
    from app.infrastructure.sse.sse_handler import SseHandler

    class _NullPubSub:
        async def subscribe(self, channel: str, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
            return
            yield

    handler = SseHandler(_NullPubSub(), keepalive_interval=999.0)  # type: ignore[arg-type]
    resp = handler.stream("sse:test:ch")
    assert resp.headers.get("cache-control") == "no-cache"
    assert resp.headers.get("x-accel-buffering") == "no"


def test_sse_handler_emits_keepalive_after_idle_gap() -> None:
    """Keepalive is emitted when elapsed time since last event exceeds keepalive_interval.

    Strategy: inject an event that arrives after the keepalive window has expired.
    We fake the event loop clock so the test doesn't actually sleep.
    """
    from unittest.mock import patch

    from app.infrastructure.sse.sse_handler import SseHandler

    # Simulate: last_event_at = 0.0, now = 31.0 (> 30s interval) when next event arrives.
    times = iter([0.0, 31.0, 31.0])  # initial time, pre-event check, post-event update

    class _SlowPubSub:
        async def subscribe(
            self,
            channel: str,
            max_messages: int | None = None,
            poll_interval: float = 0.05,
        ) -> AsyncIterator[dict[str, Any]]:
            yield {"type": "done", "payload": {"message_id": "m1"}, "channel": channel}

    app = FastAPI()
    handler = SseHandler(_SlowPubSub(), keepalive_interval=30.0)  # type: ignore[arg-type]

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return handler.stream("sse:test:keepalive")

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.time.side_effect = times
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/stream")

    body = resp.text
    assert ": keepalive" in body, f"Expected keepalive comment in:\n{body}"
    assert "event: done" in body
