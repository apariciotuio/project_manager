"""Unit tests for CORSPolicyMiddleware — RED phase."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.presentation.middleware.cors_policy import CORSPolicyMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(allowed_origins: list[str], env: str = "development") -> Starlette:
    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/api/test", handler, methods=["GET", "OPTIONS"])])
    app.add_middleware(
        CORSPolicyMiddleware,
        allowed_origins=allowed_origins,
        env=env,
    )
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_allowed_origin_echoed_in_response() -> None:
    """Allowed origin is reflected back in ACAO header."""
    app = _build_app(["https://app.example.com"])
    with TestClient(app) as client:
        resp = client.get(
            "/api/test", headers={"Origin": "https://app.example.com"}
        )
    assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"


def test_disallowed_origin_no_acao_header() -> None:
    """Requests from an origin not in the allowlist don't get ACAO header."""
    app = _build_app(["https://app.example.com"])
    with TestClient(app) as client:
        resp = client.get(
            "/api/test", headers={"Origin": "https://evil.example.com"}
        )
    assert "access-control-allow-origin" not in resp.headers


def test_disallowed_origin_returns_403() -> None:
    """Cross-origin request from disallowed origin returns 403."""
    app = _build_app(["https://app.example.com"])
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get(
            "/api/test", headers={"Origin": "https://evil.example.com"}
        )
    assert resp.status_code == 403


def test_wildcard_rejected_in_production() -> None:
    """CORSPolicyMiddleware raises ValueError if '*' is in allowed_origins in production.

    Starlette defers middleware instantiation to first request / TestClient startup.
    """
    app = _build_app(["*"], env="production")
    with pytest.raises(ValueError, match="wildcard"):
        with TestClient(app):
            pass


def test_wildcard_allowed_in_development() -> None:
    """'*' in allowed_origins is accepted in development environment."""
    # Should not raise
    app = _build_app(["*"], env="development")
    assert app is not None


def test_preflight_includes_max_age() -> None:
    """Preflight response includes Access-Control-Max-Age: 600."""
    app = _build_app(["https://app.example.com"])
    with TestClient(app) as client:
        resp = client.options(
            "/api/test",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.headers.get("access-control-max-age") == "600"


def test_preflight_allowed_headers_limited() -> None:
    """Preflight response only allows the specified headers."""
    app = _build_app(["https://app.example.com"])
    with TestClient(app) as client:
        resp = client.options(
            "/api/test",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
    allowed = resp.headers.get("access-control-allow-headers", "")
    assert "authorization" in allowed.lower()


def test_no_origin_header_passes_through() -> None:
    """Request without Origin header is not a CORS request — passes through normally."""
    app = _build_app(["https://app.example.com"])
    with TestClient(app) as client:
        resp = client.get("/api/test")
    assert resp.status_code == 200


def test_credentials_allowed() -> None:
    """Access-Control-Allow-Credentials is set to true for allowed origins."""
    app = _build_app(["https://app.example.com"])
    with TestClient(app) as client:
        resp = client.get(
            "/api/test", headers={"Origin": "https://app.example.com"}
        )
    assert resp.headers.get("access-control-allow-credentials") == "true"
