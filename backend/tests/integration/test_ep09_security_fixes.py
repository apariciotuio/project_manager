"""EP-09 security regression tests — MF-1 through MF-4.

Covers:
- MF-1: kanban cache key excludes project_id/limit → cross-project leak
- MF-2: person dashboard cache key not workspace-scoped
- MF-3: pending reviews query leaks cross-workspace
- MF-4: pipeline team_id param hashed but never applied to query

Integration level: real DB (migrated_database + db_session fixtures).
"""
from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.adapters.in_memory_cache_adapter import InMemoryCacheAdapter


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class FakeCache(InMemoryCacheAdapter):
    """Thin subclass so we can import without the full DI stack."""
    pass


async def _create_workspace_with_user(session: AsyncSession) -> tuple[UUID, UUID]:
    """Create workspace + user + membership. Returns (workspace_id, user_id)."""
    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import WorkspaceMembershipRepositoryImpl
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    uid = f"u-{uuid4().hex[:8]}"
    users = UserRepositoryImpl(session)
    workspaces = WorkspaceRepositoryImpl(session)
    memberships = WorkspaceMembershipRepositoryImpl(session)

    user = User.from_google_claims(sub=uid, email=f"{uid}@test.com", name="T", picture=None)
    await users.upsert(user)

    ws = Workspace.create_from_email(email=user.email, created_by=user.id)
    ws.slug = f"ws-{uuid4().hex[:8]}"
    await workspaces.create(ws)
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
        )
    )
    await session.commit()
    return ws.id, user.id


async def _get_or_create_project(session: AsyncSession, workspace_id: UUID, user_id: UUID) -> UUID:
    """Return a default project for the workspace, creating one if needed."""
    from sqlalchemy import select
    from app.infrastructure.persistence.models.orm import ProjectORM
    result = await session.execute(
        select(ProjectORM).where(ProjectORM.workspace_id == workspace_id).limit(1)
    )
    existing = result.scalars().first()
    if existing:
        return existing.id
    project = ProjectORM(workspace_id=workspace_id, name="Default", created_by=user_id)
    session.add(project)
    await session.flush()
    return project.id


async def _create_work_item(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    title: str = "Test work item",
    state: str = "draft",
    project_id: UUID | None = None,
) -> UUID:
    from app.infrastructure.persistence.models.orm import WorkItemORM
    if project_id is None:
        project_id = await _get_or_create_project(session, workspace_id, user_id)
    item = WorkItemORM(
        workspace_id=workspace_id,
        creator_id=user_id,
        owner_id=user_id,
        title=title,
        type="story",
        state=state,
        project_id=project_id,
        completeness_score=0,
    )
    session.add(item)
    await session.flush()
    return item.id


async def _create_version(session: AsyncSession, work_item_id: UUID, workspace_id: UUID, user_id: UUID) -> UUID:
    from app.infrastructure.persistence.models.orm import WorkItemVersionORM
    from sqlalchemy import select
    result = await session.execute(
        select(WorkItemVersionORM).where(WorkItemVersionORM.work_item_id == work_item_id)
    )
    existing = result.scalars().first()
    if existing:
        return existing.id

    version = WorkItemVersionORM(
        work_item_id=work_item_id,
        workspace_id=workspace_id,
        version_number=1,
        created_by=user_id,
        snapshot={},
    )
    session.add(version)
    await session.flush()
    return version.id


