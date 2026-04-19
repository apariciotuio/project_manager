"""SseHandler terminal-frame and keepalive tests.

Extends coverage beyond the existing test_sse_handler.py by specifically
targeting the terminal-frame contract and the keepalive idle path with clock
control.

Cases:
  - `event: done` frame emitted when job status is 'done'
  - `event: error` frame emitted on terminal error
  - After 'done' the generator stops (no more frames follow)
  - After 'error' the generator stops (no more frames follow)
  - Keepalive `: keepalive\\n\\n` emitted when idle gap exceeds the interval
  - Keepalive NOT emitted when idle gap is shorter than the interval
  - Multiple non-terminal events before done: all emitted, then done stops the stream
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Fake pub/sub
# ---------------------------------------------------------------------------


class FakePubSub:
    """Delivers a pre-loaded sequence of events then exhausts."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    async def subscribe(
        self,
        channel: str,
        max_messages: int | None = None,
        poll_interval: float = 0.05,
    ) -> AsyncIterator[dict[str, Any]]:
        for event in self._events:
            yield event


# ---------------------------------------------------------------------------
# Helper: build minimal FastAPI app using SseHandler
# ---------------------------------------------------------------------------


def _make_app(events: list[dict[str, Any]], *, keepalive_interval: float = 60.0) -> FastAPI:
    from app.infrastructure.sse.sse_handler import SseHandler

    app = FastAPI()
    handler = SseHandler(FakePubSub(events), keepalive_interval=keepalive_interval)  # type: ignore[arg-type]

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return handler.stream("sse:test:chan")

    return app


def _body(events: list[dict[str, Any]], *, keepalive_interval: float = 60.0) -> str:
    app = _make_app(events, keepalive_interval=keepalive_interval)
    client = TestClient(app, raise_server_exceptions=True)
    return client.get("/stream").text


# ---------------------------------------------------------------------------
# Terminal frames
# ---------------------------------------------------------------------------


def test_done_event_emits_event_done_frame() -> None:
    """type='done' → output contains 'event: done'."""
    body = _body([{"type": "done", "payload": {"job": "ok"}}])
    assert "event: done" in body


def test_done_event_payload_in_data_line() -> None:
    """Payload from type='done' is in the data: line following event: done."""
    body = _body([{"type": "done", "payload": {"status": "finished"}}])
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line == "event: done":
            data = json.loads(lines[i + 1][len("data: "):])
            assert data["status"] == "finished"
            return
    pytest.fail("event: done not found in output")


def test_error_event_emits_event_error_frame() -> None:
    """type='error' → output contains 'event: error'."""
    body = _body([{"type": "error", "payload": {"reason": "timeout"}}])
    assert "event: error" in body


def test_error_event_payload_in_data_line() -> None:
    """Payload from type='error' is accessible in the data: line."""
    body = _body([{"type": "error", "payload": {"reason": "disk_full"}}])
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line == "event: error":
            data = json.loads(lines[i + 1][len("data: "):])
            assert data["reason"] == "disk_full"
            return
    pytest.fail("event: error not found in output")


def test_done_frame_stops_generator_no_subsequent_frames() -> None:
    """After 'done', any events that would follow are not emitted."""
    events = [
        {"type": "done", "payload": {}},
        # This event must NOT appear — generator returns after done
        {"type": "progress", "payload": {"pct": 99}},
    ]
    body = _body(events)
    # 'event: done' present
    assert "event: done" in body
    # No progress data frame after done
    lines = [l for l in body.splitlines() if l.startswith("data: ")]
    # Only one data line (the done payload)
    assert len(lines) == 1


def test_error_frame_stops_generator_no_subsequent_frames() -> None:
    """After 'error', any events that would follow are not emitted."""
    events = [
        {"type": "error", "payload": {"reason": "boom"}},
        {"type": "progress", "payload": {"pct": 50}},
    ]
    body = _body(events)
    assert "event: error" in body
    lines = [l for l in body.splitlines() if l.startswith("data: ")]
    assert len(lines) == 1


def test_multiple_progress_events_before_done_all_emitted() -> None:
    """Non-terminal events all appear; stream terminates after done."""
    events = [
        {"type": "progress", "payload": {"pct": 10}},
        {"type": "progress", "payload": {"pct": 50}},
        {"type": "done", "payload": {"result": "ok"}},
    ]
    body = _body(events)
    data_lines = [l for l in body.splitlines() if l.startswith("data: ")]
    # 2 progress frames + 1 done frame = 3 data lines
    assert len(data_lines) == 3
    assert "event: done" in body


# ---------------------------------------------------------------------------
# Keepalive
# ---------------------------------------------------------------------------


def test_keepalive_emitted_when_idle_exceeds_interval() -> None:
    """: keepalive\\n\\n is emitted when elapsed time exceeds keepalive_interval."""
    from unittest.mock import patch

    from app.infrastructure.sse.sse_handler import SseHandler

    # Clock sequence: initial=0.0, pre-event check=31.0, post-event update=31.0
    times = iter([0.0, 31.0, 31.0])

    class _SlowPubSub:
        async def subscribe(
            self,
            channel: str,
            max_messages: int | None = None,
            poll_interval: float = 0.05,
        ) -> AsyncIterator[dict[str, Any]]:
            yield {"type": "done", "payload": {}}

    app = FastAPI()
    handler = SseHandler(_SlowPubSub(), keepalive_interval=30.0)  # type: ignore[arg-type]

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return handler.stream("sse:test:keepalive")

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.time.side_effect = times
        client = TestClient(app, raise_server_exceptions=True)
        body = client.get("/stream").text

    assert ": keepalive" in body, f"Expected keepalive in:\n{body}"
    assert "event: done" in body


def test_keepalive_not_emitted_when_idle_below_interval() -> None:
    """No keepalive when elapsed time is less than keepalive_interval."""
    from unittest.mock import patch

    from app.infrastructure.sse.sse_handler import SseHandler

    # Elapsed = 5s, interval = 30s → no keepalive
    times = iter([0.0, 5.0, 5.0])

    class _FastPubSub:
        async def subscribe(
            self,
            channel: str,
            max_messages: int | None = None,
            poll_interval: float = 0.05,
        ) -> AsyncIterator[dict[str, Any]]:
            yield {"type": "done", "payload": {}}

    app = FastAPI()
    handler = SseHandler(_FastPubSub(), keepalive_interval=30.0)  # type: ignore[arg-type]

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return handler.stream("sse:test:no-keepalive")

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.time.side_effect = times
        client = TestClient(app, raise_server_exceptions=True)
        body = client.get("/stream").text

    assert ": keepalive" not in body
    assert "event: done" in body


def test_keepalive_frame_format_is_sse_comment() -> None:
    """keepalive_frame() returns exactly ': keepalive\\n\\n'."""
    from app.infrastructure.sse.sse_handler import SseHandler

    assert SseHandler.keepalive_frame() == ": keepalive\n\n"
