"""Unit tests for SecurityHeadersMiddleware (CSP + security headers) — RED phase."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.presentation.middleware.security_headers import SecurityHeadersMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(csp_overrides: dict[str, str] | None = None) -> Starlette:
    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    app.add_middleware(SecurityHeadersMiddleware, csp_overrides=csp_overrides or {})
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_x_frame_options_deny() -> None:
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/test")
    assert resp.headers.get("x-frame-options") == "DENY"


def test_x_content_type_options_nosniff() -> None:
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/test")
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_referrer_policy_strict_origin() -> None:
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/test")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_csp_default_src_self() -> None:
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/test")
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp


def test_csp_no_unsafe_inline_scripts() -> None:
    """Default CSP must not allow unsafe-inline for scripts."""
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/test")
    csp = resp.headers.get("content-security-policy", "")
    # unsafe-inline must NOT appear in script-src or default-src
    parts = [p.strip() for p in csp.split(";")]
    for part in parts:
        if part.startswith("script-src") or part.startswith("default-src"):
            assert "'unsafe-inline'" not in part, f"unsafe-inline found in: {part}"


def test_hsts_set_on_https_request() -> None:
    """HSTS is only added when X-Forwarded-Proto is https."""
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/test", headers={"x-forwarded-proto": "https"})
    hsts = resp.headers.get("strict-transport-security", "")
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


def test_hsts_not_set_on_http_request() -> None:
    """HSTS must NOT be added on plain HTTP requests."""
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/test")
    assert "strict-transport-security" not in resp.headers


def test_csp_overrides_applied() -> None:
    """Caller-supplied directives override defaults."""
    overrides = {"img-src": "'self' data: https://cdn.example.com"}
    app = _build_app(csp_overrides=overrides)
    with TestClient(app) as client:
        resp = client.get("/test")
    csp = resp.headers.get("content-security-policy", "")
    assert "https://cdn.example.com" in csp
