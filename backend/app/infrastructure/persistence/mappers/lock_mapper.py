"""Mappers for SectionLock — EP-17."""
from __future__ import annotations

from app.domain.models.section_lock import SectionLock
from app.infrastructure.persistence.models.orm import SectionLockORM


def lock_to_domain(row: SectionLockORM) -> SectionLock:
    return SectionLock(
        id=row.id,
        section_id=row.section_id,
        work_item_id=row.work_item_id,
        held_by=row.held_by,
        acquired_at=row.acquired_at,
        heartbeat_at=row.heartbeat_at,
        expires_at=row.expires_at,
    )


def lock_to_orm(entity: SectionLock) -> SectionLockORM:
    row = SectionLockORM()
    row.id = entity.id
    row.section_id = entity.section_id
    row.work_item_id = entity.work_item_id
    row.held_by = entity.held_by
    row.acquired_at = entity.acquired_at
    row.heartbeat_at = entity.heartbeat_at
    row.expires_at = entity.expires_at
    return row
