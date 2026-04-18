"""SQLAlchemy impl for IValidationRuleRepository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.validation_rule import ValidationRule
from app.domain.repositories.validation_rule_repository import IValidationRuleRepository
from app.infrastructure.persistence.models.orm import AuditEventORM, ValidationRuleORM


def _to_domain(row: ValidationRuleORM) -> ValidationRule:
    return ValidationRule(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        work_item_type=row.work_item_type,
        validation_type=row.validation_type,
        enforcement=row.enforcement,  # type: ignore[arg-type]
        active=row.active,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ValidationRuleRepositoryImpl(IValidationRuleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, rule: ValidationRule) -> ValidationRule:
        row = ValidationRuleORM(
            id=rule.id,
            workspace_id=rule.workspace_id,
            project_id=rule.project_id,
            work_item_type=rule.work_item_type,
            validation_type=rule.validation_type,
            enforcement=rule.enforcement,
            active=rule.active,
            created_by=rule.created_by,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_id(self, rule_id: UUID, workspace_id: UUID) -> ValidationRule | None:
        stmt = select(ValidationRuleORM).where(
            ValidationRuleORM.id == rule_id,
            ValidationRuleORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def list_for_workspace(
        self,
        workspace_id: UUID,
        *,
        project_id: UUID | None = None,
        work_item_type: str | None = None,
        active_only: bool = True,
    ) -> list[ValidationRule]:
        stmt = select(ValidationRuleORM).where(
            ValidationRuleORM.workspace_id == workspace_id
        )
        if project_id is not None:
            # Include workspace-level AND project-level rules for this project
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    ValidationRuleORM.project_id.is_(None),
                    ValidationRuleORM.project_id == project_id,
                )
            )
        else:
            stmt = stmt.where(ValidationRuleORM.project_id.is_(None))

        if work_item_type is not None:
            stmt = stmt.where(ValidationRuleORM.work_item_type == work_item_type)
        if active_only:
            stmt = stmt.where(ValidationRuleORM.active.is_(True))

        stmt = stmt.order_by(ValidationRuleORM.created_at).limit(500)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def save(self, rule: ValidationRule) -> ValidationRule:
        row = await self._session.get(ValidationRuleORM, rule.id)
        if row is None:
            return await self.create(rule)
        row.enforcement = rule.enforcement
        row.active = rule.active
        row.updated_at = rule.updated_at
        await self._session.flush()
        return _to_domain(row)

    async def delete(self, rule_id: UUID, workspace_id: UUID) -> None:
        stmt = select(ValidationRuleORM).where(
            ValidationRuleORM.id == rule_id,
            ValidationRuleORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row:
            await self._session.delete(row)
            await self._session.flush()

    async def has_history(self, rule_id: UUID) -> bool:
        stmt = select(AuditEventORM.id).where(
            AuditEventORM.entity_type == "validation_rule",
            AuditEventORM.entity_id == rule_id,
        ).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row is not None
