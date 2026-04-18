"""SQLAlchemy impl for IContextPresetRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.context_preset import ContextPreset, ContextSource
from app.domain.repositories.context_preset_repository import IContextPresetRepository
from app.infrastructure.persistence.models.orm import ContextPresetORM


def _to_domain(row: ContextPresetORM) -> ContextPreset:
    sources = [ContextSource.from_dict(s) for s in (row.sources or [])]
    return ContextPreset(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        sources=sources,
        deleted_at=row.deleted_at,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ContextPresetRepositoryImpl(IContextPresetRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, preset: ContextPreset) -> ContextPreset:
        row = ContextPresetORM(
            id=preset.id,
            workspace_id=preset.workspace_id,
            name=preset.name,
            description=preset.description,
            sources=[s.to_dict() for s in preset.sources],
            deleted_at=preset.deleted_at,
            created_by=preset.created_by,
            created_at=preset.created_at,
            updated_at=preset.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_id(self, preset_id: UUID, workspace_id: UUID) -> ContextPreset | None:
        stmt = select(ContextPresetORM).where(
            ContextPresetORM.id == preset_id,
            ContextPresetORM.workspace_id == workspace_id,
            ContextPresetORM.deleted_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def list_for_workspace(self, workspace_id: UUID) -> list[ContextPreset]:
        stmt = (
            select(ContextPresetORM)
            .where(
                ContextPresetORM.workspace_id == workspace_id,
                ContextPresetORM.deleted_at.is_(None),
            )
            .order_by(ContextPresetORM.name)
            .limit(500)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def save(self, preset: ContextPreset) -> ContextPreset:
        row = await self._session.get(ContextPresetORM, preset.id)
        if row is None:
            return await self.create(preset)
        row.name = preset.name
        row.description = preset.description
        row.sources = [s.to_dict() for s in preset.sources]
        row.deleted_at = preset.deleted_at
        row.updated_at = preset.updated_at
        await self._session.flush()
        return _to_domain(row)

    async def get_by_name(self, workspace_id: UUID, name: str) -> ContextPreset | None:
        stmt = select(ContextPresetORM).where(
            ContextPresetORM.workspace_id == workspace_id,
            ContextPresetORM.name == name.strip(),
            ContextPresetORM.deleted_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None
