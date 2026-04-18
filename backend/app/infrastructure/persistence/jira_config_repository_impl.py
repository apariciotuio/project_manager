"""SQLAlchemy impl for IJiraConfigRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.jira_config import JiraConfig, JiraProjectMapping
from app.domain.repositories.jira_config_repository import IJiraConfigRepository
from app.infrastructure.persistence.models.orm import JiraConfigORM, JiraProjectMappingORM


def _config_to_domain(row: JiraConfigORM) -> JiraConfig:
    return JiraConfig(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        base_url=row.base_url,
        auth_type=row.auth_type,  # type: ignore[arg-type]
        credentials_ref=row.credentials_ref,
        state=row.state,  # type: ignore[arg-type]
        last_health_check_status=row.last_health_check_status,  # type: ignore[arg-type]
        last_health_check_at=row.last_health_check_at,
        consecutive_failures=row.consecutive_failures,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _mapping_to_domain(row: JiraProjectMappingORM) -> JiraProjectMapping:
    return JiraProjectMapping(
        id=row.id,
        jira_config_id=row.jira_config_id,
        workspace_id=row.workspace_id,
        jira_project_key=row.jira_project_key,
        local_project_id=row.local_project_id,
        type_mappings=dict(row.type_mappings or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class JiraConfigRepositoryImpl(IJiraConfigRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, config: JiraConfig) -> JiraConfig:
        row = JiraConfigORM(
            id=config.id,
            workspace_id=config.workspace_id,
            project_id=config.project_id,
            base_url=config.base_url,
            auth_type=config.auth_type,
            credentials_ref=config.credentials_ref,
            state=config.state,
            last_health_check_status=config.last_health_check_status,
            last_health_check_at=config.last_health_check_at,
            consecutive_failures=config.consecutive_failures,
            created_by=config.created_by,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _config_to_domain(row)

    async def get_by_id(self, config_id: UUID, workspace_id: UUID) -> JiraConfig | None:
        stmt = select(JiraConfigORM).where(
            JiraConfigORM.id == config_id,
            JiraConfigORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _config_to_domain(row) if row else None

    async def list_for_workspace(self, workspace_id: UUID) -> list[JiraConfig]:
        stmt = (
            select(JiraConfigORM)
            .where(JiraConfigORM.workspace_id == workspace_id)
            .order_by(JiraConfigORM.created_at)
            .limit(100)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_config_to_domain(r) for r in rows]

    async def save(self, config: JiraConfig) -> JiraConfig:
        row = await self._session.get(JiraConfigORM, config.id)
        if row is None:
            return await self.create(config)
        row.base_url = config.base_url
        row.auth_type = config.auth_type
        row.credentials_ref = config.credentials_ref
        row.state = config.state
        row.last_health_check_status = config.last_health_check_status
        row.last_health_check_at = config.last_health_check_at
        row.consecutive_failures = config.consecutive_failures
        row.updated_at = config.updated_at
        await self._session.flush()
        return _config_to_domain(row)

    async def get_active_for_workspace(
        self, workspace_id: UUID, project_id: UUID | None = None
    ) -> JiraConfig | None:
        stmt = select(JiraConfigORM).where(
            JiraConfigORM.workspace_id == workspace_id,
        )
        if project_id is None:
            stmt = stmt.where(JiraConfigORM.project_id.is_(None))
        else:
            stmt = stmt.where(JiraConfigORM.project_id == project_id)
        stmt = stmt.limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _config_to_domain(row) if row else None

    async def create_mapping(self, mapping: JiraProjectMapping) -> JiraProjectMapping:
        row = JiraProjectMappingORM(
            id=mapping.id,
            jira_config_id=mapping.jira_config_id,
            workspace_id=mapping.workspace_id,
            jira_project_key=mapping.jira_project_key,
            local_project_id=mapping.local_project_id,
            type_mappings=mapping.type_mappings,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _mapping_to_domain(row)

    async def get_mapping_by_id(
        self, mapping_id: UUID, workspace_id: UUID
    ) -> JiraProjectMapping | None:
        stmt = select(JiraProjectMappingORM).where(
            JiraProjectMappingORM.id == mapping_id,
            JiraProjectMappingORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _mapping_to_domain(row) if row else None

    async def list_mappings(self, config_id: UUID) -> list[JiraProjectMapping]:
        stmt = (
            select(JiraProjectMappingORM)
            .where(JiraProjectMappingORM.jira_config_id == config_id)
            .order_by(JiraProjectMappingORM.jira_project_key)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_mapping_to_domain(r) for r in rows]

    async def save_mapping(self, mapping: JiraProjectMapping) -> JiraProjectMapping:
        row = await self._session.get(JiraProjectMappingORM, mapping.id)
        if row is None:
            return await self.create_mapping(mapping)
        row.local_project_id = mapping.local_project_id
        row.type_mappings = mapping.type_mappings
        row.updated_at = mapping.updated_at
        await self._session.flush()
        return _mapping_to_domain(row)

    async def delete_mapping(self, mapping_id: UUID, workspace_id: UUID) -> None:
        stmt = select(JiraProjectMappingORM).where(
            JiraProjectMappingORM.id == mapping_id,
            JiraProjectMappingORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row:
            await self._session.delete(row)
            await self._session.flush()
