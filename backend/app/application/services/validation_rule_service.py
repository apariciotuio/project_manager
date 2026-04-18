"""ValidationRuleService — EP-10 admin rules CRUD + precedence."""

from __future__ import annotations

import logging
from uuid import UUID

from app.application.services.audit_service import AuditService
from app.domain.models.validation_rule import ValidationRule
from app.domain.repositories.validation_rule_repository import IValidationRuleRepository

logger = logging.getLogger(__name__)


class ValidationRuleNotFoundError(LookupError):
    pass


class DuplicateRuleError(ValueError):
    code = "rule_already_exists"

    def __init__(self, existing_id: UUID) -> None:
        super().__init__("rule already exists for this scope")
        self.existing_id = existing_id


class GlobalBlockerInEffectError(ValueError):
    code = "global_blocker_in_effect"


class RuleHasHistoryError(ValueError):
    code = "rule_has_history"


class ValidationRuleService:
    def __init__(
        self,
        repo: IValidationRuleRepository,
        audit: AuditService,
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def list_rules(
        self,
        workspace_id: UUID,
        *,
        project_id: UUID | None = None,
        work_item_type: str | None = None,
    ) -> list[ValidationRule]:
        rules = await self._repo.list_for_workspace(
            workspace_id,
            project_id=project_id,
            work_item_type=work_item_type,
            active_only=True,
        )
        # Annotate effective + superseded_by
        return _annotate_precedence(rules)

    async def create_rule(
        self,
        workspace_id: UUID,
        *,
        project_id: UUID | None,
        work_item_type: str,
        validation_type: str,
        enforcement: str,
        actor_id: UUID,
    ) -> ValidationRule:
        # Check for global blocker if creating project-scope rule
        if project_id is not None:
            workspace_rules = await self._repo.list_for_workspace(
                workspace_id,
                work_item_type=work_item_type,
                active_only=True,
            )
            blockers = [
                r
                for r in workspace_rules
                if r.is_global_blocker()
                and r.work_item_type == work_item_type
                and r.validation_type == validation_type
            ]
            if blockers:
                raise GlobalBlockerInEffectError(
                    f"workspace-level blocked_override rule in effect for "
                    f"{work_item_type}/{validation_type}"
                )

        # Check for duplicate
        existing_rules = await self._repo.list_for_workspace(
            workspace_id,
            project_id=project_id,
            work_item_type=work_item_type,
            active_only=True,
        )
        scope_rules = [
            r
            for r in existing_rules
            if r.project_id == project_id
            and r.work_item_type == work_item_type
            and r.validation_type == validation_type
        ]
        if scope_rules:
            raise DuplicateRuleError(scope_rules[0].id)

        rule = ValidationRule.create(
            workspace_id=workspace_id,
            project_id=project_id,
            work_item_type=work_item_type,
            validation_type=validation_type,
            enforcement=enforcement,
            created_by=actor_id,
        )
        created = await self._repo.create(rule)

        await self._audit.log_event(
            category="admin",
            action="validation_rule_created",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="validation_rule",
            entity_id=created.id,
            after_value={
                "work_item_type": work_item_type,
                "validation_type": validation_type,
                "enforcement": enforcement,
                "project_id": str(project_id) if project_id else None,
            },
        )
        return created

    async def update_rule(
        self,
        workspace_id: UUID,
        rule_id: UUID,
        *,
        enforcement: str | None = None,
        active: bool | None = None,
        actor_id: UUID,
    ) -> tuple[ValidationRule, list[UUID]]:
        """Returns (updated_rule, superseded_rule_ids) — list is non-empty when
        enforcement changes to blocked_override."""
        rule = await self._repo.get_by_id(rule_id, workspace_id)
        if rule is None:
            raise ValidationRuleNotFoundError(rule_id)

        before = {"enforcement": rule.enforcement, "active": rule.active}
        rule.update(enforcement=enforcement, active=active)
        updated = await self._repo.save(rule)

        superseded_ids: list[UUID] = []
        if enforcement == "blocked_override" and rule.is_workspace_scope():
            # Flag project-level rules for same type/validation as superseded
            project_rules = await self._repo.list_for_workspace(
                workspace_id,
                work_item_type=rule.work_item_type,
                active_only=True,
                include_all_projects=True,
            )
            for pr in project_rules:
                if (
                    pr.project_id is not None
                    and pr.work_item_type == rule.work_item_type
                    and pr.validation_type == rule.validation_type
                    and pr.id != rule_id
                ):
                    superseded_ids.append(pr.id)

        await self._audit.log_event(
            category="admin",
            action="validation_rule_updated",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="validation_rule",
            entity_id=rule_id,
            before_value=before,
            after_value={"enforcement": updated.enforcement, "active": updated.active},
        )
        return updated, superseded_ids

    async def delete_rule(
        self,
        workspace_id: UUID,
        rule_id: UUID,
        actor_id: UUID,
    ) -> None:
        rule = await self._repo.get_by_id(rule_id, workspace_id)
        if rule is None:
            raise ValidationRuleNotFoundError(rule_id)

        if await self._repo.has_history(rule_id):
            raise RuleHasHistoryError(f"rule {rule_id} has audit history — cannot hard delete")

        await self._repo.delete(rule_id, workspace_id)

        await self._audit.log_event(
            category="admin",
            action="validation_rule_deleted",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="validation_rule",
            entity_id=rule_id,
        )


def _annotate_precedence(rules: list[ValidationRule]) -> list[ValidationRule]:
    """Set effective=True/False and superseded_by on each rule.

    Precedence: project-level overrides workspace-level.
    blocked_override workspace rules always apply regardless of project rules.
    """
    # Group by (work_item_type, validation_type)
    from collections import defaultdict

    by_type: dict[tuple[str, str], list[ValidationRule]] = defaultdict(list)
    for rule in rules:
        by_type[(rule.work_item_type, rule.validation_type)].append(rule)

    for group in by_type.values():
        ws_rules = [r for r in group if r.project_id is None]
        proj_rules = [r for r in group if r.project_id is not None]

        # Find global blockers
        blockers = [r for r in ws_rules if r.enforcement == "blocked_override"]

        for rule in group:
            if rule.enforcement == "blocked_override" and rule.project_id is None:
                rule.effective = True
                rule.superseded_by = None
            elif proj_rules and rule.project_id is None and not blockers:
                # Workspace rule superseded by project rule
                rule.effective = False
                rule.superseded_by = proj_rules[0].id if proj_rules else None
            else:
                rule.effective = True
                rule.superseded_by = None

    return rules
