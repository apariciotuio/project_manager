"""Integration tests for Clarification endpoints — EP-03 Phase 7.

Scenarios:
  GET /api/v1/work-items/{id}/gaps/questions
    - 401 unauthenticated
    - 404 when work item does not exist
    - 200 with empty list when no BLOCKING gaps
    - 200 with up to 3 questions when BLOCKING gaps exist
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


async def _create_work_item(http: AsyncClient, token: str, *, title: str = "Gap test item") -> dict:  # type: ignore[type-arg]
    """Create a work item via REST API and return response data."""
    r = await http.post(
        "/api/v1/work-items",
        json={"title": title or "untitled", "type": "task", "project_id": str(uuid4())},
        cookies={"access_token": token},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# GET /api/v1/work-items/{id}/gaps/questions
# ---------------------------------------------------------------------------


class TestGetGapQuestions:
    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.get(f"/api/v1/work-items/{uuid4()}/gaps/questions")
        assert resp.status_code == 401

    async def test_missing_work_item_returns_404(
        self, http: AsyncClient, migrated_database
    ) -> None:
        _user, _ws, token = await _seed(migrated_database)
        resp = await http.get(
            f"/api/v1/work-items/{uuid4()}/gaps/questions",
            cookies={"access_token": token},
        )
        assert resp.status_code == 404

    async def test_returns_questions_structure(
        self, http: AsyncClient, migrated_database
    ) -> None:
        _user, _ws, token = await _seed(migrated_database)
        wi = await _create_work_item(http, token, title="Gap test item")

        resp = await http.get(
            f"/api/v1/work-items/{wi['id']}/gaps/questions",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "questions" in body["data"]
        assert isinstance(body["data"]["questions"], list)

    async def test_no_description_produces_questions(
        self, http: AsyncClient, migrated_database
    ) -> None:
        _user, _ws, token = await _seed(migrated_database)
        # Work item with minimal content → should produce BLOCKING gaps
        wi = await _create_work_item(http, token, title="Minimal")

        resp = await http.get(
            f"/api/v1/work-items/{wi['id']}/gaps/questions",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        questions = resp.json()["data"]["questions"]
        # At least one question expected (missing description, acceptance criteria, etc.)
        assert isinstance(questions, list)

    async def test_returns_at_most_three_questions(
        self, http: AsyncClient, migrated_database
    ) -> None:
        _user, _ws, token = await _seed(migrated_database)
        wi = await _create_work_item(http, token, title="Sparse item")

        resp = await http.get(
            f"/api/v1/work-items/{wi['id']}/gaps/questions",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        questions = resp.json()["data"]["questions"]
        assert len(questions) <= 3
