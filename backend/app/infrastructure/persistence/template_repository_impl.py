"""SQLAlchemy implementation of ITemplateRepository — EP-02."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import DuplicateTemplateError, TemplateNotFoundError
from app.domain.models.template import Template
from app.domain.repositories.template_repository import ITemplateRepository
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.persistence.models.orm import TemplateORM

_DUPLICATE_IDX = "idx_templates_workspace_type"
_DUPLICATE_SYSTEM_IDX = "idx_templates_system_type"


def _to_domain(row: TemplateORM) -> Template:
    return Template(
        id=row.id,
        workspace_id=row.workspace_id,
        type=WorkItemType(row.type),
        name=row.name,
        content=row.content,
        is_system=row.is_system,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _classify_integrity_error(exc: IntegrityError, template: Template) -> Exception:
    msg = str(exc.orig).lower()
    if _DUPLICATE_IDX.lower() in msg or _DUPLICATE_SYSTEM_IDX.lower() in msg or "unique" in msg:
        ws_id = template.workspace_id if template.workspace_id else UUID(int=0)
        return DuplicateTemplateError(ws_id, template.type.value)
    return exc


class TemplateRepositoryImpl(ITemplateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_workspace_and_type(
        self, workspace_id: UUID, type: WorkItemType
    ) -> Template | None:
        stmt = select(TemplateORM).where(
            TemplateORM.workspace_id == workspace_id,
            TemplateORM.type == type.value,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_system_default(self, type: WorkItemType) -> Template | None:
        stmt = select(TemplateORM).where(
            TemplateORM.is_system.is_(True),
            TemplateORM.type == type.value,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_by_id(self, template_id: UUID) -> Template | None:
        stmt = select(TemplateORM).where(TemplateORM.id == template_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def create(self, template: Template) -> Template:
        row = TemplateORM()
        row.id = template.id
        row.workspace_id = template.workspace_id
        row.type = template.type.value
        row.name = template.name
        row.content = template.content
        row.is_system = template.is_system
        row.created_by = template.created_by
        row.created_at = template.created_at
        row.updated_at = template.updated_at
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise _classify_integrity_error(exc, template) from exc
        return _to_domain(row)

    async def update(self, template_id: UUID, *, name: str | None, content: str | None) -> Template:
        values: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if name is not None:
            values["name"] = name
        if content is not None:
            values["content"] = content

        stmt = (
            update(TemplateORM)
            .where(TemplateORM.id == template_id)
            .values(**values)
            .returning(TemplateORM)
        )
        result = (await self._session.execute(stmt)).scalar_one_or_none()
        if result is None:
            raise TemplateNotFoundError(template_id)
        await self._session.flush()
        return _to_domain(result)

    async def delete(self, template_id: UUID) -> None:
        stmt = select(TemplateORM).where(TemplateORM.id == template_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise TemplateNotFoundError(template_id)
        await self._session.delete(row)
        await self._session.flush()

    async def list_for_workspace(self, workspace_id: UUID) -> list[Template]:
        # Hard cap to keep unbounded queries safe until pagination ships.
        stmt = select(TemplateORM).where(TemplateORM.workspace_id == workspace_id).limit(500)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]
