"""Mapper between OwnershipRecord domain value object and OwnershipHistoryORM.

previous_owner_id is nullable in the DB (NULL = creation/initial assignment) but
UUID-typed in the domain VO. The mapper handles this mismatch at the boundary.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.value_objects.ownership_record import OwnershipRecord
from app.infrastructure.persistence.models.orm import OwnershipHistoryORM


def to_domain(row: OwnershipHistoryORM) -> OwnershipRecord:
    # For creation events where previous_owner_id is NULL we use new_owner_id as a
    # sentinel — callers that care about "was there a previous owner" should check
    # previous_owner_id == new_owner_id.
    return OwnershipRecord(
        work_item_id=row.work_item_id,
        previous_owner_id=row.previous_owner_id if row.previous_owner_id is not None else row.new_owner_id,
        new_owner_id=row.new_owner_id,
        changed_by=row.changed_by,
        changed_at=row.changed_at,
        reason=row.reason,
    )


def to_orm(
    record: OwnershipRecord,
    *,
    workspace_id: UUID,
    previous_owner_id: UUID | None = None,
) -> OwnershipHistoryORM:
    """Build a new OwnershipHistoryORM insert row.

    previous_owner_id: pass None for the initial creation event (no prior owner).
    """
    row = OwnershipHistoryORM()
    row.work_item_id = record.work_item_id
    row.workspace_id = workspace_id
    row.previous_owner_id = previous_owner_id
    row.new_owner_id = record.new_owner_id
    row.changed_by = record.changed_by
    row.changed_at = record.changed_at
    row.reason = record.reason
    return row
