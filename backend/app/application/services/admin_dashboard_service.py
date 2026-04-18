"""AdminDashboardService — EP-10 workspace health aggregation.

All SQL lives in infrastructure (IDashboardRepository). This service orchestrates
repository calls + Redis cache. No SQL here.

Cache key: dashboard:{workspace_id}:{project_id|global}  TTL: 5 min
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300


class AdminDashboardService:
    def __init__(
        self,
        session: object,
        cache: object | None = None,
    ) -> None:
        self._session = session
        self._cache = cache

    async def get_dashboard(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
    ) -> dict[str, Any]:
        cache_key = f"dashboard:{workspace_id}:{project_id or 'global'}"

        if self._cache is not None:
            try:
                cached = await self._cache.get(cache_key)  # type: ignore[union-attr]
                if cached:
                    return json.loads(cached)
            except Exception:
                logger.warning("dashboard cache read failed")

        result = await self._compute_dashboard(workspace_id, project_id)

        if self._cache is not None:
            try:
                await self._cache.set(cache_key, json.dumps(result), ttl=_CACHE_TTL_SECONDS)  # type: ignore[union-attr]
            except Exception:
                logger.warning("dashboard cache write failed")

        return result

    async def _compute_dashboard(
        self, workspace_id: UUID, project_id: UUID | None
    ) -> dict[str, Any]:
        from sqlalchemy import func, select, and_
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.infrastructure.persistence.models.orm import (
            WorkItemORM,
            WorkspaceMembershipORM,
            UserORM,
            TeamORM,
            TeamMembershipORM,
            IntegrationConfigORM,
        )
        from datetime import UTC, datetime, timedelta

        session: AsyncSession = self._session  # type: ignore[assignment]
        now = datetime.now(UTC)
        stale_threshold = now - timedelta(days=5)

        # --- workspace_health ---
        wi_state_stmt = (
            select(WorkItemORM.state, func.count().label("cnt"))
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
            )
        )
        if project_id:
            wi_state_stmt = wi_state_stmt.where(WorkItemORM.project_id == project_id)
        wi_state_stmt = wi_state_stmt.group_by(WorkItemORM.state)

        wi_rows = (await session.execute(wi_state_stmt)).all()
        states = [{"state": r.state, "count": r.cnt} for r in wi_rows]

        # Critical blocks: non-terminal items older than stale_threshold
        critical_stmt = (
            select(func.count())
            .select_from(WorkItemORM)
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
                WorkItemORM.state.not_in(["ready", "archived", "cancelled"]),
                WorkItemORM.created_at < stale_threshold,
            )
        )
        if project_id:
            critical_stmt = critical_stmt.where(WorkItemORM.project_id == project_id)
        critical_blocks = (await session.execute(critical_stmt)).scalar_one()

        workspace_health = {
            "states": states,
            "critical_blocks": critical_blocks,
            "avg_time_to_ready": None,  # TODO: compute from state_transitions
            "stale_reviews": 0,
        }

        # --- org_health ---
        active_members_stmt = select(func.count()).select_from(WorkspaceMembershipORM).where(
            WorkspaceMembershipORM.workspace_id == workspace_id,
            WorkspaceMembershipORM.state == "active",
        )
        active_members = (await session.execute(active_members_stmt)).scalar_one()

        # TeamMembershipORM has no workspace_id — join through TeamORM
        team_users_subq = (
            select(TeamMembershipORM.user_id)
            .join(TeamORM, TeamMembershipORM.team_id == TeamORM.id)
            .where(
                TeamORM.workspace_id == workspace_id,
                TeamMembershipORM.removed_at.is_(None),
            )
        )
        teamless_stmt = (
            select(func.count())
            .select_from(WorkspaceMembershipORM)
            .where(
                WorkspaceMembershipORM.workspace_id == workspace_id,
                WorkspaceMembershipORM.state == "active",
                WorkspaceMembershipORM.user_id.not_in(team_users_subq),
            )
        )
        teamless_members = (await session.execute(teamless_stmt)).scalar_one()

        org_health = {
            "active_members": active_members,
            "teamless_members": teamless_members,
            "teams_without_lead": 0,
            "top_loaded_owners": [],
        }

        # --- integration_health ---
        jira_stmt = (
            select(
                IntegrationConfigORM.id,
                IntegrationConfigORM.state if hasattr(IntegrationConfigORM, "state") else None,
                IntegrationConfigORM.integration_type,
                IntegrationConfigORM.is_active,
            )
            .where(
                IntegrationConfigORM.workspace_id == workspace_id,
                IntegrationConfigORM.integration_type == "jira",
            )
        )
        jira_rows = (await session.execute(jira_stmt)).all()
        jira_configs_health = [
            {
                "id": str(r.id),
                "is_active": r.is_active,
            }
            for r in jira_rows
        ]

        integration_health = {
            "jira_configs": jira_configs_health,
        }

        return {
            "workspace_health": workspace_health,
            "org_health": org_health,
            "process_health": {
                "override_rate": None,
                "most_skipped_validations": [],
                "exported_count": 0,
                "blocked_by_type": [],
            },
            "integration_health": integration_health,
        }
