"""MF-3 regression — version_number_target resolved from versioning repo.

A Dundun suggestion callback for a work item with 2 existing versions must
produce suggestions with version_number_target == 3, not hardcoded 1.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_SECRET = "dev-callback-secret"
_URL = "/api/v1/dundun/callback"


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(client: AsyncClient, payload: dict, *, secret: str = _SECRET):
    raw = json.dumps(payload).encode()
    sig = _sign(raw, secret)
    return client.post(
        _URL,
        content=raw,
        headers={"Content-Type": "application/json", "X-Dundun-Signature": sig},
    )


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
                "work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()
    fake_cache = FakeCache()

    async def _override_cache():
        yield fake_cache

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
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


@pytest_asyncio.fixture
async def seeded_with_versions(migrated_database):
    """Seed work item with 2 existing versions. Returns (user_id, workspace_id, work_item_id)."""
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.work_item_version_repository_impl import (
        WorkItemVersionRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        uid = uuid4().hex[:6]
        user = User.from_google_claims(
            sub=f"mf3-{uid}", email=f"mf3-{uid}@test.com", name="MF3", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"mf3-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title="MF-3 version test item",
            type=WorkItemType.BUG,
            owner_id=user.id,
            creator_id=user.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)

        version_repo = WorkItemVersionRepositoryImpl(session)
        # Create 2 versions so the next suggestion should target version 3
        await version_repo.append(
            work_item_id=wi.id,
            snapshot={"title": wi.title, "v": 1},
            created_by=user.id,
        )
        await version_repo.append(
            work_item_id=wi.id,
            snapshot={"title": wi.title, "v": 2},
            created_by=user.id,
        )
        await session.commit()

    await engine.dispose()
    return user.id, ws.id, wi.id


@pytest.mark.asyncio
async def test_suggestion_callback_version_target_from_repo(
    http, seeded_with_versions, migrated_database
):
    """Suggestion created after 2 existing versions must have version_number_target == 3."""
    user_id, _ws_id, wi_id = seeded_with_versions
    request_id = str(uuid4())
    batch_id = str(uuid4())

    payload = {
        "agent": "wm_suggestion_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(wi_id),
        "batch_id": batch_id,
        "user_id": str(user_id),
        "suggestions": [
            {
                "section_id": None,
                "proposed_content": "New description",
                "current_content": "Old description",
                "rationale": "Better clarity",
            },
        ],
    }

    resp = await _post(http, payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["count"] == 1

    # Verify version_number_target is 3 (latest=2, target=2+1)
    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT version_number_target FROM assistant_suggestions "
                    "WHERE dundun_request_id = :rid"
                ),
                {"rid": request_id},
            )
        ).fetchone()
    await engine.dispose()

    assert row is not None
    assert row[0] == 3, f"Expected version_number_target=3, got {row[0]}"


@pytest.mark.asyncio
async def test_suggestion_callback_version_target_no_versions(http, migrated_database):
    """Suggestion for a work item with no versions should have version_number_target == 1."""
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        uid = uuid4().hex[:6]
        user = User.from_google_claims(
            sub=f"mf3b-{uid}", email=f"mf3b-{uid}@test.com", name="MF3B", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"mf3b-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        wi = WorkItem.create(
            title="MF-3 no-version test",
            type=WorkItemType.TASK,
            owner_id=user.id,
            creator_id=user.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)
        await session.commit()

    await engine.dispose()

    request_id = str(uuid4())
    payload = {
        "agent": "wm_suggestion_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(wi.id),
        "batch_id": str(uuid4()),
        "user_id": str(user.id),
        "suggestions": [
            {
                "section_id": None,
                "proposed_content": "Proposed",
                "current_content": "Current",
                "rationale": None,
            }
        ],
    }

    resp = await _post(http, payload)
    assert resp.status_code == 200, resp.text

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT version_number_target FROM assistant_suggestions "
                    "WHERE dundun_request_id = :rid"
                ),
                {"rid": request_id},
            )
        ).fetchone()
    await engine.dispose()

    assert row is not None
    assert row[0] == 1, f"Expected version_number_target=1 when no versions, got {row[0]}"
