"""WorkItemRepositoryImpl integration tests.

Covers:
- save + get round-trip (all fields, enum values, null parent, empty tags, null priority)
- list() filter combos (state, type, has_override) + pagination
- soft-delete exclusion / include_deleted
- record_transition + get_transitions DESC ordering
- record_ownership_change + get_ownership_history DESC ordering
- cross-workspace isolation (explicit workspace_id filter on get)
- append-only trigger: UPDATE on state_transitions / ownership_history raises
- FK violation on owner_id -> UserNotFoundError
- RLS default-deny: SELECT without set_config returns zero rows even when rows exist
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.domain.exceptions import UserNotFoundError
from app.domain.models.user import User
from app.domain.models.work_item import WorkItem
from app.domain.models.workspace import Workspace
from app.domain.queries.page import Page
from app.domain.queries.work_item_filters import WorkItemFilters
from app.domain.value_objects.ownership_record import OwnershipRecord
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.state_transition import StateTransition
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.persistence.session_context import with_workspace
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(session, *, sub: str, email: str) -> User:
    user = User.from_google_claims(sub=sub, email=email, name="Test User", picture=None)
    repo = UserRepositoryImpl(session)
    await repo.upsert(user)
    await session.commit()
    return user


async def _make_workspace(session, *, created_by_id, slug_email: str) -> Workspace:
    ws = Workspace.create_from_email(email=slug_email, created_by=created_by_id)
    repo = WorkspaceRepositoryImpl(session)
    await repo.create(ws)
    await session.commit()
    return ws


def _make_work_item(
    *,
    owner_id,
    creator_id,
    project_id,
    title: str = "My work item",
    type: WorkItemType = WorkItemType.TASK,
    priority: Priority | None = None,
    tags: list[str] | None = None,
    parent_work_item_id=None,
) -> WorkItem:
    return WorkItem.create(
        title=title,
        type=type,
        owner_id=owner_id,
        creator_id=creator_id,
        project_id=project_id,
        priority=priority,
        tags=tags,
        parent_work_item_id=parent_work_item_id,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def ctx(db_session):
    """Provide a dict with user, workspace, project_id, and repo wired to db_session."""
    user = await _make_user(db_session, sub="wi-owner", email="owner@acme.io")
    ws = await _make_workspace(db_session, created_by_id=user.id, slug_email="owner@acme.io")
    project_id = uuid4()
    await with_workspace(db_session, ws.id)
    repo = WorkItemRepositoryImpl(db_session)
    return {
        "session": db_session,
        "user": user,
        "ws": ws,
        "project_id": project_id,
        "repo": repo,
    }


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


async def test_save_get_roundtrip_all_fields(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    item = _make_work_item(
        owner_id=user.id,
        creator_id=user.id,
        project_id=project_id,
        title="Full field item",
        type=WorkItemType.BUG,
        priority=Priority.HIGH,
        tags=["backend", "urgent"],
    )
    saved = await repo.save(item, ws.id)
    await ctx["session"].commit()

    fetched = await repo.get(saved.id, ws.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.title == "Full field item"
    assert fetched.type == WorkItemType.BUG
    assert fetched.state == WorkItemState.DRAFT
    assert fetched.owner_id == user.id
    assert fetched.creator_id == user.id
    assert fetched.priority == Priority.HIGH
    assert fetched.tags == ["backend", "urgent"]
    assert fetched.parent_work_item_id is None
    assert fetched.deleted_at is None
    assert fetched.exported_at is None
    assert fetched.export_reference is None


async def test_save_get_roundtrip_null_priority_empty_tags(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    item = _make_work_item(
        owner_id=user.id,
        creator_id=user.id,
        project_id=project_id,
        title="Minimal item",
        priority=None,
        tags=[],
    )
    saved = await repo.save(item, ws.id)
    await ctx["session"].commit()

    fetched = await repo.get(saved.id, ws.id)
    assert fetched is not None
    assert fetched.priority is None
    assert fetched.tags == []
    assert fetched.parent_work_item_id is None


async def test_save_get_roundtrip_with_parent(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    parent = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Parent item"
    )
    await repo.save(parent, ws.id)
    await ctx["session"].commit()

    child = _make_work_item(
        owner_id=user.id,
        creator_id=user.id,
        project_id=project_id,
        title="Child item",
        parent_work_item_id=parent.id,
    )
    saved_child = await repo.save(child, ws.id)
    await ctx["session"].commit()

    fetched = await repo.get(saved_child.id, ws.id)
    assert fetched is not None
    assert fetched.parent_work_item_id == parent.id


async def test_save_upsert_updates_existing(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    item = _make_work_item(
        owner_id=user.id,
        creator_id=user.id,
        project_id=project_id,
        title="Original title",
    )
    await repo.save(item, ws.id)
    await ctx["session"].commit()

    item.title = "Updated title"
    updated = await repo.save(item, ws.id)
    await ctx["session"].commit()

    fetched = await repo.get(updated.id, ws.id)
    assert fetched is not None
    assert fetched.title == "Updated title"


async def test_get_missing_returns_none(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    assert await repo.get(uuid4(), ws.id) is None


# ---------------------------------------------------------------------------
# list() filter + pagination tests
# ---------------------------------------------------------------------------


async def test_list_filter_by_state(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    draft = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Draft item"
    )
    await repo.save(draft, ws.id)

    # Force another item to in_clarification state directly
    other = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Other state"
    )
    other.state = WorkItemState.IN_CLARIFICATION
    await repo.save(other, ws.id)
    await ctx["session"].commit()

    page = await repo.list(ws.id, project_id, WorkItemFilters(state=WorkItemState.DRAFT))
    assert page.total == 1
    assert page.items[0].title == "Draft item"


async def test_list_filter_by_type(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    bug = _make_work_item(
        owner_id=user.id,
        creator_id=user.id,
        project_id=project_id,
        title="A bug",
        type=WorkItemType.BUG,
    )
    task = _make_work_item(
        owner_id=user.id,
        creator_id=user.id,
        project_id=project_id,
        title="A task",
        type=WorkItemType.TASK,
    )
    await repo.save(bug, ws.id)
    await repo.save(task, ws.id)
    await ctx["session"].commit()

    page = await repo.list(ws.id, project_id, WorkItemFilters(type=WorkItemType.BUG))
    assert page.total == 1
    assert page.items[0].type == WorkItemType.BUG  # noqa: E501


async def test_list_filter_by_has_override(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    normal = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Normal"
    )
    override_item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Override"
    )
    override_item.has_override = True
    override_item.override_justification = "justified override reason here"

    await repo.save(normal, ws.id)
    await repo.save(override_item, ws.id)
    await ctx["session"].commit()

    page = await repo.list(ws.id, project_id, WorkItemFilters(has_override=True))
    assert page.total == 1
    assert page.items[0].has_override is True

    page_false = await repo.list(ws.id, project_id, WorkItemFilters(has_override=False))
    assert page_false.total == 1
    assert page_false.items[0].has_override is False


async def test_list_pagination_math(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    for i in range(5):
        item = _make_work_item(
            owner_id=user.id,
            creator_id=user.id,
            project_id=project_id,
            title=f"Item {i:02d}",
        )
        await repo.save(item, ws.id)
    await ctx["session"].commit()

    page1 = await repo.list(ws.id, project_id, WorkItemFilters(page=1, page_size=2))
    assert page1.total == 5
    assert len(page1.items) == 2
    assert page1.page == 1
    assert page1.page_size == 2

    page2 = await repo.list(ws.id, project_id, WorkItemFilters(page=2, page_size=2))
    assert page2.total == 5
    assert len(page2.items) == 2

    page3 = await repo.list(ws.id, project_id, WorkItemFilters(page=3, page_size=2))
    assert page3.total == 5
    assert len(page3.items) == 1

    # page beyond end
    page4 = await repo.list(ws.id, project_id, WorkItemFilters(page=4, page_size=2))
    assert page4.total == 0
    assert page4.items == []


async def test_list_returns_empty_page_when_no_items(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    project_id = ctx["project_id"]

    page = await repo.list(ws.id, project_id, WorkItemFilters())
    assert isinstance(page, Page)
    assert page.total == 0
    assert page.items == []


# ---------------------------------------------------------------------------
# Soft-delete tests
# ---------------------------------------------------------------------------


async def test_soft_delete_excluded_by_default(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="To delete"
    )
    saved = await repo.save(item, ws.id)
    await ctx["session"].commit()

    await repo.delete(saved.id, ws.id)
    await ctx["session"].commit()

    page = await repo.list(ws.id, project_id, WorkItemFilters())
    assert page.total == 0

    # get() still returns it (get does NOT filter deleted_at)
    fetched = await repo.get(saved.id, ws.id)
    assert fetched is not None
    assert fetched.deleted_at is not None


async def test_soft_delete_included_when_flag_set(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Deleted item"
    )
    saved = await repo.save(item, ws.id)
    await ctx["session"].commit()

    await repo.delete(saved.id, ws.id)
    await ctx["session"].commit()

    page = await repo.list(ws.id, project_id, WorkItemFilters(include_deleted=True))
    assert page.total == 1
    assert page.items[0].deleted_at is not None


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


async def test_record_transition_and_get_desc_ordered(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Transition item"
    )
    await repo.save(item, ws.id)
    await ctx["session"].commit()

    t1 = StateTransition(
        work_item_id=item.id,
        from_state=WorkItemState.DRAFT,
        to_state=WorkItemState.IN_CLARIFICATION,
        actor_id=user.id,
        triggered_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        reason="first",
        is_override=False,
        override_justification=None,
    )
    t2 = StateTransition(
        work_item_id=item.id,
        from_state=WorkItemState.IN_CLARIFICATION,
        to_state=WorkItemState.IN_REVIEW,
        actor_id=user.id,
        triggered_at=datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC),
        reason="second",
        is_override=False,
        override_justification=None,
    )

    await repo.record_transition(t1, ws.id)
    await repo.record_transition(t2, ws.id)
    await ctx["session"].commit()

    transitions = await repo.get_transitions(item.id, ws.id)
    assert len(transitions) == 2
    # DESC order: t2 first
    assert transitions[0].reason == "second"
    assert transitions[1].reason == "first"


async def test_get_transitions_empty(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="No transitions"
    )
    await repo.save(item, ws.id)
    await ctx["session"].commit()

    result = await repo.get_transitions(item.id, ws.id)
    assert result == []


# ---------------------------------------------------------------------------
# Ownership history
# ---------------------------------------------------------------------------


async def test_record_ownership_change_and_get_desc_ordered(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    # Need a second user to reassign to
    new_owner = await _make_user(ctx["session"], sub="wi-new-owner", email="new_owner@acme.io")
    await with_workspace(ctx["session"], ws.id)

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Ownership item"
    )
    await repo.save(item, ws.id)
    await ctx["session"].commit()
    await with_workspace(ctx["session"], ws.id)

    r1 = OwnershipRecord(
        work_item_id=item.id,
        previous_owner_id=user.id,
        new_owner_id=new_owner.id,
        changed_by=user.id,
        changed_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        reason="first transfer",
    )
    r2 = OwnershipRecord(
        work_item_id=item.id,
        previous_owner_id=new_owner.id,
        new_owner_id=user.id,
        changed_by=new_owner.id,
        changed_at=datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC),
        reason="second transfer",
    )

    await repo.record_ownership_change(r1, ws.id, previous_owner_id=user.id)
    await repo.record_ownership_change(r2, ws.id, previous_owner_id=new_owner.id)
    await ctx["session"].commit()
    await with_workspace(ctx["session"], ws.id)

    history = await repo.get_ownership_history(item.id, ws.id)
    assert len(history) == 2
    # DESC order: r2 first
    assert history[0].reason == "second transfer"
    assert history[1].reason == "first transfer"


# ---------------------------------------------------------------------------
# Cross-workspace isolation
# ---------------------------------------------------------------------------


async def test_get_returns_none_for_wrong_workspace(db_session) -> None:
    """save under workspace A, get(id, workspace_id=B) returns None."""
    user_a = await _make_user(db_session, sub="ws-a-user", email="a@wsa.io")
    ws_a = await _make_workspace(db_session, created_by_id=user_a.id, slug_email="a@wsa.io")
    ws_b = await _make_workspace(db_session, created_by_id=user_a.id, slug_email="a@wsb.io")

    await with_workspace(db_session, ws_a.id)
    repo = WorkItemRepositoryImpl(db_session)

    project_id = uuid4()
    item = _make_work_item(
        owner_id=user_a.id, creator_id=user_a.id, project_id=project_id, title="WS-A item"
    )
    saved = await repo.save(item, ws_a.id)
    await db_session.commit()

    await with_workspace(db_session, ws_a.id)
    result = await repo.get(saved.id, ws_b.id)
    assert result is None


# ---------------------------------------------------------------------------
# Append-only trigger
# ---------------------------------------------------------------------------


async def test_state_transitions_append_only_raises_on_update(ctx) -> None:
    """Direct UPDATE on state_transitions raises ProgrammingError / DBAPIError."""
    from sqlalchemy.exc import DBAPIError

    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]
    session = ctx["session"]

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="Trigger item"
    )
    await repo.save(item, ws.id)
    await session.commit()
    await with_workspace(session, ws.id)

    t = StateTransition(
        work_item_id=item.id,
        from_state=WorkItemState.DRAFT,
        to_state=WorkItemState.IN_CLARIFICATION,
        actor_id=user.id,
        triggered_at=datetime.now(UTC),
        reason="initial",
        is_override=False,
        override_justification=None,
    )
    await repo.record_transition(t, ws.id)
    await session.commit()
    await with_workspace(session, ws.id)

    with pytest.raises(DBAPIError):
        await session.execute(
            text("UPDATE state_transitions SET reason = 'hacked' WHERE work_item_id = :id"),
            {"id": str(item.id)},
        )
        await session.flush()


async def test_ownership_history_append_only_raises_on_update(ctx) -> None:
    """Direct UPDATE on ownership_history raises ProgrammingError / DBAPIError."""
    from sqlalchemy.exc import DBAPIError

    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]
    session = ctx["session"]

    new_owner = await _make_user(session, sub="ao-new", email="ao_new@acme.io")
    await with_workspace(session, ws.id)

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="AO trigger item"
    )
    await repo.save(item, ws.id)
    await session.commit()
    await with_workspace(session, ws.id)

    r = OwnershipRecord(
        work_item_id=item.id,
        previous_owner_id=user.id,
        new_owner_id=new_owner.id,
        changed_by=user.id,
        changed_at=datetime.now(UTC),
        reason="initial",
    )
    await repo.record_ownership_change(r, ws.id, previous_owner_id=user.id)
    await session.commit()
    await with_workspace(session, ws.id)

    with pytest.raises(DBAPIError):
        await session.execute(
            text("UPDATE ownership_history SET reason = 'hacked' WHERE work_item_id = :id"),
            {"id": str(item.id)},
        )
        await session.flush()


# ---------------------------------------------------------------------------
# FK violation -> UserNotFoundError
# ---------------------------------------------------------------------------


async def test_save_with_nonexistent_owner_raises_user_not_found(ctx) -> None:
    repo = ctx["repo"]
    ws = ctx["ws"]
    user = ctx["user"]
    project_id = ctx["project_id"]

    ghost_id = uuid4()
    item = _make_work_item(
        owner_id=ghost_id,  # does not exist
        creator_id=user.id,
        project_id=project_id,
        title="Ghost owner item",
    )
    with pytest.raises(UserNotFoundError):
        await repo.save(item, ws.id)
        await ctx["session"].flush()


# ---------------------------------------------------------------------------
# RLS: default-deny without set_config
# ---------------------------------------------------------------------------


async def test_rls_default_deny_without_workspace_context(db_session, rls_session) -> None:
    """Rows exist in work_items but SELECT via wmp_app without set_config returns 0 rows.

    Proves RLS default-denies when app.current_workspace is not set.
    """
    user = await _make_user(db_session, sub="rls-user", email="rls@acme.io")
    ws = await _make_workspace(db_session, created_by_id=user.id, slug_email="rls@acme.io")

    await with_workspace(db_session, ws.id)
    repo = WorkItemRepositoryImpl(db_session)
    project_id = uuid4()

    item = _make_work_item(
        owner_id=user.id, creator_id=user.id, project_id=project_id, title="RLS item"
    )
    await repo.save(item, ws.id)
    await db_session.commit()

    # rls_session connects as wmp_app (NOSUPERUSER) — no set_config called
    result = await rls_session.execute(text("SELECT * FROM work_items"))
    rows = result.fetchall()
    assert rows == [], f"RLS default-deny broken: got {len(rows)} row(s)"
