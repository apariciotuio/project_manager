"""Mapper between StoredGapFinding domain entity and GapFindingORM."""

from __future__ import annotations

from app.domain.models.gap_finding import GapSeverity, StoredGapFinding
from app.infrastructure.persistence.models.orm import GapFindingORM


def to_domain(row: GapFindingORM) -> StoredGapFinding:
    return StoredGapFinding(
        id=row.id,
        workspace_id=row.workspace_id,
        work_item_id=row.work_item_id,
        dimension=row.dimension,
        severity=GapSeverity(row.severity),
        message=row.message,
        source=row.source,  # type: ignore[arg-type]  # validated by DB CHECK
        dundun_request_id=row.dundun_request_id,
        created_at=row.created_at,
        invalidated_at=row.invalidated_at,
    )


def to_orm(entity: StoredGapFinding) -> GapFindingORM:
    row = GapFindingORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.work_item_id = entity.work_item_id
    row.source = entity.source
    row.severity = entity.severity.value
    row.dimension = entity.dimension
    row.message = entity.message
    row.dundun_request_id = entity.dundun_request_id
    row.created_at = entity.created_at
    row.invalidated_at = entity.invalidated_at
    return row
