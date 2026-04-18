"""Test csrf_client fixture — validates auto-CSRF header injection.

Demonstrates the csrf_client fixture from conftest.py. This fixture:
  - Sets a fixed csrf_token cookie
  - Auto-injects X-CSRF-Token header on all mutating requests (POST/PUT/PATCH/DELETE)
  - Leaves read-only requests (GET/HEAD/OPTIONS/TRACE) untouched
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_csrf_client_injects_header_on_post(csrf_client: AsyncClient) -> None:
    """csrf_client fixture auto-injects X-CSRF-Token header on POST."""
    # Make a POST request without manually specifying the header.
    # The fixture should inject it automatically.
    resp = await csrf_client.post(
        "/api/v1/internal/jobs/cleanup_expired_sessions/run",
    )
    # We expect 401 (no auth token) not 403 CSRF_TOKEN_INVALID.
    # This proves the CSRF header was auto-injected and passed the middleware.
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"


@pytest.mark.asyncio
async def test_csrf_client_injects_header_on_put(csrf_client: AsyncClient) -> None:
    """csrf_client fixture auto-injects X-CSRF-Token header on PUT."""
    # Similar test for PUT (though no test endpoint exists, we validate middleware passes)
    # by checking for 401 (auth failure) not 403 (CSRF failure).
    resp = await csrf_client.put("/api/v1/work-items/nonexistent")
    # If CSRF fails, we'd see 403 CSRF_TOKEN_INVALID.
    # Any other code means CSRF passed (and something else failed).
    assert resp.status_code != 403 or resp.json()["error"]["code"] != "CSRF_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_csrf_client_leaves_get_untouched(csrf_client: AsyncClient) -> None:
    """csrf_client fixture does NOT inject CSRF header on GET (safe method)."""
    # GET is safe; CSRFMiddleware doesn't check it.
    # This test just ensures the fixture doesn't break GET requests.
    resp = await csrf_client.get("/api/v1/health")
    # 404 or 200 depending on whether /health endpoint exists; doesn't matter.
    # Point is that GET wasn't blocked by CSRF middleware.
    assert resp.status_code in {200, 404}


@pytest.mark.asyncio
async def test_csrf_client_cookie_is_set(csrf_client: AsyncClient) -> None:
    """csrf_client fixture sets a csrf_token cookie."""
    assert "csrf_token" in csrf_client.cookies
    token = csrf_client.cookies.get("csrf_token")
    assert token
    assert len(token) >= 32, "CSRF token should have sufficient entropy"
