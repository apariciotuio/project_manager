"""EP-11 — IntegrationConfig + IntegrationExport domain entities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class IntegrationConfig:
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    integration_type: str
    encrypted_credentials: str
    mapping: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        integration_type: str,
        encrypted_credentials: str,
        created_by: UUID,
        project_id: UUID | None = None,
        mapping: dict[str, Any] | None = None,
    ) -> IntegrationConfig:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            integration_type=integration_type,
            encrypted_credentials=encrypted_credentials,
            mapping=mapping or {},
            is_active=True,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.now(UTC)


@dataclass
class IntegrationExport:
    id: UUID
    integration_config_id: UUID
    work_item_id: UUID
    workspace_id: UUID
    external_key: str
    external_url: str | None
    direction: str
    snapshot: dict[str, Any]
    status: str
    error_message: str | None
    exported_at: datetime
    exported_by: UUID

    @classmethod
    def create(
        cls,
        *,
        integration_config_id: UUID,
        work_item_id: UUID,
        workspace_id: UUID,
        external_key: str,
        snapshot: dict[str, Any],
        exported_by: UUID,
        direction: str = "outbound",
        status: str = "pending",
        external_url: str | None = None,
    ) -> IntegrationExport:
        return cls(
            id=uuid4(),
            integration_config_id=integration_config_id,
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            external_key=external_key,
            external_url=external_url,
            direction=direction,
            snapshot=snapshot,
            status=status,
            error_message=None,
            exported_at=datetime.now(UTC),
            exported_by=exported_by,
        )
