"""JiraConfig domain entity — EP-10 Jira integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

JiraState = Literal["active", "disabled", "error"]
JiraAuthType = Literal["basic", "oauth2"]
JiraHealthStatus = Literal["ok", "auth_failure", "unreachable"]

_MAX_CONSECUTIVE_FAILURES = 3


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class JiraConfig:
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    base_url: str
    auth_type: JiraAuthType
    credentials_ref: str  # Fernet-encrypted blob; NEVER expose to callers
    state: JiraState
    last_health_check_status: JiraHealthStatus | None
    last_health_check_at: datetime | None
    consecutive_failures: int
    created_by: UUID
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        base_url: str,
        auth_type: str,
        credentials_ref: str,
        created_by: UUID,
        project_id: UUID | None = None,
    ) -> JiraConfig:
        _validate_base_url(base_url)
        if auth_type not in ("basic", "oauth2"):
            raise ValueError(f"invalid auth_type: {auth_type!r}")
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            base_url=base_url.rstrip("/"),
            auth_type=auth_type,  # type: ignore[arg-type]
            credentials_ref=credentials_ref,
            state="active",
            last_health_check_status=None,
            last_health_check_at=None,
            consecutive_failures=0,
            created_by=created_by,
        )

    def record_health_check(self, status: JiraHealthStatus) -> None:
        self.last_health_check_status = status
        self.last_health_check_at = _now()
        self.updated_at = _now()

        if status == "ok":
            was_error = self.state == "error"
            self.consecutive_failures = 0
            if was_error:
                self.state = "active"
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                self.state = "error"

    def disable(self) -> None:
        self.state = "disabled"
        self.updated_at = _now()

    def enable(self) -> None:
        self.state = "active"
        self.consecutive_failures = 0
        self.updated_at = _now()

    def update_credentials(self, new_credentials_ref: str) -> None:
        self.credentials_ref = new_credentials_ref
        self.updated_at = _now()

    def is_testable(self) -> bool:
        return self.state != "disabled"


@dataclass
class JiraProjectMapping:
    id: UUID
    jira_config_id: UUID
    workspace_id: UUID
    jira_project_key: str
    local_project_id: UUID | None
    type_mappings: dict[str, Any]
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @classmethod
    def create(
        cls,
        *,
        jira_config_id: UUID,
        workspace_id: UUID,
        jira_project_key: str,
        local_project_id: UUID | None = None,
        type_mappings: dict[str, Any] | None = None,
    ) -> JiraProjectMapping:
        if not jira_project_key.strip():
            raise ValueError("jira_project_key must not be empty")
        return cls(
            id=uuid4(),
            jira_config_id=jira_config_id,
            workspace_id=workspace_id,
            jira_project_key=jira_project_key.upper(),
            local_project_id=local_project_id,
            type_mappings=type_mappings or {},
        )


def _validate_base_url(url: str) -> None:
    if not url.startswith("https://"):
        raise ValueError("base_url must use HTTPS")
    if len(url) > 500:
        raise ValueError("base_url too long")
