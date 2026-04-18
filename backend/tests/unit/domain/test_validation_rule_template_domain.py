"""Unit tests for ValidationRuleTemplate domain entity — EP-10 commit 2."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.validation_rule_template import ValidationRuleTemplate


def _make(**kwargs) -> ValidationRuleTemplate:
    defaults = dict(
        name="Review Required",
        requirement_type="reviewer_approval",
        is_mandatory=True,
    )
    defaults.update(kwargs)
    return ValidationRuleTemplate.create(**defaults)


class TestValidationRuleTemplateCreate:
    def test_basic_creation(self) -> None:
        t = _make()
        assert t.name == "Review Required"
        assert t.requirement_type == "reviewer_approval"
        assert t.is_mandatory is True
        assert t.active is True
        assert t.workspace_id is None
        assert t.work_item_type is None

    def test_workspace_scoped(self) -> None:
        ws = uuid4()
        t = _make(workspace_id=ws)
        assert t.workspace_id == ws

    def test_type_specific(self) -> None:
        t = _make(work_item_type="task")
        assert t.work_item_type == "task"

    def test_strips_name(self) -> None:
        t = _make(name="  My Template  ")
        assert t.name == "My Template"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _make(name="   ")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="80"):
            _make(name="x" * 81)

    def test_invalid_requirement_type_raises(self) -> None:
        with pytest.raises(ValueError, match="requirement_type"):
            _make(requirement_type="invalid_type")

    @pytest.mark.parametrize(
        "req_type",
        ["section_content", "reviewer_approval", "validator_approval", "custom"],
    )
    def test_valid_requirement_types(self, req_type: str) -> None:
        t = _make(requirement_type=req_type)
        assert t.requirement_type == req_type

    def test_unique_ids(self) -> None:
        t1 = _make()
        t2 = _make()
        assert t1.id != t2.id

    def test_optional_fields(self) -> None:
        t = _make(default_dimension="quality", default_description="Desc")
        assert t.default_dimension == "quality"
        assert t.default_description == "Desc"

    def test_non_mandatory(self) -> None:
        t = _make(is_mandatory=False)
        assert t.is_mandatory is False


class TestValidationRuleTemplateDeactivate:
    def test_deactivate_sets_inactive(self) -> None:
        t = _make()
        t.deactivate()
        assert t.active is False

    def test_deactivate_updates_timestamp(self) -> None:
        t = _make()
        before = t.updated_at
        t.deactivate()
        assert t.updated_at >= before

    def test_deactivate_idempotent(self) -> None:
        t = _make(active=False)
        t.deactivate()
        assert t.active is False
