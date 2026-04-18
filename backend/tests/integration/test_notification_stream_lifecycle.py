"""Integration tests for notification SSE stream lifecycle.

Covers two endpoints:
  POST /api/v1/notifications/stream-token   — issues short-lived JWT
  GET  /api/v1/notifications/stream         — SSE stream authenticated by that token

Lifecycle cases:
  stream-token:
    - 401 when unauthenticated
    - 401 when user has no workspace_id
    - 200 returns token + expires_in
    - Token is a valid JWT decodable by the same adapter

  stream (GET /notifications/stream):
    - 401 when token query param is missing
    - 401 when token is syntactically invalid (garbage string)
    - 401 when token has wrong purpose (not 'sse_notifications')
    - 200 + text/event-stream when token is valid (stream opens)
    - SseHandler receives frames from the fake pubsub and emits them
    - Stream closes cleanly after terminal 'done' frame
    - Stream closes cleanly after terminal 'error' frame

Architecture note: PgNotificationBus requires a live Postgres connection for
subscribe().  We override the stream endpoint's internal bus by monkey-patching
`stream_notifications` to inject a FakePubSub via dependency override on
get_jwt_adapter + module-level patch of PgNotificationBus.subscribe.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"
_CSRF_TOKEN = "test-csrf-stream-fixed"
_CSRF_HEADERS = {"X-CSRF-Token": _CSRF_TOKEN}
_CSRF_COOKIES = {"csrf_token": _CSRF_TOKEN}


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _make_access_token(*, workspace_id: str | None = None, is_superadmin: bool = False) -> str:
    adapter = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(uuid4()),
        "email": f"{uuid4().hex[:8]}@tuio.com",
        "is_superadmin": is_superadmin,
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
    }
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    return adapter.encode(payload)


def _make_stream_token(
    *,
    user_id: str | None = None,
    workspace_id: str | None = None,
    purpose: str = "sse_notifications",
    exp_offset: int = 300,
) -> str:
    """Build a stream token the same way the endpoint does."""
    adapter = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    uid = user_id or str(uuid4())
    wsid = workspace_id or str(uuid4())
    payload: dict[str, Any] = {
        "sub": uid,
        "workspace_id": wsid,
        "purpose": purpose,
        "exp": int(time.time()) + exp_offset,
    }
    return adapter.encode(payload)


# ---------------------------------------------------------------------------
# Fake pubsub
# ---------------------------------------------------------------------------


class FakePubSub:
    """Delivers a pre-loaded event list then exhausts."""

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
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(migrated_database):  # noqa: ARG001
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    from app.main import create_app
    from app.presentation.dependencies import get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = create_app()
    fake_cache = FakeCache()

    async def _override_cache():
        yield fake_cache

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    yield fastapi_app

    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def http(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/stream-token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_token_unauthenticated_returns_401(http: AsyncClient) -> None:
    """No access_token cookie → 401."""
    resp = await http.post(
        "/api/v1/notifications/stream-token",
        headers=_CSRF_HEADERS,
        cookies=_CSRF_COOKIES,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stream_token_user_without_workspace_returns_401(http: AsyncClient) -> None:
    """User with no workspace_id → 401 NO_WORKSPACE."""
    token = _make_access_token(workspace_id=None)
    resp = await http.post(
        "/api/v1/notifications/stream-token",
        headers=_CSRF_HEADERS,
        cookies={"access_token": token, **_CSRF_COOKIES},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "NO_WORKSPACE"


@pytest.mark.asyncio
async def test_stream_token_authenticated_returns_200_with_token(http: AsyncClient) -> None:
    """Valid access token + workspace → 200 with stream token and expires_in."""
    token = _make_access_token(workspace_id=str(uuid4()))
    resp = await http.post(
        "/api/v1/notifications/stream-token",
        headers=_CSRF_HEADERS,
        cookies={"access_token": token, **_CSRF_COOKIES},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body["data"]
    assert "expires_in" in body["data"]
    assert body["data"]["expires_in"] == 300


@pytest.mark.asyncio
async def test_stream_token_is_a_valid_decodable_jwt(http: AsyncClient) -> None:
    """The returned token can be decoded by the same JwtAdapter."""
    workspace_id = str(uuid4())
    access_token = _make_access_token(workspace_id=workspace_id)
    resp = await http.post(
        "/api/v1/notifications/stream-token",
        headers=_CSRF_HEADERS,
        cookies={"access_token": access_token, **_CSRF_COOKIES},
    )
    assert resp.status_code == 200

    stream_token = resp.json()["data"]["token"]
    adapter = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    claims = adapter.decode(stream_token)
    assert claims["purpose"] == "sse_notifications"
    assert claims["workspace_id"] == workspace_id


# ---------------------------------------------------------------------------
# GET /api/v1/notifications/stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_missing_token_param_returns_422_or_401(http: AsyncClient) -> None:
    """No ?token= query param → 422 (FastAPI required param) or 401."""
    resp = await http.get("/api/v1/notifications/stream")
    # FastAPI raises 422 for missing required query param before the endpoint runs
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_stream_garbage_token_returns_401(http: AsyncClient) -> None:
    """Syntactically invalid token → 401 INVALID_STREAM_TOKEN."""
    resp = await http.get(
        "/api/v1/notifications/stream",
        params={"token": "not.a.jwt.token"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "INVALID_STREAM_TOKEN"


@pytest.mark.asyncio
async def test_stream_expired_token_returns_401(http: AsyncClient) -> None:
    """Expired stream token → 401 INVALID_STREAM_TOKEN."""
    expired_token = _make_stream_token(exp_offset=-10)  # already expired
    resp = await http.get(
        "/api/v1/notifications/stream",
        params={"token": expired_token},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "INVALID_STREAM_TOKEN"


@pytest.mark.asyncio
async def test_stream_wrong_purpose_token_returns_401(http: AsyncClient) -> None:
    """Token with purpose != 'sse_notifications' → 401 INVALID_STREAM_TOKEN."""
    wrong_token = _make_stream_token(purpose="something_else")
    resp = await http.get(
        "/api/v1/notifications/stream",
        params={"token": wrong_token},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "INVALID_STREAM_TOKEN"


@pytest.mark.asyncio
async def test_stream_valid_token_returns_event_stream_content_type(
    app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid stream token → 200 text/event-stream response."""
    import app.infrastructure.sse.pg_notification_bus as bus_mod

    fake_pubsub = FakePubSub(
        [{"type": "done", "payload": {"message_id": "test-msg"}}]
    )

    original_init = bus_mod.PgNotificationBus.__init__

    def _patched_init(self, *, dsn=None, pool=None):  # noqa: ANN001
        self._dsn = dsn
        self._pool = pool

    async def _patched_subscribe(self, channel, max_messages=None, poll_interval=0.05):  # noqa: ANN001
        async for event in fake_pubsub.subscribe(channel, max_messages=max_messages):
            yield event

    monkeypatch.setattr(bus_mod.PgNotificationBus, "__init__", _patched_init)
    monkeypatch.setattr(bus_mod.PgNotificationBus, "subscribe", _patched_subscribe)

    token = _make_stream_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": f"10.0.{uuid4().int % 256}.{uuid4().int % 256}"},
    ) as client:
        resp = await client.get(
            "/api/v1/notifications/stream",
            params={"token": token},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_stream_valid_token_delivers_done_frame(
    app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid stream token + fake pubsub emitting done → done frame in body."""
    import app.infrastructure.sse.pg_notification_bus as bus_mod

    fake_pubsub = FakePubSub(
        [{"type": "done", "payload": {"message_id": "notif-final"}}]
    )

    def _patched_init(self, *, dsn=None, pool=None):  # noqa: ANN001
        self._dsn = dsn
        self._pool = pool

    async def _patched_subscribe(self, channel, max_messages=None, poll_interval=0.05):  # noqa: ANN001
        async for event in fake_pubsub.subscribe(channel):
            yield event

    monkeypatch.setattr(bus_mod.PgNotificationBus, "__init__", _patched_init)
    monkeypatch.setattr(bus_mod.PgNotificationBus, "subscribe", _patched_subscribe)

    token = _make_stream_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": f"10.0.{uuid4().int % 256}.{uuid4().int % 256}"},
    ) as client:
        resp = await client.get(
            "/api/v1/notifications/stream",
            params={"token": token},
        )

    body = resp.text
    assert "event: done" in body
    # Verify message_id is in the data line
    for line in body.splitlines():
        if line.startswith("data: ") and "notif-final" in line:
            parsed = json.loads(line[len("data: "):])
            assert parsed["message_id"] == "notif-final"
            break
    else:
        pytest.fail(f"done payload not found in SSE body:\n{body}")


@pytest.mark.asyncio
async def test_stream_valid_token_delivers_error_frame(
    app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid stream token + fake pubsub emitting error → error frame in body."""
    import app.infrastructure.sse.pg_notification_bus as bus_mod

    fake_pubsub = FakePubSub(
        [{"type": "error", "payload": {"message": "notification service failed"}}]
    )

    def _patched_init(self, *, dsn=None, pool=None):  # noqa: ANN001
        self._dsn = dsn
        self._pool = pool

    async def _patched_subscribe(self, channel, max_messages=None, poll_interval=0.05):  # noqa: ANN001
        async for event in fake_pubsub.subscribe(channel):
            yield event

    monkeypatch.setattr(bus_mod.PgNotificationBus, "__init__", _patched_init)
    monkeypatch.setattr(bus_mod.PgNotificationBus, "subscribe", _patched_subscribe)

    token = _make_stream_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": f"10.0.{uuid4().int % 256}.{uuid4().int % 256}"},
    ) as client:
        resp = await client.get(
            "/api/v1/notifications/stream",
            params={"token": token},
        )

    body = resp.text
    assert "event: error" in body
    for line in body.splitlines():
        if line.startswith("data: ") and "notification service failed" in line:
            break
    else:
        pytest.fail(f"error payload not found in SSE body:\n{body}")


@pytest.mark.asyncio
async def test_stream_done_frame_ends_stream_no_subsequent_frames(
    app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After done frame, generator stops — subsequent events are not emitted."""
    import app.infrastructure.sse.pg_notification_bus as bus_mod

    # done first, then a phantom progress that must NOT appear
    fake_pubsub = FakePubSub(
        [
            {"type": "done", "payload": {"message_id": "final"}},
            {"type": "progress", "payload": {"pct": 99}},  # must not appear
        ]
    )

    def _patched_init(self, *, dsn=None, pool=None):  # noqa: ANN001
        self._dsn = dsn
        self._pool = pool

    async def _patched_subscribe(self, channel, max_messages=None, poll_interval=0.05):  # noqa: ANN001
        async for event in fake_pubsub.subscribe(channel):
            yield event

    monkeypatch.setattr(bus_mod.PgNotificationBus, "__init__", _patched_init)
    monkeypatch.setattr(bus_mod.PgNotificationBus, "subscribe", _patched_subscribe)

    token = _make_stream_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": f"10.0.{uuid4().int % 256}.{uuid4().int % 256}"},
    ) as client:
        resp = await client.get(
            "/api/v1/notifications/stream",
            params={"token": token},
        )

    body = resp.text
    assert "event: done" in body
    data_lines = [l for l in body.splitlines() if l.startswith("data: ")]
    # Only the done payload — not the phantom progress frame
    assert len(data_lines) == 1, f"Expected 1 data line, got {len(data_lines)}:\n{body}"
