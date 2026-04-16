"""EP-11 — IntegrationService (stub; real Jira call deferred)."""
from __future__ import annotations

from uuid import UUID

from app.domain.models.integration import IntegrationConfig, IntegrationExport
from app.domain.repositories.integration_repository import (
    IIntegrationConfigRepository,
    IIntegrationExportRepository,
)


class IntegrationConfigNotFoundError(LookupError):
    pass


class IntegrationService:
    def __init__(
        self,
        *,
        config_repo: IIntegrationConfigRepository,
        export_repo: IIntegrationExportRepository,
    ) -> None:
        self._configs = config_repo
        self._exports = export_repo

    async def create_config(
        self,
        *,
        workspace_id: UUID,
        integration_type: str,
        encrypted_credentials: str,
        created_by: UUID,
        project_id: UUID | None = None,
        mapping: dict | None = None,
    ) -> IntegrationConfig:
        config = IntegrationConfig.create(
            workspace_id=workspace_id,
            integration_type=integration_type,
            encrypted_credentials=encrypted_credentials,
            created_by=created_by,
            project_id=project_id,
            mapping=mapping,
        )
        return await self._configs.create(config)

    async def list_active_configs(self, workspace_id: UUID) -> list[IntegrationConfig]:
        return await self._configs.list_active_for_workspace(workspace_id)

    async def trigger_export(
        self,
        *,
        work_item_id: UUID,
        workspace_id: UUID,
        integration_config_id: UUID,
        snapshot: dict,
        exported_by: UUID,
    ) -> IntegrationExport:
        """Stub — creates an export record with status=pending.

        Real Jira API call is deferred to a background worker.
        """
        config = await self._configs.get(integration_config_id)
        if config is None:
            raise IntegrationConfigNotFoundError(
                f"integration config {integration_config_id} not found"
            )
        export = IntegrationExport.create(
            integration_config_id=integration_config_id,
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            external_key=f"pending-{work_item_id}",
            snapshot=snapshot,
            exported_by=exported_by,
            status="pending",
        )
        return await self._exports.create(export)

    async def list_exports(self, work_item_id: UUID) -> list[IntegrationExport]:
        return await self._exports.get_by_work_item(work_item_id)
