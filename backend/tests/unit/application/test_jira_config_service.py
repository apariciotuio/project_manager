"""Unit tests for JiraConfigService — EP-10 Jira integration."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.services.jira_config_service import (
    InvalidBaseUrlError,
    JiraConfigDisabledError,
    JiraConfigExistsError,
    JiraConfigNotFoundError,
    JiraConfigService,
)
from app.domain.models.jira_config import JiraConfig, JiraProjectMapping
from app.domain.repositories.jira_config_repository import IJiraConfigRepository

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeJiraConfigRepo(IJiraConfigRepository):
    def __init__(self) -> None:
        self._configs: dict[UUID, JiraConfig] = {}
        self._mappings: dict[UUID, JiraProjectMapping] = {}

    async def create(self, config: JiraConfig) -> JiraConfig:
        self._configs[config.id] = config
        return config

    async def get_by_id(self, config_id: UUID, workspace_id: UUID) -> JiraConfig | None:
        c = self._configs.get(config_id)
        return c if c and c.workspace_id == workspace_id else None

    async def list_for_workspace(self, workspace_id: UUID) -> list[JiraConfig]:
        return [c for c in self._configs.values() if c.workspace_id == workspace_id]

    async def save(self, config: JiraConfig) -> JiraConfig:
        self._configs[config.id] = config
        return config

    async def get_active_for_workspace(
        self, workspace_id: UUID, project_id: UUID | None = None
    ) -> JiraConfig | None:
        return next(
            (c for c in self._configs.values()
             if c.workspace_id == workspace_id and c.project_id == project_id),
            None,
        )

    async def create_mapping(self, mapping: JiraProjectMapping) -> JiraProjectMapping:
        self._mappings[mapping.id] = mapping
        return mapping

    async def get_mapping_by_id(self, mapping_id: UUID, workspace_id: UUID) -> JiraProjectMapping | None:
        m = self._mappings.get(mapping_id)
        return m if m and m.workspace_id == workspace_id else None

    async def list_mappings(self, config_id: UUID) -> list[JiraProjectMapping]:
        return [m for m in self._mappings.values() if m.jira_config_id == config_id]

    async def save_mapping(self, mapping: JiraProjectMapping) -> JiraProjectMapping:
        self._mappings[mapping.id] = mapping
        return mapping

    async def delete_mapping(self, mapping_id: UUID, workspace_id: UUID) -> None:
        self._mappings.pop(mapping_id, None)


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log_event(self, **kwargs: object) -> None:
        self.events.append(kwargs)


_WS_ID = uuid4()
_ACTOR_ID = uuid4()


def _make_service() -> tuple[JiraConfigService, FakeJiraConfigRepo, FakeAudit]:
    repo = FakeJiraConfigRepo()
    audit = FakeAudit()
    svc = JiraConfigService(repo=repo, audit=audit)  # type: ignore[arg-type]
    return svc, repo, audit


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJiraConfigCreate:
    @pytest.mark.asyncio
    async def test_create_success_returns_config_without_credentials(self) -> None:
        svc, repo, audit = _make_service()

        config = await svc.create_config(
            _WS_ID,
            base_url="https://jira.example.com",
            auth_type="basic",
            credentials_ref="ENCRYPTED_TOKEN",
            actor_id=_ACTOR_ID,
        )

        assert config.state == "active"
        assert config.base_url == "https://jira.example.com"
        # credentials_ref stored, but audit must not contain it
        assert config.credentials_ref == "ENCRYPTED_TOKEN"
        assert any(e["action"] == "jira_config_created" for e in audit.events)
        audit_event = next(e for e in audit.events if e["action"] == "jira_config_created")
        assert "credentials_ref" not in str(audit_event.get("after_value", {}))

    @pytest.mark.asyncio
    async def test_create_http_url_raises_invalid_base_url(self) -> None:
        svc, _, _ = _make_service()
        with pytest.raises(InvalidBaseUrlError):
            await svc.create_config(
                _WS_ID,
                base_url="http://jira.example.com",
                auth_type="basic",
                credentials_ref="TOKEN",
                actor_id=_ACTOR_ID,
            )

    @pytest.mark.asyncio
    async def test_create_duplicate_workspace_config_raises_409(self) -> None:
        svc, repo, _ = _make_service()
        await svc.create_config(
            _WS_ID, base_url="https://jira.example.com",
            auth_type="basic", credentials_ref="T1", actor_id=_ACTOR_ID
        )
        with pytest.raises(JiraConfigExistsError):
            await svc.create_config(
                _WS_ID, base_url="https://jira2.example.com",
                auth_type="basic", credentials_ref="T2", actor_id=_ACTOR_ID
            )


class TestJiraConfigHealthCheck:
    @pytest.mark.asyncio
    async def test_three_failures_transitions_to_error(self) -> None:
        svc, repo, audit = _make_service()
        config = await svc.create_config(
            _WS_ID, base_url="https://jira.example.com",
            auth_type="basic", credentials_ref="T", actor_id=_ACTOR_ID
        )

        for _ in range(3):
            await svc.record_health_check(_WS_ID, config.id, status="auth_failure")

        updated = await svc.get_config(_WS_ID, config.id)
        assert updated.state == "error"

    @pytest.mark.asyncio
    async def test_recovery_from_error_state(self) -> None:
        svc, repo, audit = _make_service()
        config = await svc.create_config(
            _WS_ID, base_url="https://jira.example.com",
            auth_type="basic", credentials_ref="T", actor_id=_ACTOR_ID
        )
        for _ in range(3):
            await svc.record_health_check(_WS_ID, config.id, status="auth_failure")

        await svc.record_health_check(_WS_ID, config.id, status="ok")

        updated = await svc.get_config(_WS_ID, config.id)
        assert updated.state == "active"
        assert any(e["action"] == "jira_config_recovered" for e in audit.events)

    @pytest.mark.asyncio
    async def test_test_connection_disabled_raises_409(self) -> None:
        svc, _, _ = _make_service()
        config = await svc.create_config(
            _WS_ID, base_url="https://jira.example.com",
            auth_type="basic", credentials_ref="T", actor_id=_ACTOR_ID
        )
        await svc.update_config(_WS_ID, config.id, state="disabled", actor_id=_ACTOR_ID)

        with pytest.raises(JiraConfigDisabledError):
            await svc.test_connection(_WS_ID, config.id)


class TestJiraCredentialsNotInAudit:
    @pytest.mark.asyncio
    async def test_credentials_ref_never_in_audit_payload(self) -> None:
        svc, _, audit = _make_service()
        await svc.create_config(
            _WS_ID, base_url="https://jira.example.com",
            auth_type="basic", credentials_ref="SUPERSECRET", actor_id=_ACTOR_ID
        )

        for event in audit.events:
            event_str = str(event)
            assert "SUPERSECRET" not in event_str
