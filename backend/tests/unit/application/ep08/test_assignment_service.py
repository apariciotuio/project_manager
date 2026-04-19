"""EP-08 Group D — Unit tests for AssignmentService (D3.1–D3.4).

RED phase: write failing tests before implementation.

Covers:
- assign_owner: valid user assigned
- assign_owner: suspended user → ValidationError
- assign_owner: user not in workspace → ValidationError
- assign_owner: publishes assignment.changed event
- suggest_owner: routing rule matches → returns suggested_owner_id
- suggest_owner: no matching rule → returns None
- suggest_reviewer: routing rule has team → returns team suggestion
- suggest_reviewer: suspended/deleted user in rule → rule skipped
- bulk_assign: all succeed
- bulk_assign: suspended user → all rejected (422 semantics)
- bulk_assign: some fail validation → partial results with per-item success/error
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeUser:
    id: UUID
    status: str = "active"
    workspace_id: UUID | None = None


class FakeUserRepository:
    def __init__(self) -> None:
        self._users: dict[UUID, FakeUser] = {}

    def add(self, user: FakeUser) -> FakeUser:
        self._users[user.id] = user
        return user

    async def get_by_id(self, user_id: UUID) -> FakeUser | None:
        return self._users.get(user_id)


@dataclass
class FakeWorkItemDomain:
    id: UUID
    workspace_id: UUID
    owner_id: UUID
    state: str = "draft"
    title: str = "test item"
    type: str = "task"


class FakeWorkItemRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, FakeWorkItemDomain] = {}

    def add(self, item: FakeWorkItemDomain) -> FakeWorkItemDomain:
        self._items[item.id] = item
        return item

    async def get(self, item_id: UUID, workspace_id: UUID) -> FakeWorkItemDomain | None:
        item = self._items.get(item_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        return item

    async def save(self, item: FakeWorkItemDomain) -> FakeWorkItemDomain:
        self._items[item.id] = item
        return item


@dataclass
class FakeRoutingRule:
    id: UUID
    workspace_id: UUID
    item_type: str
    suggested_owner_id: UUID | None = None
    suggested_team_id: UUID | None = None


class FakeRoutingRuleRepository:
    def __init__(self) -> None:
        self._rules: list[FakeRoutingRule] = []

    def add(self, rule: FakeRoutingRule) -> FakeRoutingRule:
        self._rules.append(rule)
        return rule

    async def list_for_workspace(self, workspace_id: UUID) -> list[FakeRoutingRule]:
        return [r for r in self._rules if r.workspace_id == workspace_id]


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[Any] = []

    async def emit(self, event: Any) -> None:
        self.published.append(event)


class FakeWorkspaceMembershipRepository:
    def __init__(self) -> None:
        self._memberships: set[tuple[UUID, UUID]] = set()

    def add_member(self, workspace_id: UUID, user_id: UUID) -> None:
        self._memberships.add((workspace_id, user_id))

    async def is_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        return (workspace_id, user_id) in self._memberships


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _workspace_id() -> UUID:
    return uuid4()


def _user(status: str = "active") -> FakeUser:
    return FakeUser(id=uuid4(), status=status)


def _work_item(workspace_id: UUID, owner_id: UUID) -> FakeWorkItemDomain:
    return FakeWorkItemDomain(
        id=uuid4(),
        workspace_id=workspace_id,
        owner_id=owner_id,
    )


def _routing_rule(workspace_id: UUID, item_type: str = "task", *, suggested_owner_id: UUID | None = None, suggested_team_id: UUID | None = None) -> FakeRoutingRule:
    return FakeRoutingRule(
        id=uuid4(),
        workspace_id=workspace_id,
        item_type=item_type,
        suggested_owner_id=suggested_owner_id,
        suggested_team_id=suggested_team_id,
    )


def _make_service(
    user_repo: FakeUserRepository,
    item_repo: FakeWorkItemRepository,
    rule_repo: FakeRoutingRuleRepository,
    membership_repo: FakeWorkspaceMembershipRepository,
    event_bus: FakeEventBus,
):
    from app.application.services.assignment_service import AssignmentService

    return AssignmentService(
        user_repo=user_repo,
        work_item_repo=item_repo,
        routing_rule_repo=rule_repo,
        membership_repo=membership_repo,
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# assign_owner tests
# ---------------------------------------------------------------------------


class TestAssignOwner:
    @pytest.mark.asyncio
    async def test_assign_valid_user_succeeds(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        actor = user_repo.add(_user())
        new_owner = user_repo.add(_user())
        item = item_repo.add(_work_item(ws_id, actor.id))
        membership_repo.add_member(ws_id, new_owner.id)

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        result = await svc.assign_owner(
            item_id=item.id,
            user_id=new_owner.id,
            actor_id=actor.id,
            workspace_id=ws_id,
        )

        assert result.owner_id == new_owner.id

    @pytest.mark.asyncio
    async def test_assign_suspended_user_raises_validation_error(self) -> None:
        from app.application.services.assignment_service import ValidationError

        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        actor = user_repo.add(_user())
        suspended = user_repo.add(_user(status="suspended"))
        item = item_repo.add(_work_item(ws_id, actor.id))

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        with pytest.raises(ValidationError, match="suspended"):
            await svc.assign_owner(
                item_id=item.id,
                user_id=suspended.id,
                actor_id=actor.id,
                workspace_id=ws_id,
            )

    @pytest.mark.asyncio
    async def test_assign_non_workspace_member_raises_validation_error(self) -> None:
        from app.application.services.assignment_service import ValidationError

        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        actor = user_repo.add(_user())
        outsider = user_repo.add(_user())  # active but not workspace member
        item = item_repo.add(_work_item(ws_id, actor.id))
        # outsider is NOT added to membership_repo

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        with pytest.raises(ValidationError, match="workspace"):
            await svc.assign_owner(
                item_id=item.id,
                user_id=outsider.id,
                actor_id=actor.id,
                workspace_id=ws_id,
            )

    @pytest.mark.asyncio
    async def test_assign_owner_publishes_event(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        actor = user_repo.add(_user())
        new_owner = user_repo.add(_user())
        item = item_repo.add(_work_item(ws_id, actor.id))
        membership_repo.add_member(ws_id, new_owner.id)

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        await svc.assign_owner(
            item_id=item.id,
            user_id=new_owner.id,
            actor_id=actor.id,
            workspace_id=ws_id,
        )

        assert len(bus.published) == 1
        event = bus.published[0]
        assert event.new_owner_id == new_owner.id
        assert event.work_item_id == item.id


# ---------------------------------------------------------------------------
# suggest_owner tests
# ---------------------------------------------------------------------------


class TestSuggestOwner:
    @pytest.mark.asyncio
    async def test_suggest_owner_matching_rule_returns_user(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        owner_id = uuid4()
        user_repo.add(FakeUser(id=owner_id, status="active"))
        rule_repo.add(_routing_rule(ws_id, item_type="bug", suggested_owner_id=owner_id))

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        result = await svc.suggest_owner(item_type="bug", workspace_id=ws_id)

        assert result is not None
        assert result["type"] == "user"
        assert result["id"] == owner_id

    @pytest.mark.asyncio
    async def test_suggest_owner_no_matching_rule_returns_none(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        result = await svc.suggest_owner(item_type="task", workspace_id=ws_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_suggest_owner_skips_suspended_user_in_rule(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        suspended_id = uuid4()
        user_repo.add(FakeUser(id=suspended_id, status="suspended"))
        rule_repo.add(_routing_rule(ws_id, item_type="task", suggested_owner_id=suspended_id))

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        result = await svc.suggest_owner(item_type="task", workspace_id=ws_id)

        assert result is None


# ---------------------------------------------------------------------------
# suggest_reviewer tests
# ---------------------------------------------------------------------------


class TestSuggestReviewer:
    @pytest.mark.asyncio
    async def test_suggest_reviewer_team_rule_returns_team(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        team_id = uuid4()
        rule_repo.add(_routing_rule(ws_id, item_type="task", suggested_team_id=team_id))

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        result = await svc.suggest_reviewer(item_type="task", workspace_id=ws_id)

        assert result is not None
        assert result["type"] == "team"
        assert result["id"] == team_id

    @pytest.mark.asyncio
    async def test_suggest_reviewer_no_rule_returns_none(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        result = await svc.suggest_reviewer(item_type="initiative", workspace_id=ws_id)

        assert result is None


# ---------------------------------------------------------------------------
# bulk_assign tests
# ---------------------------------------------------------------------------


class TestBulkAssign:
    @pytest.mark.asyncio
    async def test_bulk_assign_all_succeed(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        actor = user_repo.add(_user())
        new_owner = user_repo.add(_user())
        item1 = item_repo.add(_work_item(ws_id, actor.id))
        item2 = item_repo.add(_work_item(ws_id, actor.id))
        membership_repo.add_member(ws_id, new_owner.id)

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        results = await svc.bulk_assign(
            item_ids=[item1.id, item2.id],
            user_id=new_owner.id,
            actor_id=actor.id,
            workspace_id=ws_id,
        )

        assert len(results) == 2
        for r in results:
            assert r["success"] is True
            assert "error" not in r

    @pytest.mark.asyncio
    async def test_bulk_assign_suspended_user_all_rejected(self) -> None:
        from app.application.services.assignment_service import ValidationError

        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        actor = user_repo.add(_user())
        suspended = user_repo.add(_user(status="suspended"))
        item1 = item_repo.add(_work_item(ws_id, actor.id))
        item2 = item_repo.add(_work_item(ws_id, actor.id))

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        with pytest.raises(ValidationError):
            await svc.bulk_assign(
                item_ids=[item1.id, item2.id],
                user_id=suspended.id,
                actor_id=actor.id,
                workspace_id=ws_id,
            )

    @pytest.mark.asyncio
    async def test_bulk_assign_partial_failure_returns_per_item_results(self) -> None:
        ws_id = _workspace_id()
        user_repo = FakeUserRepository()
        item_repo = FakeWorkItemRepository()
        rule_repo = FakeRoutingRuleRepository()
        membership_repo = FakeWorkspaceMembershipRepository()
        bus = FakeEventBus()

        actor = user_repo.add(_user())
        new_owner = user_repo.add(_user())
        valid_item = item_repo.add(_work_item(ws_id, actor.id))
        missing_item_id = uuid4()  # not in repo
        membership_repo.add_member(ws_id, new_owner.id)

        svc = _make_service(user_repo, item_repo, rule_repo, membership_repo, bus)
        results = await svc.bulk_assign(
            item_ids=[valid_item.id, missing_item_id],
            user_id=new_owner.id,
            actor_id=actor.id,
            workspace_id=ws_id,
        )

        assert len(results) == 2
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        assert len(successes) == 1
        assert len(failures) == 1
        assert "error" in failures[0]
