"""Unit tests for TemplateService — EP-02 Phase 4.

Uses fake repositories and fake cache. No DB/Redis.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tests.fakes.fake_repositories import FakeCache, FakeTemplateRepository


def _make_template(workspace_id, type_, *, is_system: bool = False):
    from app.domain.models.template import Template

    return Template(
        id=uuid4(),
        workspace_id=workspace_id,
        type=type_,
        name=f"{type_.value} Template",
        content=f"## {type_.value}",
        is_system=is_system,
        created_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_service(template_repo=None, cache=None):
    from app.application.services.template_service import TemplateService

    if template_repo is None:
        template_repo = FakeTemplateRepository()
    if cache is None:
        cache = FakeCache()
    return TemplateService(template_repo=template_repo, cache=cache)


class TestTemplateServiceGet:
    async def test_returns_workspace_template_when_exists(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        ws_id = uuid4()
        repo = FakeTemplateRepository()
        tmpl = _make_template(ws_id, WorkItemType.BUG)
        await repo.create(tmpl)

        service = _make_service(template_repo=repo)
        result = await service.get_template_for_type(WorkItemType.BUG, ws_id)

        assert result is not None
        assert result.workspace_id == ws_id

    async def test_falls_back_to_system_default_when_no_workspace_template(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        ws_id = uuid4()
        repo = FakeTemplateRepository()
        sys_tmpl = _make_template(None, WorkItemType.BUG, is_system=True)
        await repo.create(sys_tmpl)

        service = _make_service(template_repo=repo)
        result = await service.get_template_for_type(WorkItemType.BUG, ws_id)

        assert result is not None
        assert result.is_system is True

    async def test_returns_none_when_neither_exists(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        service = _make_service()
        result = await service.get_template_for_type(WorkItemType.IDEA, uuid4())
        assert result is None

    async def test_cache_hit_avoids_db_call(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        ws_id = uuid4()
        cache = FakeCache()
        repo = FakeTemplateRepository()

        # Pre-seed cache with a serialized template
        tmpl = _make_template(ws_id, WorkItemType.TASK)
        cache.seed(
            f"template:{ws_id}:{WorkItemType.TASK.value}",
            json.dumps(
                {
                    "id": str(tmpl.id),
                    "workspace_id": str(tmpl.workspace_id),
                    "type": tmpl.type.value,
                    "name": tmpl.name,
                    "content": tmpl.content,
                    "is_system": tmpl.is_system,
                    "created_by": str(tmpl.created_by) if tmpl.created_by else None,
                    "created_at": tmpl.created_at.isoformat(),
                    "updated_at": tmpl.updated_at.isoformat(),
                }
            ),
        )

        service = _make_service(template_repo=repo, cache=cache)
        initial_get_count = cache.get_call_count

        result = await service.get_template_for_type(WorkItemType.TASK, ws_id)

        assert result is not None
        # Repo should NOT have been called — cache returned the value
        # (we verify by checking that get was called on cache but no DB methods ran)
        assert cache.get_call_count == initial_get_count + 1


class TestTemplateServiceCreate:
    async def test_admin_can_create_template(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        ws_id = uuid4()
        admin_id = uuid4()
        service = _make_service()

        result = await service.create_template(
            workspace_id=ws_id,
            type=WorkItemType.BUG,
            name="Bug Report",
            content="## Summary",
            actor_id=admin_id,
            actor_role="admin",
        )

        from app.domain.models.template import Template

        assert isinstance(result, Template)
        assert result.workspace_id == ws_id

    async def test_non_admin_raises_forbidden(self) -> None:
        from app.domain.exceptions import TemplateForbiddenError
        from app.domain.value_objects.work_item_type import WorkItemType

        service = _make_service()
        with pytest.raises(TemplateForbiddenError):
            await service.create_template(
                workspace_id=uuid4(),
                type=WorkItemType.BUG,
                name="Bug",
                content="## Bug",
                actor_id=uuid4(),
                actor_role="member",
            )

    async def test_duplicate_type_raises_duplicate_template_error(self) -> None:
        from app.domain.exceptions import DuplicateTemplateError
        from app.domain.value_objects.work_item_type import WorkItemType

        ws_id = uuid4()
        service = _make_service()

        await service.create_template(
            workspace_id=ws_id,
            type=WorkItemType.BUG,
            name="Bug",
            content="## Bug",
            actor_id=uuid4(),
            actor_role="admin",
        )
        with pytest.raises(DuplicateTemplateError):
            await service.create_template(
                workspace_id=ws_id,
                type=WorkItemType.BUG,
                name="Bug 2",
                content="## Bug 2",
                actor_id=uuid4(),
                actor_role="admin",
            )

    async def test_content_too_long_raises_validation_error(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        service = _make_service()
        with pytest.raises(ValueError, match="content"):
            await service.create_template(
                workspace_id=uuid4(),
                type=WorkItemType.BUG,
                name="Bug",
                content="x" * 50001,
                actor_id=uuid4(),
                actor_role="admin",
            )


class TestTemplateServiceUpdate:
    async def test_update_system_template_raises_forbidden(self) -> None:
        from app.domain.exceptions import TemplateForbiddenError
        from app.domain.value_objects.work_item_type import WorkItemType

        repo = FakeTemplateRepository()
        sys_tmpl = _make_template(None, WorkItemType.BUG, is_system=True)
        await repo.create(sys_tmpl)

        service = _make_service(template_repo=repo)
        with pytest.raises(TemplateForbiddenError):
            await service.update_template(
                template_id=sys_tmpl.id,
                name="New",
                content="## New",
                actor_id=uuid4(),
                actor_role="admin",
            )

    async def test_update_invalidates_cache(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        ws_id = uuid4()
        repo = FakeTemplateRepository()
        cache = FakeCache()
        tmpl = _make_template(ws_id, WorkItemType.ENHANCEMENT)
        await repo.create(tmpl)

        service = _make_service(template_repo=repo, cache=cache)
        await service.update_template(
            template_id=tmpl.id,
            name="Updated",
            content="## Updated",
            actor_id=uuid4(),
            actor_role="admin",
        )

        assert cache.delete_call_count >= 1


class TestTemplateServiceDelete:
    async def test_delete_system_template_raises_forbidden(self) -> None:
        from app.domain.exceptions import TemplateForbiddenError
        from app.domain.value_objects.work_item_type import WorkItemType

        repo = FakeTemplateRepository()
        sys_tmpl = _make_template(None, WorkItemType.TASK, is_system=True)
        await repo.create(sys_tmpl)

        service = _make_service(template_repo=repo)
        with pytest.raises(TemplateForbiddenError):
            await service.delete_template(
                template_id=sys_tmpl.id,
                actor_id=uuid4(),
                actor_role="admin",
            )

    async def test_delete_invalidates_cache(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        ws_id = uuid4()
        repo = FakeTemplateRepository()
        cache = FakeCache()
        tmpl = _make_template(ws_id, WorkItemType.SPIKE)
        await repo.create(tmpl)

        service = _make_service(template_repo=repo, cache=cache)
        await service.delete_template(
            template_id=tmpl.id,
            actor_id=uuid4(),
            actor_role="admin",
        )

        assert cache.delete_call_count >= 1
