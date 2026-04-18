"""EP-10 — ProjectService."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.project import Project, RoutingRule
from app.domain.repositories.project_repository import (
    IProjectRepository,
    IRoutingRuleRepository,
)


class ProjectNotFoundError(LookupError):
    pass


class RoutingRuleNotFoundError(LookupError):
    pass


class ProjectService:
    def __init__(
        self,
        *,
        project_repo: IProjectRepository,
        routing_rule_repo: IRoutingRuleRepository,
    ) -> None:
        self._projects = project_repo
        self._rules = routing_rule_repo

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        created_by: UUID,
        description: str | None = None,
    ) -> Project:
        project = Project.create(
            workspace_id=workspace_id,
            name=name,
            created_by=created_by,
            description=description,
        )
        return await self._projects.create(project)

    async def get(self, project_id: UUID, *, workspace_id: UUID) -> Project:
        """Return a project scoped to the caller's workspace.

        Raises ProjectNotFoundError when the project does not exist OR
        belongs to another workspace — caller must not be able to
        distinguish the two cases (IDOR mitigation).
        """
        project = await self._projects.get(project_id)
        if project is None or project.workspace_id != workspace_id:
            raise ProjectNotFoundError(f"project {project_id} not found")
        return project

    async def list_for_workspace(self, workspace_id: UUID) -> list[Project]:
        return await self._projects.list_active_for_workspace(workspace_id)

    async def update(
        self,
        project_id: UUID,
        *,
        workspace_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        from datetime import UTC, datetime

        project = await self.get(project_id, workspace_id=workspace_id)
        if name is not None:
            if not name.strip():
                raise ValueError("project name cannot be empty")
            project.name = name.strip()
        if description is not None:
            project.description = description
        project.updated_at = datetime.now(UTC)
        return await self._projects.save(project)

    async def soft_delete(self, project_id: UUID, *, workspace_id: UUID) -> Project:
        project = await self.get(project_id, workspace_id=workspace_id)
        project.soft_delete()
        return await self._projects.save(project)

    async def create_routing_rule(
        self,
        *,
        workspace_id: UUID,
        work_item_type: str,
        created_by: UUID,
        project_id: UUID | None = None,
        suggested_team_id: UUID | None = None,
        suggested_owner_id: UUID | None = None,
        suggested_validators: list | None = None,
        priority: int = 0,
    ) -> RoutingRule:
        rule = RoutingRule.create(
            workspace_id=workspace_id,
            work_item_type=work_item_type,
            created_by=created_by,
            project_id=project_id,
            suggested_team_id=suggested_team_id,
            suggested_owner_id=suggested_owner_id,
            suggested_validators=suggested_validators,
            priority=priority,
        )
        return await self._rules.create(rule)

    async def list_routing_rules(self, workspace_id: UUID) -> list[RoutingRule]:
        return await self._rules.list_for_workspace(workspace_id)

    async def match_routing(
        self,
        workspace_id: UUID,
        work_item_type: str,
        project_id: UUID | None = None,
    ) -> RoutingRule | None:
        return await self._rules.match(workspace_id, work_item_type, project_id)

    async def get_routing_rule(self, rule_id: UUID, *, workspace_id: UUID) -> RoutingRule:
        rule = await self._rules.get(rule_id)
        if rule is None or rule.workspace_id != workspace_id:
            raise RoutingRuleNotFoundError(f"routing rule {rule_id} not found")
        return rule

    async def update_routing_rule(
        self,
        rule_id: UUID,
        *,
        workspace_id: UUID,
        suggested_team_id: UUID | None = None,
        suggested_owner_id: UUID | None = None,
        suggested_validators: list | None = None,
        priority: int | None = None,
        active: bool | None = None,
    ) -> RoutingRule:
        from datetime import UTC, datetime

        rule = await self.get_routing_rule(rule_id, workspace_id=workspace_id)
        if suggested_team_id is not None:
            rule.suggested_team_id = suggested_team_id
        if suggested_owner_id is not None:
            rule.suggested_owner_id = suggested_owner_id
        if suggested_validators is not None:
            rule.suggested_validators = suggested_validators
        if priority is not None:
            rule.priority = priority
        if active is not None:
            rule.active = active
        rule.updated_at = datetime.now(UTC)
        return await self._rules.save(rule)

    async def delete_routing_rule(self, rule_id: UUID, *, workspace_id: UUID) -> None:
        rule = await self._rules.get(rule_id)
        if rule is None or rule.workspace_id != workspace_id:
            raise RoutingRuleNotFoundError(f"routing rule {rule_id} not found")
        await self._rules.delete(rule_id)
