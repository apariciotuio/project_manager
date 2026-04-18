"""Unit tests for ValidationRuleTemplateService — EP-10."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.application.services.validation_rule_template_service import (
    ValidationRuleTemplateNotFoundError,
    ValidationRuleTemplateService,
)
from app.domain.models.validation_rule_template import ValidationRuleTemplate
from app.domain.repositories.validation_rule_template_repository import (
    IValidationRuleTemplateRepository,
)

# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------


class FakeVRTRepository(IValidationRuleTemplateRepository):
    def __init__(self) -> None:
        self._store: dict[Any, ValidationRuleTemplate] = {}

    async def create(self, template: ValidationRuleTemplate) -> ValidationRuleTemplate:
        self._store[template.id] = template
        return template

    async def get(self, template_id: Any) -> ValidationRuleTemplate | None:
        return self._store.get(template_id)

    async def list_for_workspace(self, workspace_id: Any) -> list[ValidationRuleTemplate]:
        return [t for t in self._store.values() if t.workspace_id == workspace_id and t.active]

    async def list_matching(
        self, *, workspace_id: Any, work_item_type: str | None
    ) -> list[ValidationRuleTemplate]:
        result = []
        for t in self._store.values():
            if not t.active:
                continue
            if t.workspace_id not in (workspace_id, None):
                continue
            if work_item_type is not None:
                if t.work_item_type not in (work_item_type, None):
                    continue
            result.append(t)
        return sorted(result, key=lambda x: (-x.is_mandatory, x.name))

    async def save(self, template: ValidationRuleTemplate) -> ValidationRuleTemplate:
        self._store[template.id] = template
        return template

    async def delete(self, template_id: Any) -> None:
        self._store.pop(template_id, None)


def _make_svc() -> ValidationRuleTemplateService:
    return ValidationRuleTemplateService(repo=FakeVRTRepository())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_workspace_template(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        t = await svc.create(
            name="My Template",
            requirement_type="reviewer_approval",
            is_mandatory=True,
            workspace_id=ws,
        )
        assert t.name == "My Template"
        assert t.workspace_id == ws
        assert t.active is True

    @pytest.mark.asyncio
    async def test_create_global_template(self) -> None:
        svc = _make_svc()
        t = await svc.create(
            name="Global",
            requirement_type="section_content",
            is_mandatory=False,
        )
        assert t.workspace_id is None

    @pytest.mark.asyncio
    async def test_create_invalid_type_raises(self) -> None:
        svc = _make_svc()
        with pytest.raises(ValueError):
            await svc.create(
                name="Bad",
                requirement_type="nonexistent",
                is_mandatory=True,
            )


class TestGet:
    @pytest.mark.asyncio
    async def test_get_own_workspace_template(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        t = await svc.create(
            name="T", requirement_type="custom", is_mandatory=False, workspace_id=ws
        )
        fetched = await svc.get(t.id, workspace_id=ws)
        assert fetched.id == t.id

    @pytest.mark.asyncio
    async def test_get_global_accessible_by_any_workspace(self) -> None:
        svc = _make_svc()
        t = await svc.create(name="Global", requirement_type="custom", is_mandatory=False)
        # Any workspace can access global templates
        fetched = await svc.get(t.id, workspace_id=uuid4())
        assert fetched.id == t.id

    @pytest.mark.asyncio
    async def test_get_other_workspace_raises(self) -> None:
        svc = _make_svc()
        t = await svc.create(
            name="T", requirement_type="custom", is_mandatory=False, workspace_id=uuid4()
        )
        with pytest.raises(ValidationRuleTemplateNotFoundError):
            await svc.get(t.id, workspace_id=uuid4())

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self) -> None:
        svc = _make_svc()
        with pytest.raises(ValidationRuleTemplateNotFoundError):
            await svc.get(uuid4(), workspace_id=uuid4())


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_name(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        t = await svc.create(
            name="Old", requirement_type="custom", is_mandatory=False, workspace_id=ws
        )
        updated = await svc.update(t.id, workspace_id=ws, name="New")
        assert updated.name == "New"

    @pytest.mark.asyncio
    async def test_update_deactivate(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        t = await svc.create(
            name="T", requirement_type="custom", is_mandatory=True, workspace_id=ws
        )
        updated = await svc.update(t.id, workspace_id=ws, active=False)
        assert updated.active is False

    @pytest.mark.asyncio
    async def test_update_empty_name_raises(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        t = await svc.create(
            name="T", requirement_type="custom", is_mandatory=True, workspace_id=ws
        )
        with pytest.raises(ValueError):
            await svc.update(t.id, workspace_id=ws, name="  ")

    @pytest.mark.asyncio
    async def test_update_wrong_workspace_raises(self) -> None:
        svc = _make_svc()
        t = await svc.create(
            name="T", requirement_type="custom", is_mandatory=True, workspace_id=uuid4()
        )
        with pytest.raises(ValidationRuleTemplateNotFoundError):
            await svc.update(t.id, workspace_id=uuid4(), name="New")


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_success(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        t = await svc.create(
            name="T", requirement_type="custom", is_mandatory=False, workspace_id=ws
        )
        await svc.delete(t.id, workspace_id=ws)
        with pytest.raises(ValidationRuleTemplateNotFoundError):
            await svc.get(t.id, workspace_id=ws)

    @pytest.mark.asyncio
    async def test_delete_wrong_workspace_raises(self) -> None:
        svc = _make_svc()
        t = await svc.create(
            name="T", requirement_type="custom", is_mandatory=False, workspace_id=uuid4()
        )
        with pytest.raises(ValidationRuleTemplateNotFoundError):
            await svc.delete(t.id, workspace_id=uuid4())


class TestSeedForWorkItem:
    @pytest.mark.asyncio
    async def test_seed_returns_matching_templates(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        await svc.create(
            name="Task Review",
            requirement_type="reviewer_approval",
            is_mandatory=True,
            workspace_id=ws,
            work_item_type="task",
        )
        await svc.create(
            name="Bug Content",
            requirement_type="section_content",
            is_mandatory=False,
            workspace_id=ws,
            work_item_type="bug",
        )
        matching = await svc.seed_for_work_item(ws, "task")
        assert len(matching) == 1
        assert matching[0].name == "Task Review"

    @pytest.mark.asyncio
    async def test_seed_type_agnostic_template_included(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        await svc.create(
            name="Universal",
            requirement_type="custom",
            is_mandatory=False,
            workspace_id=ws,
            work_item_type=None,  # matches all types
        )
        matching = await svc.seed_for_work_item(ws, "task")
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_seed_no_match_returns_empty(self) -> None:
        svc = _make_svc()
        ws = uuid4()
        matching = await svc.seed_for_work_item(ws, "milestone")
        assert matching == []
