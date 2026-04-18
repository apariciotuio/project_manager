"""Unit tests for CSRFMiddleware — RED phase.

Double-submit cookie pattern:
- Safe methods (GET, HEAD, OPTIONS) bypass CSRF check.
- State-changing methods (POST, PUT, PATCH, DELETE) require:
    cookie `csrf_token` == header `X-CSRF-Token` (constant-time compare).
"""

from __future__ import annotations

import secrets

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.presentation.middleware.csrf import CSRF_COOKIE, CSRF_HEADER, CSRFMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(exempt_paths: set[str] | None = None) -> Starlette:
    async def handler(_: Request) -> Response:
        return PlainTextResponse("ok")

    routes = [
        Route(
            "/resource",
            handler,
            methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
        ),
        Route(
            "/api/v1/auth/refresh",
            handler,
            methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
        ),
        Route(
            "/api/v1/auth/google/callback",
            handler,
            methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
        ),
        Route(
            "/api/v1/csp-report",
            handler,
            methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
        ),
    ]
    app = Starlette(routes=routes)
    if exempt_paths is None:
        app.add_middleware(CSRFMiddleware)
    else:
        app.add_middleware(CSRFMiddleware, exempt_paths=exempt_paths)
    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_build_app(), raise_server_exceptions=True)


@pytest.fixture()
def token() -> str:
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Safe methods — never checked
# ---------------------------------------------------------------------------


def test_get_no_csrf_passes(client: TestClient) -> None:
    """GET without any CSRF cookie/header must pass through."""
    resp = client.get("/resource")
    assert resp.status_code == 200


def test_head_no_csrf_passes(client: TestClient) -> None:
    resp = client.head("/resource")
    assert resp.status_code == 200


def test_options_no_csrf_passes(client: TestClient) -> None:
    resp = client.options("/resource")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST — missing token
# ---------------------------------------------------------------------------


def test_post_missing_header_returns_403(client: TestClient, token: str) -> None:
    """POST with csrf_token cookie but no header → 403."""
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.post("/resource")
    assert resp.status_code == 403


def test_post_missing_cookie_returns_403(client: TestClient, token: str) -> None:
    """POST with header but no cookie → 403."""
    resp = client.post("/resource", headers={CSRF_HEADER: token})
    assert resp.status_code == 403


def test_post_both_missing_returns_403(client: TestClient) -> None:
    """POST with neither cookie nor header → 403."""
    resp = client.post("/resource")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST — mismatched token
# ---------------------------------------------------------------------------


def test_post_mismatched_token_returns_403(client: TestClient, token: str) -> None:
    """POST where cookie != header → 403."""
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.post("/resource", headers={CSRF_HEADER: "different-" + token})
    assert resp.status_code == 403


def test_post_empty_header_returns_403(client: TestClient, token: str) -> None:
    """POST with empty string header → 403."""
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.post("/resource", headers={CSRF_HEADER: ""})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST — matching token (happy path)
# ---------------------------------------------------------------------------


def test_post_matching_token_passes(client: TestClient, token: str) -> None:
    """POST where cookie == header → 200 passthrough."""
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.post("/resource", headers={CSRF_HEADER: token})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Other state-changing methods
# ---------------------------------------------------------------------------


def test_put_matching_token_passes(client: TestClient, token: str) -> None:
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.put("/resource", headers={CSRF_HEADER: token})
    assert resp.status_code == 200


def test_put_missing_token_returns_403(client: TestClient, token: str) -> None:
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.put("/resource")
    assert resp.status_code == 403


def test_patch_matching_token_passes(client: TestClient, token: str) -> None:
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.patch("/resource", headers={CSRF_HEADER: token})
    assert resp.status_code == 200


def test_patch_missing_token_returns_403(client: TestClient, token: str) -> None:
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.patch("/resource")
    assert resp.status_code == 403


def test_delete_matching_token_passes(client: TestClient, token: str) -> None:
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.delete("/resource", headers={CSRF_HEADER: token})
    assert resp.status_code == 200


def test_delete_missing_token_returns_403(client: TestClient, token: str) -> None:
    client.cookies.set(CSRF_COOKIE, token)
    resp = client.delete("/resource")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Error response shape
# ---------------------------------------------------------------------------


