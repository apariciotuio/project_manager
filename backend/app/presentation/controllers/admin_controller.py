"""EP-10 — Admin controller.

Routes:
  GET /api/v1/admin/audit-events  — cursor-paginated audit log (admin-only)
  GET /api/v1/admin/health        — workspace health (work_items by state)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.pagination import InvalidCursorError, PaginationCursor
from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
from app.infrastructure.persistence.models.orm import WorkItemORM
from app.presentation.dependencies import get_current_user, get_scoped_session, require_admin
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


@router.get("/audit-events")
async def list_audit_events(
    cursor: str | None = Query(default=None),
    page_size: int = Query(default=50, ge=1, le=100),
    category: str | None = Query(default=None),
    action: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    # workspace_id presence guaranteed by require_admin
    workspace_id = current_user.workspace_id
    assert workspace_id is not None

    decoded_cursor: PaginationCursor | None = None
    if cursor is not None:
        try:
            decoded_cursor = PaginationCursor.decode(cursor)
        except InvalidCursorError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_CURSOR", "message": str(exc), "details": {}}},
            ) from exc

    repo = AuditRepositoryImpl(session)
    result = await repo.list_cursor(
        workspace_id,
        cursor=decoded_cursor,
        page_size=page_size,
        category=category,
        action=action,
    )

    items = [
        {
            "id": str(r.id),
            "category": r.category,
            "action": r.action,
            "actor_id": str(r.actor_id) if r.actor_id else None,
            "actor_display": r.actor_display,
            "entity_type": r.entity_type,
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "before_value": r.before_value,
            "after_value": r.after_value,
            "context": r.context,
            "created_at": r.created_at.isoformat(),
        }
        for r in result.rows
    ]

    return _ok(
        {
            "items": items,
            "pagination": {
                "cursor": result.next_cursor,
                "has_next": result.has_next,
            },
        }
    )


@router.get("/health")
async def workspace_health(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )

    stmt = (
        select(WorkItemORM.state, func.count().label("count"))
        .where(
            WorkItemORM.workspace_id == current_user.workspace_id,
            WorkItemORM.deleted_at.is_(None),
        )
        .group_by(WorkItemORM.state)
    )
    rows = (await session.execute(stmt)).all()
    by_state: dict[str, int] = {str(row[0]): int(row[1]) for row in rows}

    return _ok(
        {
            "workspace_id": str(current_user.workspace_id),
            "work_items_by_state": by_state,
            "total_active": sum(by_state.values()),
        }
    )
