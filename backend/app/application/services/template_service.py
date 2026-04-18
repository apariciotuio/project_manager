"""TemplateService — CRUD with Redis caching and admin authz enforcement — EP-02."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.exceptions import (
    TemplateForbiddenError,
    TemplateNotFoundError,
)
from app.domain.models.template import Template
from app.domain.ports.cache import ICache
from app.domain.repositories.template_repository import ITemplateRepository
from app.domain.value_objects.work_item_type import WorkItemType

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes


def _cache_key_workspace(workspace_id: UUID, type: WorkItemType) -> str:
    return f"template:{workspace_id}:{type.value}"


def _cache_key_system(type: WorkItemType) -> str:
    return f"template:system:{type.value}"


def _serialize(template: Template) -> str:
    return json.dumps(
        {
            "id": str(template.id),
            "workspace_id": str(template.workspace_id) if template.workspace_id else None,
            "type": template.type.value,
            "name": template.name,
            "content": template.content,
            "is_system": template.is_system,
            "created_by": str(template.created_by) if template.created_by else None,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat(),
        }
    )


def _deserialize(raw: str) -> Template:
    data = json.loads(raw)
    return Template(
        id=UUID(data["id"]),
        workspace_id=UUID(data["workspace_id"]) if data["workspace_id"] else None,
        type=WorkItemType(data["type"]),
        name=data["name"],
        content=data["content"],
        is_system=data["is_system"],
        created_by=UUID(data["created_by"]) if data["created_by"] else None,
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


class TemplateService:
    def __init__(
        self,
        *,
        template_repo: ITemplateRepository,
        cache: ICache,
    ) -> None:
        self._repo = template_repo
        self._cache = cache

    async def list_for_workspace(self, workspace_id: UUID) -> list[Template]:
        return await self._repo.list_for_workspace(workspace_id)

    async def get_template_for_type(
        self, type: WorkItemType, workspace_id: UUID
    ) -> Template | None:
        """Return workspace template; fall back to system default; cache both."""
        # Try workspace cache first
        ws_key = _cache_key_workspace(workspace_id, type)
        cached = await self._cache.get(ws_key)
        if cached is not None:
            return _deserialize(cached)

        # DB lookup: workspace first
        tmpl = await self._repo.get_by_workspace_and_type(workspace_id, type)
        if tmpl is not None:
            await self._cache.set(ws_key, _serialize(tmpl), _CACHE_TTL)
            return tmpl

        # Fall back to system default
        sys_key = _cache_key_system(type)
        cached_sys = await self._cache.get(sys_key)
        if cached_sys is not None:
            return _deserialize(cached_sys)

        sys_tmpl = await self._repo.get_system_default(type)
        if sys_tmpl is not None:
            await self._cache.set(sys_key, _serialize(sys_tmpl), _CACHE_TTL)
        return sys_tmpl

    async def create_template(
        self,
        *,
        workspace_id: UUID,
        type: WorkItemType,
        name: str,
        content: str,
        actor_id: UUID,
        actor_role: str,
    ) -> Template:
        if actor_role != "admin":
            raise TemplateForbiddenError("only workspace admins can create templates")

        # Domain invariant will raise ValueError for content > 50000 chars
        tmpl = Template(
            id=uuid4(),
            workspace_id=workspace_id,
            type=type,
            name=name,
            content=content,
            is_system=False,
            created_by=actor_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        result = await self._repo.create(tmpl)
        await self._cache.delete(_cache_key_workspace(workspace_id, type))
        logger.info("template_created workspace=%s type=%s actor=%s", workspace_id, type, actor_id)
        return result

    async def update_template(
        self,
        *,
        template_id: UUID,
        name: str | None,
        content: str | None,
        actor_id: UUID,
        actor_role: str,
    ) -> Template:
        existing = await self._repo.get_by_id(template_id)
        if existing is None:
            raise TemplateNotFoundError(template_id)

        if existing.is_system:
            raise TemplateForbiddenError("system templates are immutable")
        if actor_role != "admin":
            raise TemplateForbiddenError("only workspace admins can update templates")

        if content is not None and len(content) > 50000:
            raise ValueError(
                f"content exceeds maximum length of 50000 characters; got {len(content)}"
            )

        updated = await self._repo.update(template_id, name=name, content=content)
        # Invalidate cache
        if existing.workspace_id is not None:
            await self._cache.delete(_cache_key_workspace(existing.workspace_id, existing.type))
        else:
            await self._cache.delete(_cache_key_system(existing.type))
        logger.info("template_updated id=%s actor=%s", template_id, actor_id)
        return updated

    async def delete_template(
        self,
        *,
        template_id: UUID,
        actor_id: UUID,
        actor_role: str,
    ) -> None:
        existing = await self._repo.get_by_id(template_id)
        if existing is None:
            raise TemplateNotFoundError(template_id)

        if existing.is_system:
            raise TemplateForbiddenError("system templates cannot be deleted")
        if actor_role != "admin":
            raise TemplateForbiddenError("only workspace admins can delete templates")

        await self._repo.delete(template_id)
        if existing.workspace_id is not None:
            await self._cache.delete(_cache_key_workspace(existing.workspace_id, existing.type))
        logger.info("template_deleted id=%s actor=%s", template_id, actor_id)
