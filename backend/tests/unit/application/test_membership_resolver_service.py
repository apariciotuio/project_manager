"""MembershipResolverService unit tests — 0/1/N routing logic."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.membership_resolver_service import (
    MembershipResolverService,
)
from app.domain.models.workspace_membership import WorkspaceMembership
from tests.fakes.fake_repositories import FakeWorkspaceMembershipRepository


@pytest.fixture
def memberships() -> FakeWorkspaceMembershipRepository:
    return FakeWorkspaceMembershipRepository()


def _membership(*, user_id, workspace_id, state="active", is_default=True) -> WorkspaceMembership:
    return WorkspaceMembership.create(
        workspace_id=workspace_id,
        user_id=user_id,
        role="member",
        is_default=is_default,
        state=state,
    )


async def test_no_memberships_returns_no_access(memberships) -> None:
    service = MembershipResolverService(memberships)
    outcome = await service.resolve(user_id=uuid4())
    assert outcome.kind == "no_access"
    assert outcome.workspace_id is None
    assert outcome.choices == []


async def test_single_active_membership_returns_single(memberships) -> None:
    user_id = uuid4()
    ws_id = uuid4()
    await memberships.create(_membership(user_id=user_id, workspace_id=ws_id))

    service = MembershipResolverService(memberships)
    outcome = await service.resolve(user_id=user_id)

    assert outcome.kind == "single"
    assert outcome.workspace_id == ws_id


async def test_suspended_memberships_are_ignored(memberships) -> None:
    user_id = uuid4()
    await memberships.create(_membership(user_id=user_id, workspace_id=uuid4(), state="suspended"))
    await memberships.create(_membership(user_id=user_id, workspace_id=uuid4(), state="invited"))

    service = MembershipResolverService(memberships)
    outcome = await service.resolve(user_id=user_id)

    assert outcome.kind == "no_access"


async def test_multiple_active_without_last_chosen_returns_picker(memberships) -> None:
    user_id = uuid4()
    ws1, ws2 = uuid4(), uuid4()
    await memberships.create(_membership(user_id=user_id, workspace_id=ws1))
    await memberships.create(_membership(user_id=user_id, workspace_id=ws2, is_default=False))

    service = MembershipResolverService(memberships)
    outcome = await service.resolve(user_id=user_id, last_chosen_workspace_id=None)

    assert outcome.kind == "picker"
    assert outcome.workspace_id is None
    assert {c.workspace_id for c in outcome.choices} == {ws1, ws2}


async def test_multiple_active_with_valid_last_chosen_returns_single(memberships) -> None:
    user_id = uuid4()
    ws1, ws2 = uuid4(), uuid4()
    await memberships.create(_membership(user_id=user_id, workspace_id=ws1))
    await memberships.create(_membership(user_id=user_id, workspace_id=ws2, is_default=False))

    service = MembershipResolverService(memberships)
    outcome = await service.resolve(user_id=user_id, last_chosen_workspace_id=ws2)

    assert outcome.kind == "single"
    assert outcome.workspace_id == ws2


async def test_last_chosen_not_in_active_set_falls_back_to_picker(memberships) -> None:
    user_id = uuid4()
    ws1, ws2 = uuid4(), uuid4()
    ghost = uuid4()  # stale cookie pointing at a workspace the user lost
    await memberships.create(_membership(user_id=user_id, workspace_id=ws1))
    await memberships.create(_membership(user_id=user_id, workspace_id=ws2, is_default=False))

    service = MembershipResolverService(memberships)
    outcome = await service.resolve(user_id=user_id, last_chosen_workspace_id=ghost)

    assert outcome.kind == "picker"
