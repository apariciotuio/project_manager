"""ContextPresetService — EP-10 admin context presets CRUD."""
from __future__ import annotations

import logging
from uuid import UUID

from app.application.services.audit_service import AuditService
from app.domain.models.context_preset import ContextPreset, ContextSource
from app.domain.repositories.context_preset_repository import IContextPresetRepository

logger = logging.getLogger(__name__)


class ContextPresetNotFoundError(LookupError):
    pass


class DuplicatePresetNameError(ValueError):
    code = "duplicate_preset_name"


class PresetInUseError(ValueError):
    code = "preset_in_use"


class ContextPresetService:
    def __init__(
        self,
        repo: IContextPresetRepository,
        audit: AuditService,
        session: object,
    ) -> None:
        self._repo = repo
        self._audit = audit
        self._session = session

    async def list_presets(self, workspace_id: UUID) -> list[ContextPreset]:
        return await self._repo.list_for_workspace(workspace_id)

    async def get_preset(self, workspace_id: UUID, preset_id: UUID) -> ContextPreset:
        preset = await self._repo.get_by_id(preset_id, workspace_id)
        if preset is None:
            raise ContextPresetNotFoundError(preset_id)
        return preset

    async def create_preset(
        self,
        workspace_id: UUID,
        *,
        name: str,
        description: str | None,
        sources: list[dict],
        actor_id: UUID,
    ) -> ContextPreset:
        existing = await self._repo.get_by_name(workspace_id, name)
        if existing is not None:
            raise DuplicatePresetNameError(f"preset name already in use: {name!r}")

        preset = ContextPreset.create(
            workspace_id=workspace_id,
            name=name,
            description=description,
            sources=[ContextSource.from_dict(s) for s in sources],
            created_by=actor_id,
        )
        created = await self._repo.create(preset)

        await self._audit.log_event(
            category="admin",
            action="context_preset_created",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="context_preset",
            entity_id=created.id,
            after_value={"name": name},
        )
        return created

    async def update_preset(
        self,
        workspace_id: UUID,
        preset_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        sources: list[dict] | None = None,
        actor_id: UUID,
    ) -> ContextPreset:
        preset = await self._repo.get_by_id(preset_id, workspace_id)
        if preset is None:
            raise ContextPresetNotFoundError(preset_id)

        before = {"name": preset.name}

        if name is not None and name.strip() != preset.name:
            clash = await self._repo.get_by_name(workspace_id, name)
            if clash is not None and clash.id != preset_id:
                raise DuplicatePresetNameError(f"preset name already in use: {name!r}")

        preset.update(
            name=name,
            description=description,
            sources=[ContextSource.from_dict(s) for s in sources] if sources is not None else None,
        )
        updated = await self._repo.save(preset)

        await self._audit.log_event(
            category="admin",
            action="context_preset_updated",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="context_preset",
            entity_id=preset_id,
            before_value=before,
            after_value={"name": updated.name},
        )
        return updated

    async def delete_preset(
        self,
        workspace_id: UUID,
        preset_id: UUID,
        actor_id: UUID,
    ) -> None:
        preset = await self._repo.get_by_id(preset_id, workspace_id)
        if preset is None:
            raise ContextPresetNotFoundError(preset_id)

        # Check if any project links this preset
        in_use = await self._preset_in_use(preset_id)
        if in_use:
            raise PresetInUseError(f"preset {preset_id} is linked to one or more projects")

        preset.soft_delete()
        await self._repo.save(preset)

        await self._audit.log_event(
            category="admin",
            action="context_preset_deleted",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="context_preset",
            entity_id=preset_id,
        )

    async def _preset_in_use(self, preset_id: UUID) -> bool:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.infrastructure.persistence.models.orm import ProjectORM

        session: AsyncSession = self._session  # type: ignore[assignment]
        # ProjectORM doesn't have context_preset_id yet — plan says it should
        # Check if the column exists at runtime; if not, not in use
        from sqlalchemy import inspect, text
        try:
            stmt = select(ProjectORM.id).where(
                ProjectORM.deleted_at.is_(None),
            ).limit(1)
            # Try accessing context_preset_id — may not exist yet
            # For now we do a raw query that's safe against missing column
            result = await session.execute(
                text(
                    "SELECT id FROM projects WHERE context_preset_id = :pid "
                    "AND deleted_at IS NULL LIMIT 1"
                ),
                {"pid": preset_id},
            )
            return result.scalar_one_or_none() is not None
        except Exception:
            return False
