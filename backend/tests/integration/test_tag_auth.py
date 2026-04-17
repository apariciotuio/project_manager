"""EP-21 — Tag endpoint auth + workspace scoping integration tests.

Covers MF-1 + SF-4:
  - 401 when no auth token on all 4 previously-unprotected endpoints
  - 404 when accessing tags/work-items from a different workspace (IDOR prevention)
  - 200/201 when properly authorized

Endpoints under test:
  PATCH  /api/v1/tags/{tag_id}
  DELETE /api/v1/tags/{tag_id}
  DELETE /api/v1/work-items/{work_item_id}/tags/{tag_id}
  GET    /api/v1/work-items/{work_item_id}/tags
"""
from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.models.tag import Tag, WorkItemTag
from app.domain.models.user import User
from app.domain.models.work_item import WorkItem
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.tag_repository_impl import (
    TagRepositoryImpl,
    WorkItemTagRepositoryImpl,
)
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl
from app.main import create_app


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
                "TRUNCATE TABLE work_item_tags, tags, "
                "ownership_history, state_transitions, work_items, "
                "workspace_memberships, sessions, oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    fastapi_app = create_app()
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


def _mint_token(user: User, workspace_id: UUID) -> str:
    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
    return jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


async def _seed_workspace(
    migrated_database,
    *,
    sub: str,
    email: str,
    slug: str,
) -> tuple[User, Workspace, str]:
    """Create a user + workspace + admin membership. Returns (user, workspace, jwt_token)."""
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(sub=sub, email=email, name=email.split("@")[0], picture=None)
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

    await engine.dispose()
    return user, ws, _mint_token(user, ws.id)


async def _create_tag(migrated_database, *, workspace_id: UUID, created_by: UUID, name: str) -> Tag:
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        repo = TagRepositoryImpl(session)
        tag = Tag.create(workspace_id=workspace_id, name=name, created_by=created_by)
        saved = await repo.create(tag)
        await session.commit()
    await engine.dispose()
    return saved


async def _create_work_item(migrated_database, *, workspace_id: UUID, created_by: UUID) -> WorkItem:
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        repo = WorkItemRepositoryImpl(session)
        wi = WorkItem.create(
            workspace_id=workspace_id,
            title="Test work item for tag auth",
            type="feature",
            created_by=created_by,
        )
        saved = await repo.create(wi)
        await session.commit()
    await engine.dispose()
    return saved


