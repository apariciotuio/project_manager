"""Unit tests for BodySizeLimitMiddleware — RED phase."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.presentation.middleware.body_size_limit import BodySizeLimitMiddleware

_1_KiB = 1024
_1_MiB = 1024 * 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(
    max_body_bytes: int = _1_MiB,
    large_body_prefixes: list[str] | None = None,
    large_body_limit: int = 10 * _1_MiB,
) -> Starlette:
    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/upload", handler, methods=["POST"]),
            Route("/api/items", handler, methods=["POST"]),
        ]
    )
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_bytes=max_body_bytes,
        large_body_prefixes=large_body_prefixes or ["/upload"],
        large_body_limit=large_body_limit,
    )
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_request_within_limit_passes_through() -> None:
    """Body smaller than the limit is accepted with 200."""
    app = _build_app(max_body_bytes=_1_MiB)
    with TestClient(app) as client:
        resp = client.post(
            "/api/items",
            content=b"x" * (_1_KiB),
            headers={"content-length": str(_1_KiB)},
        )
    assert resp.status_code == 200


def test_request_exceeding_limit_returns_413() -> None:
    """Body with Content-Length > max_body_bytes returns 413."""
    app = _build_app(max_body_bytes=_1_KiB)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/items",
            content=b"x" * (_1_KiB + 1),
            headers={"content-length": str(_1_KiB + 1)},
        )
    assert resp.status_code == 413


def test_413_response_has_error_body() -> None:
    """413 response includes an error body with a meaningful code."""
    app = _build_app(max_body_bytes=_1_KiB)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/items",
            content=b"x" * (_1_KiB + 1),
            headers={"content-length": str(_1_KiB + 1)},
        )
    assert resp.status_code == 413
    body = resp.json()
    assert body.get("error", {}).get("code") == "BODY_TOO_LARGE"


def test_attachment_path_uses_large_limit() -> None:
    """Paths in large_body_prefixes get the larger limit instead of default."""
    app = _build_app(max_body_bytes=_1_KiB, large_body_prefixes=["/upload"], large_body_limit=5 * _1_MiB)
    with TestClient(app, raise_server_exceptions=False) as client:
        # 2 MiB — exceeds default 1 KiB but within 5 MiB large limit
        size = 2 * _1_MiB
        resp = client.post(
            "/upload",
            content=b"x" * size,
            headers={"content-length": str(size)},
        )
    # Should pass through (the handler says 200)
    assert resp.status_code == 200


def test_attachment_path_still_enforces_large_limit() -> None:
    """Attachment paths reject bodies exceeding the large limit."""
    app = _build_app(max_body_bytes=_1_KiB, large_body_prefixes=["/upload"], large_body_limit=2 * _1_MiB)
    with TestClient(app, raise_server_exceptions=False) as client:
        size = 3 * _1_MiB
        resp = client.post(
            "/upload",
            content=b"x" * size,
            headers={"content-length": str(size)},
        )
    assert resp.status_code == 413


def test_no_content_length_header_passes_through() -> None:
    """Request without Content-Length header is not rejected at middleware level."""
    app = _build_app(max_body_bytes=_1_KiB)
    with TestClient(app) as client:
        # TestClient may or may not set content-length; ensure it doesn't 413
        resp = client.post("/api/items", content=b"small")
    assert resp.status_code == 200


def test_get_request_no_body_passes() -> None:
    """GET requests (no body) are never rejected."""
    async def get_handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    from starlette.applications import Starlette
    from starlette.routing import Route

    app = Starlette(routes=[Route("/items", get_handler, methods=["GET"])])
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=_1_KiB)
    with TestClient(app) as client:
        resp = client.get("/items")
    assert resp.status_code == 200
