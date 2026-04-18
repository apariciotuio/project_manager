"""Unit tests for RequestLoggingMiddleware — RED phase."""

from __future__ import annotations

import logging

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.presentation.middleware.request_logging import RequestLoggingMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(status: int = 200) -> Starlette:
    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok", status_code=status)

    app = Starlette(routes=[Route("/test", handler), Route("/test-5xx", handler)])
    app.add_middleware(RequestLoggingMiddleware)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_log_line_emitted_per_request(caplog: pytest.LogCaptureFixture) -> None:
    """A single structured log line is emitted for every request."""
    app = _build_app(200)
    with caplog.at_level(logging.INFO, logger="app.presentation.middleware.request_logging"):
        with TestClient(app) as client:
            client.get("/test")

    assert len(caplog.records) == 1


def test_log_contains_required_fields(caplog: pytest.LogCaptureFixture) -> None:
    """Log record contains method, path, status_code, duration_ms, correlation_id."""
    app = _build_app(200)
    with caplog.at_level(logging.INFO, logger="app.presentation.middleware.request_logging"):
        with TestClient(app, headers={"X-Correlation-Id": "test-cid-123"}) as client:
            client.get("/test")

    record = caplog.records[0]
    assert record.method == "GET"  # type: ignore[attr-defined]
    assert record.path == "/test"  # type: ignore[attr-defined]
    assert record.status_code == 200  # type: ignore[attr-defined]
    assert isinstance(record.duration_ms, float)  # type: ignore[attr-defined]
    assert record.duration_ms >= 0  # type: ignore[attr-defined]


def test_4xx_logged_at_info_level(caplog: pytest.LogCaptureFixture) -> None:
    """4xx responses logged at INFO level (not warning/error)."""
    app = _build_app(404)
    with caplog.at_level(logging.DEBUG, logger="app.presentation.middleware.request_logging"):
        with TestClient(app, raise_server_exceptions=False) as client:
            client.get("/test")

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.INFO


def test_5xx_logged_at_error_level(caplog: pytest.LogCaptureFixture) -> None:
    """5xx responses logged at ERROR level."""
    app = _build_app(500)
    with caplog.at_level(logging.DEBUG, logger="app.presentation.middleware.request_logging"):
        with TestClient(app, raise_server_exceptions=False) as client:
            client.get("/test")

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR


def test_authorization_header_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Authorization header must never appear in log output."""
    app = _build_app(200)
    with caplog.at_level(logging.DEBUG, logger="app.presentation.middleware.request_logging"):
        with TestClient(app) as client:
            client.get("/test", headers={"Authorization": "Bearer super-secret-token"})

    for record in caplog.records:
        assert "super-secret-token" not in record.getMessage()
        assert "Authorization" not in record.getMessage()


def test_request_body_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Request bodies are never logged (PII / secret risk)."""

    async def post_handler(request: Request) -> Response:
        await request.body()
        return PlainTextResponse("ok", status_code=200)

    app = Starlette(routes=[Route("/post", post_handler, methods=["POST"])])
    app.add_middleware(RequestLoggingMiddleware)

    with caplog.at_level(logging.DEBUG, logger="app.presentation.middleware.request_logging"):
        with TestClient(app) as client:
            client.post("/post", json={"password": "s3cr3t"})

    for record in caplog.records:
        assert "s3cr3t" not in record.getMessage()
        assert "password" not in record.getMessage()


def test_correlation_id_attached_from_contextvar(caplog: pytest.LogCaptureFixture) -> None:
    """If CorrelationIDMiddleware ran first the correlation_id flows into the log line."""
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.config.logging import correlation_id_var

    class _SetCidMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):  # type: ignore[override]
            token = correlation_id_var.set("fixed-cid")
            try:
                return await call_next(request)
            finally:
                correlation_id_var.reset(token)

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(_SetCidMiddleware)

    with caplog.at_level(logging.INFO, logger="app.presentation.middleware.request_logging"):
        with TestClient(app) as client:
            client.get("/test")

    record = caplog.records[0]
    assert getattr(record, "correlation_id", None) == "fixed-cid"
