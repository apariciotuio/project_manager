"""CSRF cookie emission tests — EP-12.

Verifies that:
1. Successful OAuth callback sets a non-empty csrf_token cookie (httponly=false, samesite=strict).
2. Failed callback (cancelled / invalid state) does NOT set the csrf_token cookie.
3. Successful token refresh rotates the csrf_token cookie.
4. Failed refresh does NOT set the csrf_token cookie.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.google_oauth_adapter import GoogleClaims
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import (
    WorkspaceRepositoryImpl,
)
from app.main import create_app
from app.presentation.dependencies import get_google_oauth_adapter
from tests.fakes.fake_google_oauth import FakeGoogleOAuthAdapter

CSRF_COOKIE = "csrf_token"


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE workspace_memberships, sessions, oauth_states, "
                "workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    fastapi_app = create_app()
    fake_google = FakeGoogleOAuthAdapter(
        claims=GoogleClaims(
            sub="sub-alice",
            email="alice@tuio.com",
            name="Alice",
            picture="https://x/p.png",
        )
    )
    fastapi_app.dependency_overrides[get_google_oauth_adapter] = lambda: fake_google
    fastapi_app.state.fake_google = fake_google
    yield fastapi_app
    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def http(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        yield client


async def _seed_user_with_workspace(migrated_database, *, sub: str, email: str, slug: str):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    eng = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(sub=sub, email=email, name="A", picture=None)
        await users.upsert(user)
        ws = Workspace.create_from_email(email=email, created_by=user.id)
        ws.slug = slug
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()
    await eng.dispose()
    return user, ws


def _extract_csrf_cookies(headers) -> list[str]:
    """Return all Set-Cookie headers that start with csrf_token=."""
    return [c for c in headers.get_list("set-cookie") if c.startswith(f"{CSRF_COOKIE}=")]


def _parse_cookie_attrs(cookie_header: str) -> dict[str, str]:
    """Parse a single Set-Cookie header string into a dict of attr -> value."""
    parts = [p.strip() for p in cookie_header.split(";")]
    attrs: dict[str, str] = {}
    for i, part in enumerate(parts):
        if "=" in part:
            k, v = part.split("=", 1)
            attrs[k.strip().lower()] = v.strip()
        else:
            attrs[part.strip().lower()] = ""
    return attrs


# ---------------------------------------------------------------------------
# OAuth callback — successful login sets csrf_token
# ---------------------------------------------------------------------------


async def test_callback_sets_csrf_token_cookie_on_success(http, migrated_database) -> None:
    await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )
    init = await http.get("/api/v1/auth/google")
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]

    resp = await http.get(f"/api/v1/auth/google/callback?code=dummy-code&state={state}")

    assert resp.status_code == 302
    csrf_cookies = _extract_csrf_cookies(resp.headers)
    assert len(csrf_cookies) == 1, f"Expected exactly one csrf_token cookie, got: {csrf_cookies}"

    attrs = _parse_cookie_attrs(csrf_cookies[0])
    value = attrs.get(CSRF_COOKIE, "")
    assert value, "csrf_token cookie value must be non-empty"
    assert len(value) >= 32, "csrf_token value must have sufficient entropy"


async def test_callback_csrf_cookie_is_not_httponly(http, migrated_database) -> None:
    """JS must be able to read the CSRF token — HttpOnly must be absent."""
    await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )
    init = await http.get("/api/v1/auth/google")
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]

    resp = await http.get(f"/api/v1/auth/google/callback?code=dummy-code&state={state}")

    csrf_cookies = _extract_csrf_cookies(resp.headers)
    assert csrf_cookies
    raw = csrf_cookies[0].lower()
    assert "httponly" not in raw, "csrf_token cookie must NOT be HttpOnly"


async def test_callback_csrf_cookie_samesite_strict(http, migrated_database) -> None:
    await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )
    init = await http.get("/api/v1/auth/google")
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]

    resp = await http.get(f"/api/v1/auth/google/callback?code=dummy-code&state={state}")

    csrf_cookies = _extract_csrf_cookies(resp.headers)
    assert csrf_cookies
    attrs = _parse_cookie_attrs(csrf_cookies[0])
    assert attrs.get("samesite", "").lower() == "strict"


async def test_callback_does_not_set_csrf_on_cancelled(http) -> None:
    resp = await http.get("/api/v1/auth/google/callback?error=access_denied")
    assert resp.status_code == 302
    csrf_cookies = _extract_csrf_cookies(resp.headers)
    assert not csrf_cookies, "Failed login must not set csrf_token cookie"


async def test_callback_does_not_set_csrf_on_invalid_state(http) -> None:
    resp = await http.get("/api/v1/auth/google/callback?code=c&state=nonexistent")
    assert resp.status_code == 302
    csrf_cookies = _extract_csrf_cookies(resp.headers)
    assert not csrf_cookies, "Failed login must not set csrf_token cookie"


# ---------------------------------------------------------------------------
# Token refresh — rotates csrf_token
# ---------------------------------------------------------------------------


async def test_refresh_rotates_csrf_token_cookie(http, migrated_database) -> None:
    _, ws = await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )
    init = await http.get("/api/v1/auth/google")
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    callback = await http.get(f"/api/v1/auth/google/callback?code=c&state={state}")

    refresh = next(
        (
            c.split("=", 1)[1].split(";", 1)[0]
            for c in callback.headers.get_list("set-cookie")
            if c.startswith("refresh_token=")
        ),
        None,
    )
    original_csrf = next(
        (
            c.split("=", 1)[1].split(";", 1)[0]
            for c in callback.headers.get_list("set-cookie")
            if c.startswith(f"{CSRF_COOKIE}=")
        ),
        None,
    )
    assert refresh
    assert original_csrf

    # Must send the CSRF cookie + header — CSRFMiddleware guards all POST requests
    resp = await http.post(
        f"/api/v1/auth/refresh?workspace_slug={ws.slug}",
        cookies={"refresh_token": refresh, CSRF_COOKIE: original_csrf},
        headers={"X-CSRF-Token": original_csrf},
    )

    assert resp.status_code == 200
    csrf_cookies = _extract_csrf_cookies(resp.headers)
    assert len(csrf_cookies) == 1, "Refresh must emit a new csrf_token cookie"
    new_csrf = csrf_cookies[0].split("=", 1)[1].split(";", 1)[0]
    assert new_csrf, "Rotated csrf_token must be non-empty"
    # Tokens should differ (collision probability ~0 for 32-byte random)
    assert new_csrf != original_csrf, "Refresh must rotate the csrf_token"


async def test_refresh_does_not_set_csrf_on_failure(http) -> None:
    # Provide a valid CSRF pair so middleware passes, but an invalid refresh token
    # so the auth logic rejects with 401.
    dummy_csrf = "valid-csrf-token-for-middleware-test"
    resp = await http.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "never-issued", CSRF_COOKIE: dummy_csrf},
        headers={"X-CSRF-Token": dummy_csrf},
    )
    assert resp.status_code == 401
    csrf_cookies = _extract_csrf_cookies(resp.headers)
    assert not csrf_cookies, "Failed refresh must not set csrf_token cookie"
