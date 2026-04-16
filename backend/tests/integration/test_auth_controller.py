"""EP-00 auth controller integration tests — real FastAPI app + Postgres.

Google OAuth adapter is overridden with an in-memory fake; everything else (JWT,
repos, audit, sessions, state storage) runs against the real implementations.
"""

from __future__ import annotations

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


@pytest_asyncio.fixture
async def app(migrated_database):
    # asyncpg engines are bound to the event loop that created them. Reset the global
    # engine so each test gets one bound to its own pytest-asyncio loop.
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    # Wipe state from any previous test in the session.
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


async def _seed_user_with_workspace(
    migrated_database,
    *,
    sub: str,
    email: str,
    slug: str,
) -> tuple[User, Workspace]:
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
        ws.slug = slug  # pin slug for assertion
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()
    await eng.dispose()
    return user, ws


# ---------------------------------------------------------------------------
# GET /api/v1/auth/google — initiate OAuth
# ---------------------------------------------------------------------------


async def test_initiate_oauth_redirects_to_google(http) -> None:
    resp = await http.get("/api/v1/auth/google")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "accounts.google.com" in location
    assert "code_challenge_method=S256" in location
    assert "state=" in location


# ---------------------------------------------------------------------------
# GET /api/v1/auth/google/callback
# ---------------------------------------------------------------------------


async def test_callback_happy_path_sets_cookies_and_redirects(http, migrated_database) -> None:
    await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )

    # Obtain a valid state via /auth/google
    init = await http.get("/api/v1/auth/google")
    assert init.status_code == 302
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]

    resp = await http.get(
        f"/api/v1/auth/google/callback?code=dummy-code&state={state}"
    )

    assert resp.status_code == 302
    assert "/workspace/tuio" in resp.headers["location"]
    set_cookies = resp.headers.get_list("set-cookie")
    assert any(c.startswith("access_token=") for c in set_cookies)
    assert any(c.startswith("refresh_token=") for c in set_cookies)


async def test_callback_cancelled_redirects_to_login_cancelled(http) -> None:
    resp = await http.get("/api/v1/auth/google/callback?error=access_denied")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?error=cancelled"


async def test_callback_invalid_state_redirects(http) -> None:
    resp = await http.get("/api/v1/auth/google/callback?code=c&state=nonexistent")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?error=invalid_state"


async def test_callback_missing_state_redirects_invalid_state(http) -> None:
    resp = await http.get("/api/v1/auth/google/callback?code=some-code")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?error=invalid_state"


async def test_callback_missing_code_redirects_oauth_failed(http) -> None:
    # state present but no code
    init = await http.get("/api/v1/auth/google")
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    resp = await http.get(f"/api/v1/auth/google/callback?state={state}")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?error=oauth_failed"


async def test_callback_no_workspace_redirects(http, migrated_database) -> None:
    # User exists but NO workspace membership
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    eng = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        await users.upsert(
            User.from_google_claims(
                sub="sub-alice", email="alice@tuio.com", name="A", picture=None
            )
        )
        await session.commit()
    await eng.dispose()

    init = await http.get("/api/v1/auth/google")
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    resp = await http.get(f"/api/v1/auth/google/callback?code=c&state={state}")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?error=no_workspace"


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


async def test_me_unauthenticated_returns_401(http) -> None:
    resp = await http.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"


async def test_me_authenticated_returns_user_and_workspace(http, migrated_database) -> None:
    await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )

    # Log in via the callback flow to get cookies.
    init = await http.get("/api/v1/auth/google")
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    callback = await http.get(f"/api/v1/auth/google/callback?code=c&state={state}")
    access = next(
        (
            c.split("=", 1)[1].split(";", 1)[0]
            for c in callback.headers.get_list("set-cookie")
            if c.startswith("access_token=")
        ),
        None,
    )
    assert access, "access_token cookie must be set by callback"

    resp = await http.get(
        "/api/v1/auth/me", cookies={"access_token": access}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["email"] == "alice@tuio.com"
    assert body["full_name"] == "Alice"  # callback upserts with Google claims
    assert body["workspace_slug"] == "tuio"
    assert body["is_superadmin"] is False


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------


async def test_logout_clears_cookies_returns_204(http, migrated_database) -> None:
    await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )
    init = await http.get("/api/v1/auth/google")
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    callback = await http.get(f"/api/v1/auth/google/callback?code=c&state={state}")
    cookies = {
        c.split("=", 1)[0]: c.split("=", 1)[1].split(";", 1)[0]
        for c in callback.headers.get_list("set-cookie")
    }

    resp = await http.post("/api/v1/auth/logout", cookies=cookies)
    assert resp.status_code == 204
    # Cookies cleared (Max-Age=0 or empty value in deletion)
    clears = resp.headers.get_list("set-cookie")
    assert any("access_token=" in c for c in clears)
    assert any("refresh_token=" in c for c in clears)


async def test_logout_without_cookies_still_204(http) -> None:
    resp = await http.post("/api/v1/auth/logout")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


async def test_refresh_with_valid_cookie_rotates_access_token(http, migrated_database) -> None:
    _, ws = await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="tuio"
    )
    init = await http.get("/api/v1/auth/google")
    from urllib.parse import parse_qs, urlparse

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
    assert refresh

    resp = await http.post(
        f"/api/v1/auth/refresh?workspace_slug={ws.slug}",
        cookies={"refresh_token": refresh},
    )
    assert resp.status_code == 200
    assert "access_token_expires_at" in resp.json()["data"]


async def test_refresh_without_cookie_returns_401(http) -> None:
    resp = await http.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"


async def test_refresh_with_unknown_token_returns_401(http) -> None:
    resp = await http.post(
        "/api/v1/auth/refresh", cookies={"refresh_token": "never-issued"}
    )
    assert resp.status_code == 401


async def test_refresh_idor_wrong_workspace_returns_401(http, migrated_database) -> None:
    """Session minted for W1; refresh request asks for W2 slug → must be 401."""
    # Seed user with W1
    await _seed_user_with_workspace(
        migrated_database, sub="sub-alice", email="alice@tuio.com", slug="w1"
    )
    # Seed a second workspace W2 with a different user (alice has no membership in it)
    await _seed_user_with_workspace(
        migrated_database, sub="sub-bob", email="bob@tuio.com", slug="w2"
    )

    # Log in as alice (gets session for W1)
    init = await http.get("/api/v1/auth/google")
    from urllib.parse import parse_qs, urlparse

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
    assert refresh, "refresh cookie must be set"

    # Ask refresh for W2 — alice is NOT a member → expect 401
    resp = await http.post(
        "/api/v1/auth/refresh?workspace_slug=w2",
        cookies={"refresh_token": refresh},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NO_WORKSPACE_ACCESS"
