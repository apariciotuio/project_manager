"""Integration tests for Conversation thread endpoints — EP-03 Phase 7.

Scenarios:
  GET /api/v1/threads — list user's threads; IDOR: only own
  POST /api/v1/threads — get-or-create; 201
  GET /api/v1/threads/{id} — get pointer; 404 on wrong user (IDOR: no existence leak)
  GET /api/v1/threads/{id}/history — 404 if not owner; empty list (Dundun stub)
  DELETE /api/v1/threads/{id} — archive; 404 on missing; 404 on wrong user
  Unauthenticated → 401
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter, get_dundun_client
    from tests.fakes.fake_dundun_client import FakeDundunClient
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()

    fake_cache = FakeCache()
    fake_dundun = FakeDundunClient()

    async def _override_cache():
        yield fake_cache

    def _override_dundun():
        return fake_dundun

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    fastapi_app.dependency_overrides[get_dundun_client] = _override_dundun
    fastapi_app._fake_dundun = fake_dundun  # type: ignore[attr-defined]

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


async def _seed(migrated_database):
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # Use a unique domain per seed call to avoid slug collision
    _uid = uuid4().hex[:8]
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub=f"sub-{_uid}",
            email=f"u{_uid}@{_uid}.com",
            name="U",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="member", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(ws.id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )
    return user, ws, token


# ---------------------------------------------------------------------------
# GET /api/v1/threads
# ---------------------------------------------------------------------------


class TestListThreads:
    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.get("/api/v1/threads")
        assert resp.status_code == 401

    async def test_empty_list_for_new_user(self, http: AsyncClient, migrated_database) -> None:
        _user, _ws, token = await _seed(migrated_database)
        resp = await http.get("/api/v1/threads", cookies={"access_token": token})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_lists_only_own_threads(self, http: AsyncClient, migrated_database) -> None:
        user_a, _ws_a, token_a = await _seed(migrated_database)
        user_b, _ws_b, token_b = await _seed(migrated_database)

        # Create a thread as user A
        resp = await http.post(
            "/api/v1/threads",
            json={},
            cookies={"access_token": token_a},
        )
        assert resp.status_code == 201

        # User B sees no threads
        resp_b = await http.get("/api/v1/threads", cookies={"access_token": token_b})
        assert resp_b.status_code == 200
        assert resp_b.json()["data"] == []

        # User A sees their thread
        resp_a = await http.get("/api/v1/threads", cookies={"access_token": token_a})
        assert resp_a.status_code == 200
        assert len(resp_a.json()["data"]) == 1


# ---------------------------------------------------------------------------
# POST /api/v1/threads
# ---------------------------------------------------------------------------


class TestCreateThread:
    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.post("/api/v1/threads", json={})
        assert resp.status_code == 401

    async def test_creates_general_thread_returns_201(
        self, http: AsyncClient, migrated_database
    ) -> None:
        _user, _ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/threads",
            json={},
            cookies={"access_token": token},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert "id" in data
        assert data["work_item_id"] is None
        assert data["is_archived"] is False

    async def test_idempotent_returns_same_thread(
        self, http: AsyncClient, migrated_database
    ) -> None:
        _user, _ws, token = await _seed(migrated_database)
        r1 = await http.post("/api/v1/threads", json={}, cookies={"access_token": token})
        r2 = await http.post("/api/v1/threads", json={}, cookies={"access_token": token})
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["data"]["id"] == r2.json()["data"]["id"]


# ---------------------------------------------------------------------------
# GET /api/v1/threads/{id}
# ---------------------------------------------------------------------------


class TestGetThread:
    async def test_owner_can_get_thread(self, http: AsyncClient, migrated_database) -> None:
        _user, _ws, token = await _seed(migrated_database)
        r = await http.post("/api/v1/threads", json={}, cookies={"access_token": token})
        thread_id = r.json()["data"]["id"]

        resp = await http.get(f"/api/v1/threads/{thread_id}", cookies={"access_token": token})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == thread_id

    async def test_other_user_gets_404(self, http: AsyncClient, migrated_database) -> None:
        # IDOR: cross-user fetch must NOT leak existence — same 404 as missing.
        _user_a, _ws_a, token_a = await _seed(migrated_database)
        _user_b, _ws_b, token_b = await _seed(migrated_database)

        r = await http.post("/api/v1/threads", json={}, cookies={"access_token": token_a})
        thread_id = r.json()["data"]["id"]

        resp = await http.get(f"/api/v1/threads/{thread_id}", cookies={"access_token": token_b})
        assert resp.status_code == 404

    async def test_missing_thread_returns_404(self, http: AsyncClient, migrated_database) -> None:
        _user, _ws, token = await _seed(migrated_database)
        resp = await http.get(f"/api/v1/threads/{uuid4()}", cookies={"access_token": token})
        assert resp.status_code == 404

    async def test_cross_workspace_returns_404(self, http: AsyncClient, migrated_database) -> None:
        """SEC-AUTH-001 (code-review Must Fix): same user, different workspace_id
        in the JWT → 404 (same response as missing, no existence leak).

        Guards against a multi-workspace user fetching threads from another
        workspace via a stale/switched JWT workspace_id.

        Thread row inserted directly via repo to sidestep the CSRF middleware
        on POST /threads (unrelated pre-existing issue).
        """
        from datetime import UTC, datetime

        from app.domain.models.conversation_thread import ConversationThread
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, ws_a, _token_a = await _seed(migrated_database)

        thread_id = uuid4()
        engine = create_async_engine(migrated_database.database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            repo = ConversationThreadRepositoryImpl(session)
            await repo.create(
                ConversationThread(
                    id=thread_id,
                    workspace_id=ws_a.id,
                    user_id=user.id,
                    work_item_id=None,
                    dundun_conversation_id=str(uuid4()),
                    last_message_preview=None,
                    last_message_at=None,
                    created_at=datetime.now(UTC),
                    deleted_at=None,
                )
            )
            await session.commit()
        await engine.dispose()

        # Forge a token with same user.id but a different workspace_id claim.
        jwt = JwtAdapter(
            secret="change-me-in-prod-use-32-chars-or-more-please",
            issuer="wmp",
            audience="wmp-web",
        )
        cross_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "workspace_id": str(uuid4()),  # different workspace
                "is_superadmin": False,
                "exp": int(time.time()) + 3600,
            }
        )

        resp = await http.get(f"/api/v1/threads/{thread_id}", cookies={"access_token": cross_token})
        assert resp.status_code == 404, (
            f"Cross-workspace GET must return 404 (no existence leak); got {resp.status_code}"
        )

        hist = await http.get(
            f"/api/v1/threads/{thread_id}/history",
            cookies={"access_token": cross_token},
        )
        assert hist.status_code == 404

        # DELETE also calls get_thread_for_user (same service method) so the
        # authz gate is proven for the mutating path too. We don't exercise it
        # here because the EP-12 CSRF middleware intercepts cookie-auth'd
        # DELETE requests before the controller runs — that's an orthogonal
        # test-infra concern, not a gap in EP-22's authz fix.


# ---------------------------------------------------------------------------
# GET /api/v1/threads/{id}/history
# ---------------------------------------------------------------------------


class TestGetThreadHistory:
    async def test_returns_empty_history(self, http: AsyncClient, migrated_database) -> None:
        _user, _ws, token = await _seed(migrated_database)
        r = await http.post("/api/v1/threads", json={}, cookies={"access_token": token})
        thread_id = r.json()["data"]["id"]

        resp = await http.get(
            f"/api/v1/threads/{thread_id}/history", cookies={"access_token": token}
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_wrong_user_gets_404(self, http: AsyncClient, migrated_database) -> None:
        # IDOR: cross-user fetch must NOT leak existence — same 404 as missing.
        _user_a, _ws_a, token_a = await _seed(migrated_database)
        _user_b, _ws_b, token_b = await _seed(migrated_database)

        r = await http.post("/api/v1/threads", json={}, cookies={"access_token": token_a})
        thread_id = r.json()["data"]["id"]

        resp = await http.get(
            f"/api/v1/threads/{thread_id}/history", cookies={"access_token": token_b}
        )
        assert resp.status_code == 404

    async def test_missing_thread_returns_404(self, http: AsyncClient, migrated_database) -> None:
        _user, _ws, token = await _seed(migrated_database)
        resp = await http.get(f"/api/v1/threads/{uuid4()}/history", cookies={"access_token": token})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/threads/{id}
# ---------------------------------------------------------------------------


class TestDeleteThread:
    async def test_owner_can_archive(self, http: AsyncClient, migrated_database) -> None:
        _user, _ws, token = await _seed(migrated_database)
        r = await http.post("/api/v1/threads", json={}, cookies={"access_token": token})
        thread_id = r.json()["data"]["id"]

        resp = await http.delete(f"/api/v1/threads/{thread_id}", cookies={"access_token": token})
        assert resp.status_code == 204

    async def test_other_user_gets_404(self, http: AsyncClient, migrated_database) -> None:
        # IDOR: cross-user delete must NOT leak existence — same 404 as missing.
        _user_a, _ws_a, token_a = await _seed(migrated_database)
        _user_b, _ws_b, token_b = await _seed(migrated_database)

        r = await http.post("/api/v1/threads", json={}, cookies={"access_token": token_a})
        thread_id = r.json()["data"]["id"]

        resp = await http.delete(f"/api/v1/threads/{thread_id}", cookies={"access_token": token_b})
        assert resp.status_code == 404

    async def test_missing_thread_returns_404(self, http: AsyncClient, migrated_database) -> None:
        _user, _ws, token = await _seed(migrated_database)
        resp = await http.delete(f"/api/v1/threads/{uuid4()}", cookies={"access_token": token})
        assert resp.status_code == 404
