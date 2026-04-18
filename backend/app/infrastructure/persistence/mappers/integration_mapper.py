"""Mappers for IntegrationConfig, IntegrationExport — EP-11."""

from __future__ import annotations

from app.domain.models.integration import IntegrationConfig, IntegrationExport
from app.infrastructure.persistence.models.orm import (
    IntegrationConfigORM,
    IntegrationExportORM,
)


def integration_config_to_domain(row: IntegrationConfigORM) -> IntegrationConfig:
    return IntegrationConfig(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        integration_type=row.integration_type,
        encrypted_credentials=row.encrypted_credentials,
        mapping=dict(row.mapping),
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by=row.created_by,
    )


def integration_config_to_orm(entity: IntegrationConfig) -> IntegrationConfigORM:
    row = IntegrationConfigORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.project_id = entity.project_id
    row.integration_type = entity.integration_type
    row.encrypted_credentials = entity.encrypted_credentials
    row.mapping = entity.mapping
    row.is_active = entity.is_active
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.created_by = entity.created_by
    return row


def integration_export_to_domain(row: IntegrationExportORM) -> IntegrationExport:
    return IntegrationExport(
        id=row.id,
        integration_config_id=row.integration_config_id,
        work_item_id=row.work_item_id,
        workspace_id=row.workspace_id,
        external_key=row.external_key,
        external_url=row.external_url,
        direction=row.direction,
        snapshot=dict(row.snapshot),
        status=row.status,
        error_message=row.error_message,
        exported_at=row.exported_at,
        exported_by=row.exported_by,
    )


def integration_export_to_orm(entity: IntegrationExport) -> IntegrationExportORM:
    row = IntegrationExportORM()
    row.id = entity.id
    row.integration_config_id = entity.integration_config_id
    row.work_item_id = entity.work_item_id
    row.workspace_id = entity.workspace_id
    row.external_key = entity.external_key
    row.external_url = entity.external_url
    row.direction = entity.direction
    row.snapshot = entity.snapshot
    row.status = entity.status
    row.error_message = entity.error_message
    row.exported_at = entity.exported_at
    row.exported_by = entity.exported_by
    return row
