"""EP-10 — Project, RoutingRule repository implementations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.project import Project, RoutingRule
from app.domain.repositories.project_repository import (
    IProjectRepository,
    IRoutingRuleRepository,
)
from app.infrastructure.persistence.mappers.project_mapper import (
    project_to_domain,
    project_to_orm,
    routing_rule_to_domain,
    routing_rule_to_orm,
)
from app.infrastructure.persistence.models.orm import ProjectORM, RoutingRuleORM


class ProjectRepositoryImpl(IProjectRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, project: Project) -> Project:
        self._session.add(project_to_orm(project))
        await self._session.flush()
        return project

    async def get(self, project_id: UUID) -> Project | None:
        row = await self._session.get(ProjectORM, project_id)
        return project_to_domain(row) if row else None

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Project]:
        # Hard cap to keep unbounded queries safe until pagination ships.
        stmt = (
            select(ProjectORM)
            .where(
                ProjectORM.workspace_id == workspace_id,
                ProjectORM.deleted_at.is_(None),
            )
            .order_by(ProjectORM.name)
            .limit(500)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [project_to_domain(r) for r in rows]

    async def save(self, project: Project) -> Project:
        existing = await self._session.get(ProjectORM, project.id)
        if existing is None:
            self._session.add(project_to_orm(project))
        else:
            existing.name = project.name
            existing.description = project.description
            existing.deleted_at = project.deleted_at
            existing.updated_at = project.updated_at
        await self._session.flush()
        return project


class RoutingRuleRepositoryImpl(IRoutingRuleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, rule: RoutingRule) -> RoutingRule:
        self._session.add(routing_rule_to_orm(rule))
        await self._session.flush()
        return rule

    async def get(self, rule_id: UUID) -> RoutingRule | None:
        row = await self._session.get(RoutingRuleORM, rule_id)
        return routing_rule_to_domain(row) if row else None

    async def list_for_workspace(self, workspace_id: UUID) -> list[RoutingRule]:
        stmt = (
            select(RoutingRuleORM)
            .where(RoutingRuleORM.workspace_id == workspace_id)
            .order_by(RoutingRuleORM.priority.desc(), RoutingRuleORM.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [routing_rule_to_domain(r) for r in rows]

    async def match(
        self,
        workspace_id: UUID,
        work_item_type: str,
        project_id: UUID | None,
    ) -> RoutingRule | None:
        """Return highest-priority rule matching workspace + type, optionally project."""
        conditions = [
            RoutingRuleORM.workspace_id == workspace_id,
            RoutingRuleORM.work_item_type == work_item_type,
        ]
        if project_id is not None:
            # prefer project-specific rule, fall back to workspace-level
            stmt = (
                select(RoutingRuleORM)
                .where(
                    *conditions,
                    RoutingRuleORM.project_id.in_([project_id, None]),
                )
                .order_by(
                    # project-specific beats workspace-level
                    RoutingRuleORM.project_id.is_(None),
                    RoutingRuleORM.priority.desc(),
                )
                .limit(1)
            )
        else:
            stmt = (
                select(RoutingRuleORM)
                .where(*conditions, RoutingRuleORM.project_id.is_(None))
                .order_by(RoutingRuleORM.priority.desc())
                .limit(1)
            )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return routing_rule_to_domain(row) if row else None

    async def save(self, rule: RoutingRule) -> RoutingRule:
        existing = await self._session.get(RoutingRuleORM, rule.id)
        if existing is None:
            self._session.add(routing_rule_to_orm(rule))
        else:
            existing.suggested_team_id = rule.suggested_team_id
            existing.suggested_owner_id = rule.suggested_owner_id
            existing.suggested_validators = rule.suggested_validators  # type: ignore[assignment]  # JSON col; ORM annotates as dict but stores list
            existing.priority = rule.priority
            existing.active = rule.active
            existing.updated_at = rule.updated_at
        await self._session.flush()
        return rule

    async def delete(self, rule_id: UUID) -> None:
        row = await self._session.get(RoutingRuleORM, rule_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()