# ---------------------------------------------------------------------------
# 401 — no auth token on all 4 endpoints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path_tmpl"),
    [
        ("PATCH", "/api/v1/tags/{tag_id}"),
        ("DELETE", "/api/v1/tags/{tag_id}"),
        ("DELETE", "/api/v1/work-items/{work_item_id}/tags/{tag_id}"),
        ("GET", "/api/v1/work-items/{work_item_id}/tags"),
    ],
)
async def test_unauthenticated_returns_401(http, method, path_tmpl) -> None:
    tag_id = uuid4()
    work_item_id = uuid4()
    path = path_tmpl.format(tag_id=tag_id, work_item_id=work_item_id)
    resp = await http.request(method, path, json={"name": "x"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 404 — cross-workspace access (not 403 — no existence leak)
# ---------------------------------------------------------------------------


async def test_patch_tag_cross_workspace_returns_404(http, migrated_database) -> None:
    user_a, ws_a, token_a = await _seed_workspace(
        migrated_database, sub="sub-tag-a1", email="a1@test.com", slug="ws-tag-a1"
    )
    user_b, ws_b, token_b = await _seed_workspace(
        migrated_database, sub="sub-tag-b1", email="b1@test.com", slug="ws-tag-b1"
    )
    # tag belongs to workspace B
    tag = await _create_tag(migrated_database, workspace_id=ws_b.id, created_by=user_b.id, name="cross-tag-patch")

    # user A tries to PATCH workspace B's tag
    resp = await http.patch(
        f"/api/v1/tags/{tag.id}",
        json={"name": "hacked"},
        cookies={"access_token": token_a},
    )
    assert resp.status_code == 404


async def test_delete_tag_cross_workspace_returns_404(http, migrated_database) -> None:
    user_a, ws_a, token_a = await _seed_workspace(
        migrated_database, sub="sub-tag-a2", email="a2@test.com", slug="ws-tag-a2"
    )
    user_b, ws_b, token_b = await _seed_workspace(
        migrated_database, sub="sub-tag-b2", email="b2@test.com", slug="ws-tag-b2"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws_b.id, created_by=user_b.id, name="cross-tag-delete")

    resp = await http.delete(
        f"/api/v1/tags/{tag.id}",
        cookies={"access_token": token_a},
    )
    assert resp.status_code == 404


async def test_remove_work_item_tag_cross_workspace_returns_404(http, migrated_database) -> None:
    user_a, ws_a, token_a = await _seed_workspace(
        migrated_database, sub="sub-tag-a3", email="a3@test.com", slug="ws-tag-a3"
    )
    user_b, ws_b, token_b = await _seed_workspace(
        migrated_database, sub="sub-tag-b3", email="b3@test.com", slug="ws-tag-b3"
    )
    wi = await _create_work_item(migrated_database, workspace_id=ws_b.id, created_by=user_b.id)
    tag = await _create_tag(migrated_database, workspace_id=ws_b.id, created_by=user_b.id, name="cross-tag-rm")

    # user A tries to delete a tag from workspace B's work item
    resp = await http.delete(
        f"/api/v1/work-items/{wi.id}/tags/{tag.id}",
        cookies={"access_token": token_a},
    )
    assert resp.status_code == 404


async def test_list_work_item_tags_cross_workspace_returns_404(http, migrated_database) -> None:
    user_a, ws_a, token_a = await _seed_workspace(
        migrated_database, sub="sub-tag-a4", email="a4@test.com", slug="ws-tag-a4"
    )
    user_b, ws_b, token_b = await _seed_workspace(
        migrated_database, sub="sub-tag-b4", email="b4@test.com", slug="ws-tag-b4"
    )
    wi = await _create_work_item(migrated_database, workspace_id=ws_b.id, created_by=user_b.id)

    resp = await http.get(
        f"/api/v1/work-items/{wi.id}/tags",
        cookies={"access_token": token_a},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 200/201 — authorized access
# ---------------------------------------------------------------------------


async def test_patch_tag_authorized_returns_200(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-ok1", email="ok1@test.com", slug="ws-tag-ok1"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="original-name")

    resp = await http.patch(
        f"/api/v1/tags/{tag.id}",
        json={"name": "renamed"},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "renamed"


async def test_delete_tag_authorized_returns_200(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-ok2", email="ok2@test.com", slug="ws-tag-ok2"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="to-archive")

    resp = await http.delete(
        f"/api/v1/tags/{tag.id}",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == str(tag.id)


async def test_list_work_item_tags_authorized_returns_200(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-ok3", email="ok3@test.com", slug="ws-tag-ok3"
    )
    wi = await _create_work_item(migrated_database, workspace_id=ws.id, created_by=user.id)

    resp = await http.get(
        f"/api/v1/work-items/{wi.id}/tags",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


async def test_remove_work_item_tag_authorized_returns_200(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-ok4", email="ok4@test.com", slug="ws-tag-ok4"
    )
    wi = await _create_work_item(migrated_database, workspace_id=ws.id, created_by=user.id)
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="remove-me-tag")

    resp = await http.delete(
        f"/api/v1/work-items/{wi.id}/tags/{tag.id}",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# MF-2 — PATCH accepts partial updates
# ---------------------------------------------------------------------------


async def test_patch_tag_name_only(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-p1", email="p1@test.com", slug="ws-tag-p1"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="patch-name-only")

    resp = await http.patch(
        f"/api/v1/tags/{tag.id}",
        json={"name": "new-name"},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "new-name"
    assert data["color"] == tag.color  # unchanged


async def test_patch_tag_color_only(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-p2", email="p2@test.com", slug="ws-tag-p2"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="patch-color-only")

    resp = await http.patch(
        f"/api/v1/tags/{tag.id}",
        json={"color": "#ff0000"},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["color"] == "#ff0000"


async def test_patch_tag_archived_only(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-p3", email="p3@test.com", slug="ws-tag-p3"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="patch-archived-only")

    resp = await http.patch(
        f"/api/v1/tags/{tag.id}",
        json={"archived": True},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_archived"] is True


async def test_patch_tag_multi_field(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-p4", email="p4@test.com", slug="ws-tag-p4"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="patch-multi")

    resp = await http.patch(
        f"/api/v1/tags/{tag.id}",
        json={"name": "new-multi", "color": "#00ff00"},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "new-multi"
    assert data["color"] == "#00ff00"


async def test_patch_tag_all_none_returns_422(http, migrated_database) -> None:
    user, ws, token = await _seed_workspace(
        migrated_database, sub="sub-tag-p5", email="p5@test.com", slug="ws-tag-p5"
    )
    tag = await _create_tag(migrated_database, workspace_id=ws.id, created_by=user.id, name="patch-all-none")

    resp = await http.patch(
        f"/api/v1/tags/{tag.id}",
        json={},
        cookies={"access_token": token},
    )
    assert resp.status_code == 422
