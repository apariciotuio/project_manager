"""AdminSupportService — EP-10 support tools (read-only aggregation + reassign).

Endpoints:
  GET /admin/support/orphaned-work-items
  GET /admin/support/pending-invitations
  GET /admin/support/failed-exports
  GET /admin/support/config-blocked-work-items
  POST /admin/support/reassign-owner
  POST /admin/support/failed-exports/retry-all
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.application.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_RETRY_ALL_RATE_LIMIT_KEY = "retry_all:{workspace_id}"
_RETRY_ALL_TTL = 600  # 10 min


class SupportError(ValueError):
    pass


class ReassignTargetInactiveError(SupportError):
    code = "reassign_target_inactive"


class ReassignTerminalItemError(SupportError):
    code = "reassign_terminal_item"


class RetryAllRateLimitedError(SupportError):
    code = "retry_all_rate_limited"


_TERMINAL_STATES = frozenset({"ready", "archived", "cancelled"})


class AdminSupportService:
    def __init__(
        self,
        session: object,
        audit: AuditService,
        cache: object | None = None,
    ) -> None:
        self._session = session
        self._audit = audit
        self._cache = cache

    async def get_orphaned_work_items(self, workspace_id: UUID) -> list[dict[str, Any]]:
        from sqlalchemy import or_, select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.infrastructure.persistence.models.orm import UserORM, WorkItemORM

        session: AsyncSession = self._session  # type: ignore[assignment]
        stmt = (
            select(WorkItemORM, UserORM)
            .join(UserORM, WorkItemORM.owner_id == UserORM.id)
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
                WorkItemORM.state.not_in(list(_TERMINAL_STATES)),
                or_(
                    UserORM.status == "suspended",
                    UserORM.status == "deleted",
                ),
            )
            .order_by(WorkItemORM.created_at.desc())
            .limit(200)
        )
        rows = (await session.execute(stmt)).all()
        return [
            {
                "id": str(r.WorkItemORM.id),
                "title": r.WorkItemORM.title,
                "state": r.WorkItemORM.state,
                "owner_id": str(r.WorkItemORM.owner_id),
                "owner_email": r.UserORM.email,
                "owner_status": r.UserORM.status,
                "created_at": r.WorkItemORM.created_at.isoformat(),
            }
            for r in rows
        ]

    async def get_pending_invitations(
        self, workspace_id: UUID, *, expiring_soon: bool = False
    ) -> list[dict[str, Any]]:
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.infrastructure.persistence.models.orm import InvitationORM

        session: AsyncSession = self._session  # type: ignore[assignment]
        stmt = select(InvitationORM).where(
            InvitationORM.workspace_id == workspace_id,
            InvitationORM.state == "invited",
        )
        if expiring_soon:
            threshold = datetime.now(UTC) + timedelta(hours=24)
            stmt = stmt.where(InvitationORM.expires_at <= threshold)
        stmt = stmt.order_by(InvitationORM.expires_at).limit(200)

        rows = (await session.execute(stmt)).scalars().all()
        now = datetime.now(UTC)
        return [
            {
                "id": str(r.id),
                "email": r.email,
                "state": r.state,
                "expires_at": r.expires_at.isoformat(),
                "expired": r.expires_at < now,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

    async def get_failed_exports(self, workspace_id: UUID) -> list[dict[str, Any]]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.infrastructure.persistence.models.orm import IntegrationExportORM

        session: AsyncSession = self._session  # type: ignore[assignment]
        stmt = (
            select(IntegrationExportORM)
            .where(
                IntegrationExportORM.workspace_id == workspace_id,
                IntegrationExportORM.status == "failed",
            )
            .order_by(IntegrationExportORM.exported_at.desc())
            .limit(200)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": str(r.id),
                "work_item_id": str(r.work_item_id),
                "integration_config_id": str(r.integration_config_id),
                "error_message": r.error_message,
                "exported_at": r.exported_at.isoformat(),
            }
            for r in rows
        ]

    async def retry_all_failed_exports(
        self, workspace_id: UUID, actor_id: UUID
    ) -> dict[str, Any]:
        rate_key = _RETRY_ALL_RATE_LIMIT_KEY.format(workspace_id=workspace_id)

        if self._cache is not None:
            try:
                existing = await self._cache.get(rate_key)  # type: ignore[union-attr]
                if existing:
                    raise RetryAllRateLimitedError("retry-all called within 10 min window")
                await self._cache.set(rate_key, "1", ttl=_RETRY_ALL_TTL)  # type: ignore[union-attr]
            except RetryAllRateLimitedError:
                raise
            except Exception:
                logger.warning("retry-all rate limit cache failed")

        failed = await self.get_failed_exports(workspace_id)

        # Emit audit
        await self._audit.log_event(
            category="admin",
            action="jira_bulk_retry",
            actor_id=actor_id,
            workspace_id=workspace_id,
            context={"count": len(failed)},
        )

        return {"queued": len(failed), "warning": None}

    async def reassign_owner(
        self,
        workspace_id: UUID,
        work_item_id: UUID,
        new_owner_id: UUID,
        actor_id: UUID,
    ) -> None:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.infrastructure.persistence.models.orm import (
            WorkItemORM,
            WorkspaceMembershipORM,
        )

        session: AsyncSession = self._session  # type: ignore[assignment]

        # Validate work item
        wi = (
            await session.execute(
                select(WorkItemORM).where(
                    WorkItemORM.id == work_item_id,
                    WorkItemORM.workspace_id == workspace_id,
                    WorkItemORM.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if wi is None:
            raise SupportError(f"work item {work_item_id} not found")
        if wi.state in _TERMINAL_STATES:
            raise ReassignTerminalItemError(f"cannot reassign terminal work item in state {wi.state!r}")

        # Validate new owner is active in workspace
        membership = (
            await session.execute(
                select(WorkspaceMembershipORM).where(
                    WorkspaceMembershipORM.workspace_id == workspace_id,
                    WorkspaceMembershipORM.user_id == new_owner_id,
                    WorkspaceMembershipORM.state == "active",
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            raise ReassignTargetInactiveError(f"new owner {new_owner_id} is not an active member")

        old_owner = wi.owner_id
        wi.owner_id = new_owner_id
        await session.flush()

        await self._audit.log_event(
            category="admin",
            action="owner_reassigned",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="work_item",
            entity_id=work_item_id,
            before_value={"owner_id": str(old_owner)},
            after_value={"owner_id": str(new_owner_id)},
        )

    async def get_config_blocked_work_items(
        self, workspace_id: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.infrastructure.persistence.models.orm import UserORM, WorkItemORM

        session: AsyncSession = self._session  # type: ignore[assignment]

        # Suspended owner group
        suspended_stmt = (
            select(WorkItemORM, UserORM)
            .join(UserORM, WorkItemORM.owner_id == UserORM.id)
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
                WorkItemORM.state.not_in(list(_TERMINAL_STATES)),
                UserORM.status == "suspended",
            )
            .limit(100)
        )
        suspended_rows = (await session.execute(suspended_stmt)).all()

        return {
            "suspended_owner": [
                {
                    "id": str(r.WorkItemORM.id),
                    "title": r.WorkItemORM.title,
                    "owner_id": str(r.WorkItemORM.owner_id),
                }
                for r in suspended_rows
            ],
            "deleted_team_in_rule": [],
            "archived_project": [],
        }
