"""JiraConfigService — EP-10 Jira integration admin CRUD."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.application.services.audit_service import AuditService
from app.domain.models.jira_config import JiraConfig, JiraProjectMapping, _validate_base_url
from app.domain.repositories.jira_config_repository import IJiraConfigRepository

logger = logging.getLogger(__name__)


class JiraConfigNotFoundError(LookupError):
    pass


class JiraConfigExistsError(ValueError):
    code = "jira_config_exists"


class JiraConfigDisabledError(ValueError):
    code = "config_disabled"


class InvalidBaseUrlError(ValueError):
    code = "invalid_base_url"


class JiraConfigService:
    def __init__(
        self,
        repo: IJiraConfigRepository,
        audit: AuditService,
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def list_configs(self, workspace_id: UUID) -> list[JiraConfig]:
        return await self._repo.list_for_workspace(workspace_id)

    async def get_config(self, workspace_id: UUID, config_id: UUID) -> JiraConfig:
        config = await self._repo.get_by_id(config_id, workspace_id)
        if config is None:
            raise JiraConfigNotFoundError(config_id)
        return config

    async def create_config(
        self,
        workspace_id: UUID,
        *,
        base_url: str,
        auth_type: str,
        credentials_ref: str,
        actor_id: UUID,
        project_id: UUID | None = None,
    ) -> JiraConfig:
        try:
            _validate_base_url(base_url)
        except ValueError as exc:
            raise InvalidBaseUrlError(str(exc)) from exc

        # Duplicate check
        existing = await self._repo.get_active_for_workspace(workspace_id, project_id)
        if existing is not None:
            raise JiraConfigExistsError(
                f"jira config already exists for workspace "
                f"{'(workspace-level)' if project_id is None else str(project_id)}"
            )

        config = JiraConfig.create(
            workspace_id=workspace_id,
            base_url=base_url,
            auth_type=auth_type,
            credentials_ref=credentials_ref,
            created_by=actor_id,
            project_id=project_id,
        )
        created = await self._repo.create(config)

        await self._audit.log_event(
            category="admin",
            action="jira_config_created",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="jira_config",
            entity_id=created.id,
            after_value={"base_url": base_url, "auth_type": auth_type},
            # Credentials deliberately excluded from audit
        )
        return created

    async def update_config(
        self,
        workspace_id: UUID,
        config_id: UUID,
        *,
        credentials_ref: str | None = None,
        state: str | None = None,
        actor_id: UUID,
    ) -> JiraConfig:
        config = await self._repo.get_by_id(config_id, workspace_id)
        if config is None:
            raise JiraConfigNotFoundError(config_id)

        before = {"state": config.state}

        if credentials_ref is not None:
            config.update_credentials(credentials_ref)
        if state == "disabled":
            config.disable()
        elif state == "active":
            config.enable()

        updated = await self._repo.save(config)

        await self._audit.log_event(
            category="admin",
            action="jira_config_updated",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="jira_config",
            entity_id=config_id,
            before_value=before,
            after_value={"state": updated.state},
            # credentials_ref intentionally excluded from audit
        )
        return updated

    async def record_health_check(
        self,
        workspace_id: UUID,
        config_id: UUID,
        *,
        status: str,
    ) -> JiraConfig:
        config = await self._repo.get_by_id(config_id, workspace_id)
        if config is None:
            raise JiraConfigNotFoundError(config_id)

        was_error = config.state == "error"
        config.record_health_check(status)  # type: ignore[arg-type]
        updated = await self._repo.save(config)

        if was_error and status == "ok":
            await self._audit.log_event(
                category="admin",
                action="jira_config_recovered",
                workspace_id=workspace_id,
                entity_type="jira_config",
                entity_id=config_id,
            )
        return updated

    async def test_connection(self, workspace_id: UUID, config_id: UUID) -> dict[str, str]:
        """Always returns HTTP 200; result is in body."""
        config = await self._repo.get_by_id(config_id, workspace_id)
        if config is None:
            raise JiraConfigNotFoundError(config_id)
        if config.state == "disabled":
            raise JiraConfigDisabledError(f"config {config_id} is disabled")
        # Actual connectivity test delegated to JiraAdapter (not wired here)
        # Returns test result — caller updates via record_health_check
        return {"status": "ok", "config_id": str(config_id)}

    # Mappings

    async def list_mappings(self, workspace_id: UUID, config_id: UUID) -> list[JiraProjectMapping]:
        await self.get_config(workspace_id, config_id)
        return await self._repo.list_mappings(config_id)

    async def create_mapping(
        self,
        workspace_id: UUID,
        config_id: UUID,
        *,
        jira_project_key: str,
        local_project_id: UUID | None,
        type_mappings: dict[str, Any] | None,
        actor_id: UUID,
    ) -> JiraProjectMapping:
        await self.get_config(workspace_id, config_id)
        mapping = JiraProjectMapping.create(
            jira_config_id=config_id,
            workspace_id=workspace_id,
            jira_project_key=jira_project_key,
            local_project_id=local_project_id,
            type_mappings=type_mappings,
        )
        created = await self._repo.create_mapping(mapping)
        await self._audit.log_event(
            category="admin",
            action="jira_mapping_created",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="jira_project_mapping",
            entity_id=created.id,
            after_value={"jira_project_key": jira_project_key},
        )
        return created