def test_403_response_body(client: TestClient) -> None:
    """403 response must include a structured error body."""
    resp = client.post("/resource")
    assert resp.status_code == 403
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "CSRF_TOKEN_INVALID"


# ---------------------------------------------------------------------------
# Exempt paths — bootstrap endpoints that don't have CSRF cookie yet
# ---------------------------------------------------------------------------


def test_exempt_path_post_without_csrf_passes() -> None:
    """POST to exempt path without CSRF header/cookie must pass through."""
    app = _build_app(
        exempt_paths={"/api/v1/auth/refresh", "/api/v1/auth/google/callback", "/api/v1/csp-report"}
    )
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200


def test_exempt_path_google_callback_post_without_csrf_passes() -> None:
    """POST to /api/v1/auth/google/callback exempt path without CSRF → 200."""
    app = _build_app(
        exempt_paths={"/api/v1/auth/refresh", "/api/v1/auth/google/callback", "/api/v1/csp-report"}
    )
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.post("/api/v1/auth/google/callback")
    assert resp.status_code == 200


def test_exempt_path_csp_report_post_without_csrf_passes() -> None:
    """POST to /api/v1/csp-report exempt path without CSRF → 200."""
    app = _build_app(
        exempt_paths={"/api/v1/auth/refresh", "/api/v1/auth/google/callback", "/api/v1/csp-report"}
    )
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.post("/api/v1/csp-report")
    assert resp.status_code == 200


def test_non_exempt_path_still_requires_csrf() -> None:
    """POST to non-exempt path without CSRF must still be 403."""
    app = _build_app(
        exempt_paths={"/api/v1/auth/refresh", "/api/v1/auth/google/callback", "/api/v1/csp-report"}
    )
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.post("/resource")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Server-to-server webhooks — HMAC-authenticated, no browser CSRF cookie
# ---------------------------------------------------------------------------


def test_dundun_webhook_exempted() -> None:
    """CSRFMiddleware must exempt /api/v1/dundun/callback."""
    from app.presentation.middleware.csrf import CSRFMiddleware

    middleware = CSRFMiddleware(
        app=lambda r: PlainTextResponse("ok"),
        exempt_paths={
            "/api/v1/auth/refresh",
            "/api/v1/auth/google/callback",
            "/api/v1/csp-report",
            "/api/v1/dundun/callback",
            "/api/v1/puppet/ingest-callback",
        },
    )
    assert middleware._is_exempt("/api/v1/dundun/callback")


def test_puppet_webhook_exempted() -> None:
    """CSRFMiddleware must exempt /api/v1/puppet/ingest-callback."""
    from app.presentation.middleware.csrf import CSRFMiddleware

    middleware = CSRFMiddleware(
        app=lambda r: PlainTextResponse("ok"),
        exempt_paths={
            "/api/v1/auth/refresh",
            "/api/v1/auth/google/callback",
            "/api/v1/csp-report",
            "/api/v1/dundun/callback",
            "/api/v1/puppet/ingest-callback",
        },
    )
    assert middleware._is_exempt("/api/v1/puppet/ingest-callback")


# ---------------------------------------------------------------------------
# SF-2: /api/v1/auth/logout must be exempt (SF-2)
# ---------------------------------------------------------------------------


def test_logout_is_exempt_via_is_exempt() -> None:
    """/api/v1/auth/logout must be in the default exempt set or _is_exempt returns True."""
    from app.presentation.middleware.csrf import CSRFMiddleware

    middleware = CSRFMiddleware(
        app=lambda r: PlainTextResponse("ok"),
        exempt_paths={
            "/api/v1/auth/refresh",
            "/api/v1/auth/google/callback",
            "/api/v1/auth/logout",
            "/api/v1/csp-report",
        },
    )
    assert middleware._is_exempt("/api/v1/auth/logout")


def test_logout_post_without_csrf_passes() -> None:
    """POST to /api/v1/auth/logout without X-CSRF-Token must pass through."""
    from starlette.routing import Route

    async def handler(_: Request) -> Response:
        return PlainTextResponse("ok")

    routes = [
        Route(
            "/api/v1/auth/logout",
            handler,
            methods=["POST"],
        ),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(
        CSRFMiddleware,
        exempt_paths={
            "/api/v1/auth/refresh",
            "/api/v1/auth/google/callback",
            "/api/v1/auth/logout",
            "/api/v1/csp-report",
        },
    )
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