async def _create_review_request(
    session: AsyncSession,
    work_item_id: UUID,
    reviewer_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    from app.infrastructure.persistence.models.orm import ReviewRequestORM
    version_id = await _create_version(session, work_item_id, workspace_id, user_id)
    rr = ReviewRequestORM(
        work_item_id=work_item_id,
        version_id=version_id,
        reviewer_type="user",
        reviewer_id=reviewer_id,
        status="pending",
        requested_by=user_id,
    )
    session.add(rr)
    await session.flush()


# ---------------------------------------------------------------------------
# MF-3: cross-workspace pending reviews leak
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mf3_pending_reviews_scoped_to_workspace(db_session: AsyncSession) -> None:
    """Reviewer in 2 workspaces — each workspace's count is independent."""
    from app.application.services.person_dashboard_service import PersonDashboardService

    # Two workspaces, same reviewer
    ws_a_id, user_a_id = await _create_workspace_with_user(db_session)
    ws_b_id, user_b_id = await _create_workspace_with_user(db_session)

    # The reviewer is a shared user — create directly
    from app.domain.models.user import User
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.persistence.workspace_membership_repository_impl import WorkspaceMembershipRepositoryImpl

    reviewer_sub = f"rev-{uuid4().hex[:8]}"
    reviewer = User.from_google_claims(sub=reviewer_sub, email=f"{reviewer_sub}@test.com", name="Rev", picture=None)
    await UserRepositoryImpl(db_session).upsert(reviewer)
    # Add reviewer to both workspaces
    for ws_id in (ws_a_id, ws_b_id):
        await WorkspaceMembershipRepositoryImpl(db_session).create(
            WorkspaceMembership.create(workspace_id=ws_id, user_id=reviewer.id, role="member", is_default=False)
        )
    await db_session.commit()

    # 1 review in workspace_A
    item_a = await _create_work_item(db_session, ws_a_id, user_a_id)
    await _create_review_request(db_session, item_a, reviewer.id, ws_a_id, user_a_id)

    # 2 reviews in workspace_B
    item_b1 = await _create_work_item(db_session, ws_b_id, user_b_id)
    item_b2 = await _create_work_item(db_session, ws_b_id, user_b_id)
    await _create_review_request(db_session, item_b1, reviewer.id, ws_b_id, user_b_id)
    await _create_review_request(db_session, item_b2, reviewer.id, ws_b_id, user_b_id)
    await db_session.commit()

    cache = FakeCache()
    svc = PersonDashboardService(session=db_session, cache=cache)

    result_a = await svc.get_metrics(reviewer.id, workspace_id=ws_a_id)
    result_b = await svc.get_metrics(reviewer.id, workspace_id=ws_b_id)

    assert result_a["pending_reviews_count"] == 1, (
        f"workspace_A should have 1 pending review, got {result_a['pending_reviews_count']}"
    )
    assert result_b["pending_reviews_count"] == 2, (
        f"workspace_B should have 2 pending reviews, got {result_b['pending_reviews_count']}"
    )


# ---------------------------------------------------------------------------
# MF-2: person dashboard cache key not workspace-scoped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mf2_person_dashboard_cache_scoped_to_workspace(db_session: AsyncSession) -> None:
    """Same user in two workspaces must not collide in cache."""
    from app.application.services.person_dashboard_service import PersonDashboardService

    ws_a_id, _ = await _create_workspace_with_user(db_session)
    ws_b_id, _ = await _create_workspace_with_user(db_session)

    # Create the shared user
    from app.domain.models.user import User
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.persistence.workspace_membership_repository_impl import WorkspaceMembershipRepositoryImpl

    sub = f"shared-{uuid4().hex[:8]}"
    user = User.from_google_claims(sub=sub, email=f"{sub}@test.com", name="S", picture=None)
    await UserRepositoryImpl(db_session).upsert(user)
    for ws_id in (ws_a_id, ws_b_id):
        await WorkspaceMembershipRepositoryImpl(db_session).create(
            WorkspaceMembership.create(workspace_id=ws_id, user_id=user.id, role="member", is_default=False)
        )
    await db_session.commit()

    # 3 items owned in workspace_A
    for i in range(3):
        item_id = await _create_work_item(db_session, ws_a_id, user.id, title=f"A-{i}")
        from app.infrastructure.persistence.models.orm import WorkItemORM
        # update owner_id explicitly
    # Items above already have user.id as owner — committed via flush
    await db_session.commit()

    cache = FakeCache()
    svc = PersonDashboardService(session=db_session, cache=cache)

    # Call workspace_A first — populates cache
    result_a = await svc.get_metrics(user.id, workspace_id=ws_a_id)
    # Call workspace_B second — must NOT hit workspace_A's cache
    result_b = await svc.get_metrics(user.id, workspace_id=ws_b_id)

    # workspace_B has 0 owned items — if cache leaks, it would return 3
    total_a = sum(result_a["owned_by_state"].values())
    total_b = sum(result_b["owned_by_state"].values())
    assert total_a == 3, f"workspace_A should have 3 items, got {total_a}"
    assert total_b == 0, f"workspace_B should have 0 items, got {total_b} (possible cache leak)"


# ---------------------------------------------------------------------------
# MF-1: kanban cache key excludes project_id → cross-project leak
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mf1_kanban_cache_scoped_to_project(db_session: AsyncSession) -> None:
    """Same workspace, different project_ids must produce isolated cache entries."""
    from app.application.services.kanban_service import KanbanService

    ws_id, user_id = await _create_workspace_with_user(db_session)
    from app.infrastructure.persistence.models.orm import ProjectORM
    proj_a_orm = ProjectORM(workspace_id=ws_id, name="Project A", created_by=user_id)
    proj_b_orm = ProjectORM(workspace_id=ws_id, name="Project B", created_by=user_id)
    db_session.add_all([proj_a_orm, proj_b_orm])
    await db_session.flush()
    proj_a = proj_a_orm.id
    proj_b = proj_b_orm.id

    # 2 items in project_A (state=draft), 5 items in project_B (state=in_clarification)
    for _ in range(2):
        await _create_work_item(db_session, ws_id, user_id, state="draft", project_id=proj_a)
    for _ in range(5):
        await _create_work_item(db_session, ws_id, user_id, state="in_clarification", project_id=proj_b)
    await db_session.commit()

    cache = FakeCache()
    svc = KanbanService(session=db_session, cache=cache)

    result_a = await svc.get_board(workspace_id=ws_id, group_by="state", project_id=proj_a)
    result_b = await svc.get_board(workspace_id=ws_id, group_by="state", project_id=proj_b)

    draft_a = next((c for c in result_a["columns"] if c["key"] == "draft"), None)
    clarif_b = next((c for c in result_b["columns"] if c["key"] == "in_clarification"), None)

    assert draft_a is not None
    assert draft_a["total_count"] == 2, f"project_A draft count should be 2, got {draft_a['total_count']}"
    assert clarif_b is not None
    assert clarif_b["total_count"] == 5, f"project_B in_clarification count should be 5, got {clarif_b['total_count']}"

    # Critical: project_B must not see project_A's drafts from cache
    draft_b = next((c for c in result_b["columns"] if c["key"] == "draft"), None)
    assert draft_b is not None
    assert draft_b["total_count"] == 0, (
        f"project_B should have 0 draft items, got {draft_b['total_count']} (possible cache leak from project_A)"
    )


@pytest.mark.asyncio
async def test_mf1_kanban_cache_scoped_to_limit(db_session: AsyncSession) -> None:
    """Different limit values must produce distinct cache entries (not share a stale slice)."""
    from app.application.services.kanban_service import KanbanService

    ws_id, user_id = await _create_workspace_with_user(db_session)

    # 10 draft items
    for i in range(10):
        await _create_work_item(db_session, ws_id, user_id, state="draft")
    await db_session.commit()

    cache = FakeCache()
    svc = KanbanService(session=db_session, cache=cache)

    result_3 = await svc.get_board(workspace_id=ws_id, group_by="state", limit=3)
    result_10 = await svc.get_board(workspace_id=ws_id, group_by="state", limit=10)

    draft_3 = next(c for c in result_3["columns"] if c["key"] == "draft")
    draft_10 = next(c for c in result_10["columns"] if c["key"] == "draft")

    assert len(draft_3["cards"]) <= 3, f"limit=3 should cap at 3 cards, got {len(draft_3['cards'])}"
    assert len(draft_10["cards"]) == 10, (
        f"limit=10 should show 10 cards, got {len(draft_10['cards'])} (possible stale cache from limit=3)"
    )


# ---------------------------------------------------------------------------
# MF-4: pipeline team_id hashed but never applied to query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mf4_pipeline_filtered_by_team(db_session: AsyncSession) -> None:
    """Team A with 2 items, team B with 5 — each pipeline call returns its own count."""
    from app.application.services.pipeline_service import PipelineQueryService
    from app.infrastructure.persistence.models.orm import TeamMembershipORM, WorkItemORM
    from sqlalchemy import text

    ws_id, user_a_id = await _create_workspace_with_user(db_session)
    _, user_b_id = await _create_workspace_with_user(db_session)

    # Add user_b to workspace_A too
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.persistence.workspace_membership_repository_impl import WorkspaceMembershipRepositoryImpl
    await WorkspaceMembershipRepositoryImpl(db_session).create(
        WorkspaceMembership.create(workspace_id=ws_id, user_id=user_b_id, role="member", is_default=False)
    )
    await db_session.commit()

    # Create 2 teams using raw ORM (no team service dependency)
    from app.infrastructure.persistence.models.orm import TeamORM
    team_a = TeamORM(workspace_id=ws_id, name="Team A", created_by=user_a_id)
    team_b = TeamORM(workspace_id=ws_id, name="Team B", created_by=user_a_id)
    db_session.add_all([team_a, team_b])
    await db_session.flush()

    # Memberships
    db_session.add_all([
        TeamMembershipORM(team_id=team_a.id, user_id=user_a_id),
        TeamMembershipORM(team_id=team_b.id, user_id=user_b_id),
    ])
    await db_session.flush()

    # 2 items owned by user_a (team_A member), 5 owned by user_b (team_B member), all same workspace
    for _ in range(2):
        await _create_work_item(db_session, ws_id, user_a_id, state="draft")
    for _ in range(5):
        await _create_work_item(db_session, ws_id, user_b_id, state="draft")
    await db_session.commit()

    cache = FakeCache()
    svc = PipelineQueryService(session=db_session, cache=cache)

    result_a = await svc.get_pipeline(workspace_id=ws_id, team_id=team_a.id)
    result_b = await svc.get_pipeline(workspace_id=ws_id, team_id=team_b.id)

    count_a = sum(c["count"] for c in result_a["columns"])
    count_b = sum(c["count"] for c in result_b["columns"])

    assert count_a == 2, f"team_A pipeline should have 2 items total, got {count_a}"
    assert count_b == 5, f"team_B pipeline should have 5 items total, got {count_b}"
