"""EP-10 — Admin controller.

Routes:
  GET /api/v1/admin/audit-events  — paginated audit log
  GET /api/v1/admin/health        — workspace health (work_items by state)
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.orm import AuditEventORM, WorkItemORM
from app.presentation.dependencies import get_current_user, get_scoped_session
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


@router.get("/audit-events")
async def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    category: str | None = Query(default=None),
    action: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )

    conditions = [AuditEventORM.workspace_id == current_user.workspace_id]
    if category is not None:
        conditions.append(AuditEventORM.category == category)
    if action is not None:
        conditions.append(AuditEventORM.action == action)

    count_stmt = select(func.count()).where(*conditions).select_from(AuditEventORM)
    total: int = (await session.execute(count_stmt)).scalar_one()

    rows_stmt = (
        select(AuditEventORM)
        .where(*conditions)
        .order_by(AuditEventORM.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(rows_stmt)).scalars().all()

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
        for r in rows
    ]

    return _ok(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
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
    by_state = {row.state: row.count for row in rows}

    return _ok(
        {
            "workspace_id": str(current_user.workspace_id),
            "work_items_by_state": by_state,
            "total_active": sum(by_state.values()),
        }
    )
