"""EP-11 — IntegrationConfig, IntegrationExport repository implementations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.integration import IntegrationConfig, IntegrationExport
from app.domain.repositories.integration_repository import (
    IIntegrationConfigRepository,
    IIntegrationExportRepository,
)
from app.infrastructure.persistence.mappers.integration_mapper import (
    integration_config_to_domain,
    integration_config_to_orm,
    integration_export_to_domain,
    integration_export_to_orm,
)
from app.infrastructure.persistence.models.orm import (
    IntegrationConfigORM,
    IntegrationExportORM,
)


class IntegrationConfigRepositoryImpl(IIntegrationConfigRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, config: IntegrationConfig) -> IntegrationConfig:
        self._session.add(integration_config_to_orm(config))
        await self._session.flush()
        return config

    async def get(self, config_id: UUID) -> IntegrationConfig | None:
        row = await self._session.get(IntegrationConfigORM, config_id)
        return integration_config_to_domain(row) if row else None

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[IntegrationConfig]:
        stmt = (
            select(IntegrationConfigORM)
            .where(
                IntegrationConfigORM.workspace_id == workspace_id,
                IntegrationConfigORM.is_active.is_(True),
            )
            .order_by(IntegrationConfigORM.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [integration_config_to_domain(r) for r in rows]

    async def save(self, config: IntegrationConfig) -> IntegrationConfig:
        existing = await self._session.get(IntegrationConfigORM, config.id)
        if existing is None:
            self._session.add(integration_config_to_orm(config))
        else:
            existing.encrypted_credentials = config.encrypted_credentials
            existing.mapping = config.mapping
            existing.is_active = config.is_active
            existing.updated_at = config.updated_at
        await self._session.flush()
        return config

    async def delete(self, config_id: UUID) -> None:
        row = await self._session.get(IntegrationConfigORM, config_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class IntegrationExportRepositoryImpl(IIntegrationExportRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, export: IntegrationExport) -> IntegrationExport:
        self._session.add(integration_export_to_orm(export))
        await self._session.flush()
        return export

    async def get(self, export_id: UUID) -> IntegrationExport | None:
        row = await self._session.get(IntegrationExportORM, export_id)
        return integration_export_to_domain(row) if row else None

    async def get_by_work_item(self, work_item_id: UUID) -> list[IntegrationExport]:
        stmt = (
            select(IntegrationExportORM)
            .where(IntegrationExportORM.work_item_id == work_item_id)
            .order_by(IntegrationExportORM.exported_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [integration_export_to_domain(r) for r in rows]

    async def get_by_external_key(
        self, external_key: str, integration_config_id: UUID
    ) -> IntegrationExport | None:
        stmt = select(IntegrationExportORM).where(
            IntegrationExportORM.external_key == external_key,
            IntegrationExportORM.integration_config_id == integration_config_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return integration_export_to_domain(row) if row else None
