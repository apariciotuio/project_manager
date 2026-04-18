"""Unit tests for CorrelationIDMiddleware — RED phase."""

from __future__ import annotations

import uuid

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.config.logging import correlation_id_var
from app.presentation.middleware.correlation_id import (
    CORRELATION_ID_HEADER,
    CorrelationIDMiddleware,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app() -> Starlette:
    captured: list[str] = []

    async def handler(request: Request) -> Response:
        # Capture the ContextVar value mid-request so tests can assert on it.
        captured.append(correlation_id_var.get(""))
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    app.add_middleware(CorrelationIDMiddleware)
    app.state.captured = captured
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_generates_uuid_when_header_absent() -> None:
    """No X-Correlation-ID header → middleware generates a UUID v4."""
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/test")

    assert response.status_code == 200
    value = response.headers.get(CORRELATION_ID_HEADER)
    assert value is not None
    parsed = uuid.UUID(value)
    assert parsed.version == 4


def test_passes_through_valid_uuid_header() -> None:
    """Valid UUID in X-Correlation-ID is preserved in the response header."""
    valid_id = str(uuid.uuid4())
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/test", headers={CORRELATION_ID_HEADER: valid_id})

    assert response.headers.get(CORRELATION_ID_HEADER) == valid_id


def test_rejects_and_regenerates_invalid_uuid_header() -> None:
    """Non-UUID string in X-Correlation-ID is discarded; a fresh UUID v4 is generated."""
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/test", headers={CORRELATION_ID_HEADER: "not-a-uuid"})

    value = response.headers.get(CORRELATION_ID_HEADER)
    assert value is not None
    assert value != "not-a-uuid"
    parsed = uuid.UUID(value)
    assert parsed.version == 4


def test_response_always_contains_correlation_id_header() -> None:
    """X-Correlation-ID is present on every response regardless of request."""
    app = _build_app()
    with TestClient(app) as client:
        r1 = client.get("/test")
        r2 = client.get("/test", headers={CORRELATION_ID_HEADER: str(uuid.uuid4())})
        r3 = client.get("/test", headers={CORRELATION_ID_HEADER: "garbage"})

    for response in (r1, r2, r3):
        assert CORRELATION_ID_HEADER in response.headers


def test_contextvar_set_to_correlation_id_during_request() -> None:
    """The ContextVar holds the correlation_id value while the handler runs."""
    captured: list[str] = []

    async def handler(request: Request) -> Response:
        captured.append(correlation_id_var.get(""))
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    app.add_middleware(CorrelationIDMiddleware)

    valid_id = str(uuid.uuid4())
    with TestClient(app) as client:
        client.get("/test", headers={CORRELATION_ID_HEADER: valid_id})

    assert captured == [valid_id]


def test_contextvar_reset_after_request() -> None:
    """ContextVar is reset to default after the request completes (no leakage)."""
    correlation_id_var.set("")

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    app.add_middleware(CorrelationIDMiddleware)

    with TestClient(app) as client:
        client.get("/test")

    assert correlation_id_var.get("") == ""
