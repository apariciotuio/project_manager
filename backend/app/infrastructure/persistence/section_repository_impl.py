"""EP-04 — SQLAlchemy Section + SectionVersion + Validator + WorkItemVersion repos.

Grouped in a single module for brevity — the 4 tables ship together and share
the same infrastructure concerns.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.section import Section
from app.domain.models.section_version import SectionVersion
from app.domain.models.validator import Validator
from app.domain.models.work_item_version import WorkItemVersion
from app.domain.repositories.section_repository import ISectionRepository
from app.domain.repositories.section_version_repository import (
    ISectionVersionRepository,
)
from app.domain.repositories.validator_repository import IValidatorRepository
from app.domain.repositories.work_item_version_repository import (
    IWorkItemVersionRepository,
)
from app.infrastructure.persistence.mappers.section_mapper import (
    section_to_domain,
    section_to_orm,
    section_version_to_domain,
    validator_to_domain,
    validator_to_orm,
    work_item_version_to_domain,
)
from app.infrastructure.persistence.models.orm import (
    WorkItemORM,
    WorkItemSectionORM,
    WorkItemSectionVersionORM,
    WorkItemValidatorORM,
    WorkItemVersionORM,
)


async def _resolve_workspace_id(session: AsyncSession, work_item_id: UUID) -> UUID:
    """Resolve workspace_id from work_items for RLS column population."""
    row = await session.get(WorkItemORM, work_item_id)
    if row is None:
        raise ValueError(f"work_item {work_item_id} not found — cannot resolve workspace_id")
    return row.workspace_id


class SectionRepositoryImpl(ISectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, section_id: UUID) -> Section | None:
        row = await self._session.get(WorkItemSectionORM, section_id)
        return section_to_domain(row) if row else None

    async def get_by_work_item(self, work_item_id: UUID) -> list[Section]:
        stmt = (
            select(WorkItemSectionORM)
            .where(WorkItemSectionORM.work_item_id == work_item_id)
            .order_by(WorkItemSectionORM.display_order)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [section_to_domain(r) for r in rows]

    async def save(self, section: Section) -> Section:
        existing = await self._session.get(WorkItemSectionORM, section.id)
        if existing is None:
            row = section_to_orm(section)
            if row.workspace_id is None:  # type: ignore[attr-defined]
                row.workspace_id = await _resolve_workspace_id(
                    self._session, section.work_item_id
                )
            self._session.add(row)
        else:
            existing.content = section.content
            existing.is_required = section.is_required
            existing.display_order = section.display_order
            existing.generation_source = section.generation_source.value
            existing.version = section.version
            existing.updated_at = section.updated_at
            existing.updated_by = section.updated_by
        await self._session.flush()
        return section

    async def bulk_insert(self, sections: list[Section]) -> list[Section]:
        if not sections:
            return []
        # Resolve workspace_id once (all sections share the same work_item_id)
        work_item_id = sections[0].work_item_id
        workspace_id = (
            sections[0].workspace_id
            or await _resolve_workspace_id(self._session, work_item_id)
        )
        rows = [section_to_orm(s) for s in sections]
        for r in rows:
            if r.workspace_id is None:  # type: ignore[attr-defined]
                r.workspace_id = workspace_id
            self._session.add(r)
        await self._session.flush()
        return [section_to_domain(r) for r in rows]


class SectionVersionRepositoryImpl(ISectionVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, section: Section, actor_id: UUID) -> SectionVersion:
        workspace_id = section.workspace_id or await _resolve_workspace_id(
            self._session, section.work_item_id
        )
        row = WorkItemSectionVersionORM()
        row.id = uuid4()
        row.section_id = section.id
        row.work_item_id = section.work_item_id
        row.workspace_id = workspace_id
        row.section_type = section.section_type.value
        row.content = section.content
        row.version = section.version
        row.generation_source = section.generation_source.value
        row.revert_from_version = None
        row.created_at = datetime.now(UTC)
        row.created_by = actor_id
        self._session.add(row)
        await self._session.flush()
        return section_version_to_domain(row)

    async def get_history(self, section_id: UUID) -> list[SectionVersion]:
        stmt = (
            select(WorkItemSectionVersionORM)
            .where(WorkItemSectionVersionORM.section_id == section_id)
            .order_by(WorkItemSectionVersionORM.version.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [section_version_to_domain(r) for r in rows]


class ValidatorRepositoryImpl(IValidatorRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, validator_id: UUID) -> Validator | None:
        row = await self._session.get(WorkItemValidatorORM, validator_id)
        return validator_to_domain(row) if row else None

    async def get_by_work_item(self, work_item_id: UUID) -> list[Validator]:
        stmt = select(WorkItemValidatorORM).where(
            WorkItemValidatorORM.work_item_id == work_item_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [validator_to_domain(r) for r in rows]

    async def assign(self, validator: Validator) -> Validator:
        row = validator_to_orm(validator)
        if row.workspace_id is None:  # type: ignore[attr-defined]
            row.workspace_id = await _resolve_workspace_id(
                self._session, validator.work_item_id
            )
        self._session.add(row)
        await self._session.flush()
        return validator

    async def save(self, validator: Validator) -> Validator:
        existing = await self._session.get(WorkItemValidatorORM, validator.id)
        if existing is None:
            row = validator_to_orm(validator)
            if row.workspace_id is None:  # type: ignore[attr-defined]
                row.workspace_id = await _resolve_workspace_id(
                    self._session, validator.work_item_id
                )
            self._session.add(row)
        else:
            existing.status = validator.status.value
            existing.responded_at = validator.responded_at
            existing.user_id = validator.user_id
        await self._session.flush()
        return validator


class WorkItemVersionRepositoryImpl(IWorkItemVersionRepository):
    """EP-04 implementation — append-only, no workspace scoping in queries.

    For workspace-scoped reads (EP-07 API), use
    work_item_version_repository_impl.WorkItemVersionRepositoryImpl instead.
    This class is kept for backward-compat with EP-04 tests and section save path.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        work_item_id: UUID,
        snapshot: dict[str, Any],
        created_by: UUID,
        *,
        trigger: str = "content_edit",
        actor_type: str = "human",
        actor_id: UUID | None = None,
        commit_message: str | None = None,
    ) -> WorkItemVersion:
        stmt = (
            select(WorkItemVersionORM.version_number)
            .where(WorkItemVersionORM.work_item_id == work_item_id)
            .order_by(WorkItemVersionORM.version_number.desc())
            .limit(1)
        )
        latest = (await self._session.execute(stmt)).scalar_one_or_none()
        next_number = (latest or 0) + 1

        workspace_id = await _resolve_workspace_id(self._session, work_item_id)
        row = WorkItemVersionORM()
        row.id = uuid4()
        row.work_item_id = work_item_id
        row.workspace_id = workspace_id
        row.version_number = next_number
        row.snapshot = snapshot
        row.created_by = created_by
        row.created_at = datetime.now(UTC)
        row.trigger = trigger
        row.actor_type = actor_type
        row.actor_id = actor_id
        row.commit_message = commit_message
        row.archived = False
        self._session.add(row)
        await self._session.flush()
        return work_item_version_to_domain(row)

    async def get_latest(self, work_item_id: UUID, workspace_id: UUID | None = None) -> WorkItemVersion | None:  # type: ignore[override]
        stmt = (
            select(WorkItemVersionORM)
            .where(WorkItemVersionORM.work_item_id == work_item_id)
            .order_by(WorkItemVersionORM.version_number.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return work_item_version_to_domain(row) if row else None

    async def get(self, version_id: UUID, workspace_id: UUID | None = None) -> WorkItemVersion | None:  # type: ignore[override]
        row = await self._session.get(WorkItemVersionORM, version_id)
        return work_item_version_to_domain(row) if row else None

    async def get_by_number(
        self, work_item_id: UUID, version_number: int, workspace_id: UUID
    ) -> WorkItemVersion | None:
        stmt = (
            select(WorkItemVersionORM)
            .where(
                WorkItemVersionORM.work_item_id == work_item_id,
                WorkItemVersionORM.version_number == version_number,
            )
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return work_item_version_to_domain(row) if row else None

    async def list_by_work_item(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        limit: int = 20,
        before_version: int | None = None,
    ) -> list[WorkItemVersion]:
        stmt = select(WorkItemVersionORM).where(
            WorkItemVersionORM.work_item_id == work_item_id
        )
        if not include_archived:
            stmt = stmt.where(WorkItemVersionORM.archived.is_(False))
        if before_version is not None:
            stmt = stmt.where(WorkItemVersionORM.version_number < before_version)
        stmt = stmt.order_by(WorkItemVersionORM.version_number.desc()).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [work_item_version_to_domain(r) for r in rows]
