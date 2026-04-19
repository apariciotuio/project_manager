"""ExportService — application service for exporting work items to Jira.

Scope (EP-11):
  - Fetch work item from repository
  - Map WorkItemType → Jira issue type
  - Call JiraClient.create_issue()
  - Persist Jira key in external_jira_key (migration 0118); dual-writes
    export_reference for one release of backward compat.
  - Emit audit event under category='domain', action='jira_export'
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from app.domain.repositories.work_item_repository import IWorkItemRepository
from app.infrastructure.adapters.jira_adapter import (
    JiraAuthError,
    JiraClient,
    JiraIssue,
    JiraRateLimited,
    JiraUnavailable,
    JiraValidationError,
)

logger = logging.getLogger(__name__)

# WorkItemType value → Jira issue type name
_ISSUE_TYPE_MAP: dict[str, str] = {
    "task": "Task",
    "story": "Story",
    "bug": "Bug",
    "initiative": "Epic",
    "enhancement": "Task",
    "idea": "Task",
    "spike": "Task",
    "business_change": "Task",
    "requirement": "Story",
    "milestone": "Epic",
}

_DEFAULT_ISSUE_TYPE = "Task"


class WorkItemNotFoundError(LookupError):
    pass


class ExportError(RuntimeError):
    """Wraps upstream Jira errors for the presentation layer."""

    def __init__(self, message: str, code: str = "JIRA_ERROR") -> None:
        self.code = code
        super().__init__(message)


class ExportService:
    def __init__(
        self,
        *,
        work_item_repo: IWorkItemRepository,
        jira_client: JiraClient,
        audit_service: object | None = None,  # AuditService — optional so tests stay simple
    ) -> None:
        self._work_item_repo = work_item_repo
        self._jira_client = jira_client
        self._audit = audit_service

    async def export_work_item_to_jira(
        self,
        *,
        work_item_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        project_key: str,
    ) -> JiraIssue:
        """Fetch work item, create Jira issue, persist key, emit audit.

        Raises:
            WorkItemNotFoundError: work item not found or cross-workspace access
            ExportError:           any Jira API error (auth, rate limit, unavailable)
        """
        work_item = await self._work_item_repo.get(work_item_id, workspace_id)
        if work_item is None:
            raise WorkItemNotFoundError(f"work item {work_item_id} not found")

        issue_type = _ISSUE_TYPE_MAP.get(str(work_item.type), _DEFAULT_ISSUE_TYPE)

        try:
            issue = await self._jira_client.create_issue(
                summary=work_item.title,
                description=work_item.description or "",
                issue_type=issue_type,
                project_key=project_key,
                labels=work_item.tags if work_item.tags else None,
            )
        except JiraAuthError as exc:
            await self._audit_failure(work_item_id, workspace_id, user_id, "auth_error")
            raise ExportError(str(exc), code="JIRA_AUTH_ERROR") from exc
        except JiraRateLimited as exc:
            await self._audit_failure(work_item_id, workspace_id, user_id, "rate_limited")
            raise ExportError(str(exc), code="JIRA_RATE_LIMITED") from exc
        except JiraUnavailable as exc:
            await self._audit_failure(work_item_id, workspace_id, user_id, "unavailable")
            raise ExportError(str(exc), code="JIRA_UNAVAILABLE") from exc
        except JiraValidationError as exc:
            await self._audit_failure(work_item_id, workspace_id, user_id, "validation_error")
            raise ExportError(exc.raw_body, code="JIRA_VALIDATION_ERROR") from exc

        # Write to the canonical external_jira_key column (migration 0118).
        # Dual-write to export_reference for one release of backward compat —
        # drop the export_reference assignment in the next release.
        work_item.external_jira_key = issue.key
        work_item.export_reference = issue.key
        work_item.exported_at = datetime.now(UTC)
        await self._work_item_repo.save(work_item, workspace_id)

        await self._audit_success(work_item_id, workspace_id, user_id, issue.key)
        return issue

    async def _audit_success(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        actor_id: UUID,
        jira_key: str,
    ) -> None:
        if self._audit is None:
            return
        try:
            await self._audit.log_event(
                category="domain",
                action="jira_export",
                actor_id=actor_id,
                workspace_id=workspace_id,
                entity_type="work_item",
                entity_id=work_item_id,
                after_value={"jira_key": jira_key, "outcome": "success"},
            )
        except Exception:
            logger.exception("audit log failed for jira_export success")

    async def _audit_failure(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> None:
        if self._audit is None:
            return
        try:
            await self._audit.log_event(
                category="domain",
                action="jira_export",
                actor_id=actor_id,
                workspace_id=workspace_id,
                entity_type="work_item",
                entity_id=work_item_id,
                after_value={"outcome": "failure", "reason": reason},
            )
        except Exception:
            logger.exception("audit log failed for jira_export failure")
