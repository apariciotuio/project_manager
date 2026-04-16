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
    WorkItemSectionORM,
    WorkItemSectionVersionORM,
    WorkItemValidatorORM,
    WorkItemVersionORM,
)


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
            self._session.add(section_to_orm(section))
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
        rows = [section_to_orm(s) for s in sections]
        for r in rows:
            self._session.add(r)
        await self._session.flush()
        return [section_to_domain(r) for r in rows]


class SectionVersionRepositoryImpl(ISectionVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, section: Section, actor_id: UUID) -> SectionVersion:
        row = WorkItemSectionVersionORM()
        row.id = uuid4()
        row.section_id = section.id
        row.work_item_id = section.work_item_id
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
        self._session.add(validator_to_orm(validator))
        await self._session.flush()
        return validator

    async def save(self, validator: Validator) -> Validator:
        existing = await self._session.get(WorkItemValidatorORM, validator.id)
        if existing is None:
            self._session.add(validator_to_orm(validator))
        else:
            existing.status = validator.status.value
            existing.responded_at = validator.responded_at
            existing.user_id = validator.user_id
        await self._session.flush()
        return validator


class WorkItemVersionRepositoryImpl(IWorkItemVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        work_item_id: UUID,
        snapshot: dict[str, Any],
        created_by: UUID,
    ) -> WorkItemVersion:
        # Compute next version_number under a SELECT-then-INSERT pattern; the
        # UNIQUE(work_item_id, version_number) constraint will reject racing
        # writers so the caller can surface VersionConflictError.
        stmt = (
            select(WorkItemVersionORM.version_number)
            .where(WorkItemVersionORM.work_item_id == work_item_id)
            .order_by(WorkItemVersionORM.version_number.desc())
            .limit(1)
        )
        latest = (await self._session.execute(stmt)).scalar_one_or_none()
        next_number = (latest or 0) + 1

        row = WorkItemVersionORM()
        row.id = uuid4()
        row.work_item_id = work_item_id
        row.version_number = next_number
        row.snapshot = snapshot
        row.created_by = created_by
        row.created_at = datetime.now(UTC)
        self._session.add(row)
        await self._session.flush()
        return work_item_version_to_domain(row)

    async def get_latest(self, work_item_id: UUID) -> WorkItemVersion | None:
        stmt = (
            select(WorkItemVersionORM)
            .where(WorkItemVersionORM.work_item_id == work_item_id)
            .order_by(WorkItemVersionORM.version_number.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return work_item_version_to_domain(row) if row else None

    async def get(self, version_id: UUID) -> WorkItemVersion | None:
        row = await self._session.get(WorkItemVersionORM, version_id)
        return work_item_version_to_domain(row) if row else None
