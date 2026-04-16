"""WorkspaceMembershipRepositoryImpl integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl


@pytest.fixture
def repo(db_session) -> WorkspaceMembershipRepositoryImpl:
    return WorkspaceMembershipRepositoryImpl(db_session)


async def _bootstrap(db_session) -> tuple[User, Workspace]:
    users = UserRepositoryImpl(db_session)
    workspaces = WorkspaceRepositoryImpl(db_session)
    user = User.from_google_claims(
        sub="sub-m", email="m@acme.io", name="M", picture=None
    )
    await users.upsert(user)
    ws = Workspace.create_from_email(email="m@acme.io", created_by=user.id)
    await workspaces.create(ws)
    await db_session.commit()
    return user, ws


async def test_create_and_list(repo, db_session) -> None:
    user, ws = await _bootstrap(db_session)
    m = WorkspaceMembership.create(
        workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
    )
    await repo.create(m)
    await db_session.commit()

    all_for_user = await repo.get_by_user_id(user.id)
    assert len(all_for_user) == 1
    assert all_for_user[0].workspace_id == ws.id
    assert all_for_user[0].role == "admin"


async def test_get_active_filters_suspended(repo, db_session) -> None:
    user, ws = await _bootstrap(db_session)

    active = WorkspaceMembership.create(
        workspace_id=ws.id, user_id=user.id, role="member", is_default=True,
    )
    await repo.create(active)
    await db_session.commit()

    # Simulate a second workspace with a suspended membership
    workspaces = WorkspaceRepositoryImpl(db_session)
    ws2 = Workspace.create_from_email(email="m@other.io", created_by=user.id)
    await workspaces.create(ws2)
    suspended = WorkspaceMembership.create(
        workspace_id=ws2.id, user_id=user.id, role="member", is_default=False,
        state="suspended",
    )
    await repo.create(suspended)
    await db_session.commit()

    active_only = await repo.get_active_by_user_id(user.id)
    assert len(active_only) == 1
    assert active_only[0].workspace_id == ws.id

    all_for_user = await repo.get_by_user_id(user.id)
    assert len(all_for_user) == 2


async def test_get_default(repo, db_session) -> None:
    user, ws = await _bootstrap(db_session)
    default = WorkspaceMembership.create(
        workspace_id=ws.id, user_id=user.id, role="member", is_default=True,
    )
    await repo.create(default)
    await db_session.commit()

    got = await repo.get_default_for_user(user.id)
    assert got is not None
    assert got.workspace_id == ws.id


async def test_get_default_returns_none_when_absent(repo) -> None:
    assert await repo.get_default_for_user(uuid4()) is None


async def test_duplicate_membership_rejected(repo, db_session) -> None:
    user, ws = await _bootstrap(db_session)
    first = WorkspaceMembership.create(
        workspace_id=ws.id, user_id=user.id, role="member", is_default=True,
    )
    await repo.create(first)
    await db_session.commit()

    dup = WorkspaceMembership.create(
        workspace_id=ws.id, user_id=user.id, role="admin", is_default=False,
    )
    with pytest.raises(Exception, match="duplicate key|unique|uq_membership_ws_user"):
        await repo.create(dup)
        await db_session.commit()
