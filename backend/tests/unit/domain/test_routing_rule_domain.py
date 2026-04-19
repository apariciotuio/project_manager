"""Unit tests for RoutingRule domain entity — EP-10 commit 1."""
from __future__ import annotations

from uuid import uuid4

from app.domain.models.project import RoutingRule


def _make_rule(**kwargs) -> RoutingRule:
    defaults = dict(
        workspace_id=uuid4(),
        work_item_type="task",
        created_by=uuid4(),
    )
    defaults.update(kwargs)
    return RoutingRule.create(**defaults)


class TestRoutingRuleCreate:
    def test_default_active_true(self) -> None:
        rule = _make_rule()
        assert rule.active is True

    def test_explicit_inactive(self) -> None:
        rule = _make_rule(active=False)
        assert rule.active is False

    def test_default_priority_zero(self) -> None:
        rule = _make_rule()
        assert rule.priority == 0

    def test_custom_priority(self) -> None:
        rule = _make_rule(priority=10)
        assert rule.priority == 10

    def test_suggested_validators_empty_by_default(self) -> None:
        rule = _make_rule()
        assert rule.suggested_validators == []

    def test_suggested_validators_set(self) -> None:
        uid = uuid4()
        rule = _make_rule(suggested_validators=[str(uid)])
        assert rule.suggested_validators == [str(uid)]

    def test_project_id_optional(self) -> None:
        rule = _make_rule()
        assert rule.project_id is None

        rule2 = _make_rule(project_id=uuid4())
        assert rule2.project_id is not None

    def test_ids_generated(self) -> None:
        r1 = _make_rule()
        r2 = _make_rule()
        assert r1.id != r2.id


class TestRoutingRuleDeactivate:
    def test_deactivate_sets_active_false(self) -> None:
        rule = _make_rule()
        rule.deactivate()
        assert rule.active is False

    def test_deactivate_updates_timestamp(self) -> None:
        rule = _make_rule()
        before = rule.updated_at
        rule.deactivate()
        assert rule.updated_at >= before

    def test_deactivate_already_inactive_idempotent(self) -> None:
        rule = _make_rule(active=False)
        rule.deactivate()
        assert rule.active is False
