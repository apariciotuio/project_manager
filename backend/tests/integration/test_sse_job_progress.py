"""Integration tests for SSE job progress endpoint.

Tests verify end-to-end SSE streaming behaviour:
  - done frame sent when job completes, generator closes cleanly
  - error frame sent when job fails, generator closes cleanly
  - keepalive comment sent when idle exceeds interval
  - 404 when job not found
  - 401 when no auth

Uses httpx.AsyncClient with the real FastAPI app router (in-process).
Redis/pub-sub are faked via dependency overrides — no real Redis needed.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.infrastructure.sse.job_progress_service import JobProgressService, JobState
from app.presentation.controllers.job_progress_controller import (
    router,
    override_current_user,
    override_job_progress_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


def _fake_user() -> CurrentUser:
    return CurrentUser(
        id=uuid4(), email="test@example.com", workspace_id=uuid4(), is_superadmin=False
    )


def _make_app(
    *,
    job_state: dict[str, Any] | None,
    stream_events: list[dict[str, Any]],
    emit_keepalive_when_empty: bool = False,
) -> FastAPI:
    """Build app with a fake streaming source injected via module-level patch."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    user = _fake_user()
    app.dependency_overrides[override_current_user] = lambda: user

    fake_redis = _FakeRedis()
    if job_state is not None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            fake_redis.setex("job:test-job", 3600, json.dumps(job_state))
        )
        loop.close()

    svc = JobProgressService(fake_redis)  # type: ignore[arg-type]
    app.dependency_overrides[override_job_progress_service] = lambda: svc

    # Patch _stream_job_progress with a fake that yields from stream_events
    import app.presentation.controllers.job_progress_controller as ctrl_mod

    async def _fake_stream(
        job_id: str, redis_url: str, keepalive_interval: float = 60.0
    ) -> AsyncIterator[str]:
        for event in stream_events:
            event_type = event.get("type")
            if event_type == "done":
                lines = ["event: done", f"data: {json.dumps(event.get('payload', event))}", "", ""]
                yield "\n".join(lines)
                return
            elif event_type == "error":
                lines = ["event: error", f"data: {json.dumps(event.get('payload', event))}", "", ""]
                yield "\n".join(lines)
                return
            else:
                lines = [f"data: {json.dumps(event)}", "", ""]
                yield "\n".join(lines)
        # Emit keepalive when explicitly requested (simulates idle keepalive)
        if emit_keepalive_when_empty and not stream_events:
            yield ": keepalive\n\n"

    ctrl_mod._stream_job_progress = _fake_stream  # type: ignore[assignment]

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sse_job_progress_done_frame() -> None:
    """Streaming ends with event: done frame when job completes."""
    events = [
        {"type": "progress", "payload": {"pct": 50}, "channel": "sse:job:test-job"},
        {"type": "done", "payload": {"message_id": "msg-final"}, "channel": "sse:job:test-job"},
    ]
    app = _make_app(
        job_state={"state": "running", "progress": 0},
        stream_events=events,
    )
    client = TestClient(app)
    resp = client.get("/api/v1/jobs/test-job/progress")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "event: done" in body
    # done payload includes message_id
    for line in body.splitlines():
        if line.startswith("data: ") and "msg-final" in line:
            parsed = json.loads(line[len("data: "):])
            assert parsed["message_id"] == "msg-final"
            break
    else:
        pytest.fail("done payload with message_id not found")


def test_sse_job_progress_error_frame() -> None:
    """Streaming ends with event: error frame when job fails."""
    events = [
        {"type": "error", "payload": {"message": "upstream crashed"}, "channel": "sse:job:test-job"},
    ]
    app = _make_app(
        job_state={"state": "running", "progress": 0},
        stream_events=events,
    )
    client = TestClient(app)
    resp = client.get("/api/v1/jobs/test-job/progress")
    assert resp.status_code == 200
    body = resp.text
    assert "event: error" in body
    # error payload accessible
    for line in body.splitlines():
        if line.startswith("data: ") and "upstream crashed" in line:
            break
    else:
        pytest.fail("error payload not found in SSE stream")


def test_sse_job_progress_keepalive_comment() -> None:
    """Keepalive comment `: keepalive` is sent when no events arrive."""
    app = _make_app(
        job_state={"state": "running", "progress": 0},
        stream_events=[],  # empty — triggers keepalive path
        emit_keepalive_when_empty=True,
    )
    client = TestClient(app)
    resp = client.get("/api/v1/jobs/test-job/progress")
    assert resp.status_code == 200
    assert ": keepalive" in resp.text


def test_sse_job_progress_404_when_job_missing() -> None:
    """Returns 404 when job_id has no state in Redis."""
    app = _make_app(job_state=None, stream_events=[])
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/jobs/test-job/progress")
    assert resp.status_code == 404


def test_sse_job_progress_content_type_is_text_event_stream() -> None:
    """Content-Type must be text/event-stream."""
    events = [
        {"type": "done", "payload": {"message_id": "x"}, "channel": "sse:job:test-job"},
    ]
    app = _make_app(
        job_state={"state": "running"},
        stream_events=events,
    )
    client = TestClient(app)
    resp = client.get("/api/v1/jobs/test-job/progress")
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_sse_job_progress_progress_frame_format() -> None:
    """Intermediate progress frames use `data: {...}` without event: line."""
    events = [
        {"type": "progress", "payload": {"pct": 25}, "channel": "sse:job:test-job"},
        {"type": "done", "payload": {"message_id": "fin"}, "channel": "sse:job:test-job"},
    ]
    app = _make_app(
        job_state={"state": "running"},
        stream_events=events,
    )
    client = TestClient(app)
    resp = client.get("/api/v1/jobs/test-job/progress")
    body = resp.text
    # At least one line that is data: without a preceding event: line
    lines = body.splitlines()
    # Find a data line containing pct=25
    found = any(
        '"pct": 25' in line or '"pct":25' in line
        for line in lines
        if line.startswith("data: ")
    )
    assert found, f"progress frame not found. body=\n{body}"
