"""Unit tests for RoutingRule service operations — EP-10."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.application.services.project_service import (
    ProjectService,
    RoutingRuleNotFoundError,
)
from app.domain.models.project import Project, RoutingRule
from app.domain.repositories.project_repository import (
    IProjectRepository,
    IRoutingRuleRepository,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeProjectRepository(IProjectRepository):
    def __init__(self) -> None:
        self._store: dict[Any, Project] = {}

    async def create(self, project: Project) -> Project:
        self._store[project.id] = project
        return project

    async def get(self, project_id: Any) -> Project | None:
        return self._store.get(project_id)

    async def list_active_for_workspace(self, workspace_id: Any) -> list[Project]:
        return [
            p for p in self._store.values()
            if p.workspace_id == workspace_id and p.deleted_at is None
        ]

    async def save(self, project: Project) -> Project:
        self._store[project.id] = project
        return project


class FakeRoutingRuleRepository(IRoutingRuleRepository):
    def __init__(self) -> None:
        self._store: dict[Any, RoutingRule] = {}

    async def create(self, rule: RoutingRule) -> RoutingRule:
        self._store[rule.id] = rule
        return rule

    async def get(self, rule_id: Any) -> RoutingRule | None:
        return self._store.get(rule_id)

    async def list_for_workspace(self, workspace_id: Any) -> list[RoutingRule]:
        return [r for r in self._store.values() if r.workspace_id == workspace_id]

    async def match(
        self, workspace_id: Any, work_item_type: str, project_id: Any
    ) -> RoutingRule | None:
        candidates = [
            r for r in self._store.values()
            if r.workspace_id == workspace_id
            and r.work_item_type == work_item_type
            and r.active
        ]
        # project-specific first, then workspace-level, ordered by priority
        project_rules = [r for r in candidates if r.project_id == project_id]
        ws_rules = [r for r in candidates if r.project_id is None]
        all_candidates = sorted(
            project_rules or ws_rules, key=lambda r: r.priority, reverse=True
        )
        return all_candidates[0] if all_candidates else None

    async def save(self, rule: RoutingRule) -> RoutingRule:
        self._store[rule.id] = rule
        return rule

    async def delete(self, rule_id: Any) -> None:
        self._store.pop(rule_id, None)


def _make_service() -> ProjectService:
    return ProjectService(
        project_repo=FakeProjectRepository(),
        routing_rule_repo=FakeRoutingRuleRepository(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateRoutingRule:
    @pytest.mark.asyncio
    async def test_create_basic(self) -> None:
        svc = _make_service()
        ws = uuid4()
        rule = await svc.create_routing_rule(
            workspace_id=ws,
            work_item_type="task",
            created_by=uuid4(),
            suggested_team_id=uuid4(),
        )
        assert rule.workspace_id == ws
        assert rule.work_item_type == "task"
        assert rule.active is True

    @pytest.mark.asyncio
    async def test_create_with_priority(self) -> None:
        svc = _make_service()
        rule = await svc.create_routing_rule(
            workspace_id=uuid4(),
            work_item_type="bug",
            created_by=uuid4(),
            priority=5,
        )
        assert rule.priority == 5

    @pytest.mark.asyncio
    async def test_create_with_suggested_validators(self) -> None:
        svc = _make_service()
        validators = [str(uuid4()), str(uuid4())]
        rule = await svc.create_routing_rule(
            workspace_id=uuid4(),
            work_item_type="story",
            created_by=uuid4(),
            suggested_validators=validators,
        )
        assert rule.suggested_validators == validators


class TestGetRoutingRule:
    @pytest.mark.asyncio
    async def test_get_scoped_success(self) -> None:
        svc = _make_service()
        ws = uuid4()
        rule = await svc.create_routing_rule(
            workspace_id=ws, work_item_type="task", created_by=uuid4()
        )
        fetched = await svc.get_routing_rule(rule.id, workspace_id=ws)
        assert fetched.id == rule.id

    @pytest.mark.asyncio
    async def test_get_wrong_workspace_raises(self) -> None:
        svc = _make_service()
        rule = await svc.create_routing_rule(
            workspace_id=uuid4(), work_item_type="task", created_by=uuid4()
        )
        with pytest.raises(RoutingRuleNotFoundError):
            await svc.get_routing_rule(rule.id, workspace_id=uuid4())

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self) -> None:
        svc = _make_service()
        with pytest.raises(RoutingRuleNotFoundError):
            await svc.get_routing_rule(uuid4(), workspace_id=uuid4())


class TestUpdateRoutingRule:
    @pytest.mark.asyncio
    async def test_update_priority(self) -> None:
        svc = _make_service()
        ws = uuid4()
        rule = await svc.create_routing_rule(
            workspace_id=ws, work_item_type="task", created_by=uuid4(), priority=1
        )
        updated = await svc.update_routing_rule(
            rule.id, workspace_id=ws, priority=10
        )
        assert updated.priority == 10

    @pytest.mark.asyncio
    async def test_deactivate_via_update(self) -> None:
        svc = _make_service()
        ws = uuid4()
        rule = await svc.create_routing_rule(
            workspace_id=ws, work_item_type="task", created_by=uuid4()
        )
        updated = await svc.update_routing_rule(rule.id, workspace_id=ws, active=False)
        assert updated.active is False

    @pytest.mark.asyncio
    async def test_update_wrong_workspace_raises(self) -> None:
        svc = _make_service()
        rule = await svc.create_routing_rule(
            workspace_id=uuid4(), work_item_type="task", created_by=uuid4()
        )
        with pytest.raises(RoutingRuleNotFoundError):
            await svc.update_routing_rule(rule.id, workspace_id=uuid4())


class TestDeleteRoutingRule:
    @pytest.mark.asyncio
    async def test_delete_success(self) -> None:
        svc = _make_service()
        ws = uuid4()
        rule = await svc.create_routing_rule(
            workspace_id=ws, work_item_type="task", created_by=uuid4()
        )
        await svc.delete_routing_rule(rule.id, workspace_id=ws)
        with pytest.raises(RoutingRuleNotFoundError):
            await svc.get_routing_rule(rule.id, workspace_id=ws)

    @pytest.mark.asyncio
    async def test_delete_wrong_workspace_raises(self) -> None:
        svc = _make_service()
        rule = await svc.create_routing_rule(
            workspace_id=uuid4(), work_item_type="task", created_by=uuid4()
        )
        with pytest.raises(RoutingRuleNotFoundError):
            await svc.delete_routing_rule(rule.id, workspace_id=uuid4())

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self) -> None:
        svc = _make_service()
        with pytest.raises(RoutingRuleNotFoundError):
            await svc.delete_routing_rule(uuid4(), workspace_id=uuid4())


class TestMatchRouting:
    @pytest.mark.asyncio
    async def test_match_by_type(self) -> None:
        svc = _make_service()
        ws = uuid4()
        team = uuid4()
        await svc.create_routing_rule(
            workspace_id=ws, work_item_type="task", created_by=uuid4(),
            suggested_team_id=team,
        )
        match = await svc.match_routing(ws, "task")
        assert match is not None
        assert match.suggested_team_id == team

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self) -> None:
        svc = _make_service()
        ws = uuid4()
        match = await svc.match_routing(ws, "task")
        assert match is None

    @pytest.mark.asyncio
    async def test_inactive_rule_not_matched(self) -> None:
        svc = _make_service()
        ws = uuid4()
        rule = await svc.create_routing_rule(
            workspace_id=ws, work_item_type="task", created_by=uuid4()
        )
        await svc.update_routing_rule(rule.id, workspace_id=ws, active=False)
        match = await svc.match_routing(ws, "task")
        assert match is None
