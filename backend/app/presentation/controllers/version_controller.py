"""EP-07 — Version controller.

Routes:
  GET  /api/v1/work-items/{id}/versions                    — list (cursor-paginated)
  GET  /api/v1/work-items/{id}/versions/{version_number}   — get snapshot
  GET  /api/v1/work-items/{id}/versions/{version_number}/diff — diff vs previous
  GET  /api/v1/work-items/{id}/versions/diff?from=N&to=M   — arbitrary diff
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.application.services.diff_service import DiffService
from app.application.services.versioning_service import VersioningService
from app.domain.models.work_item_version import WorkItemVersion
from app.presentation.dependencies import (
    get_current_user,
    get_diff_service,
    get_versioning_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["versions"])


def _require_workspace(user: CurrentUser) -> UUID:
    if user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    return user.workspace_id


def _version_payload(v: WorkItemVersion) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "work_item_id": str(v.work_item_id),
        "version_number": v.version_number,
        "trigger": v.trigger.value,
        "actor_type": v.actor_type.value,
        "actor_id": str(v.actor_id) if v.actor_id else None,
        "commit_message": v.commit_message,
        "archived": v.archived,
        "created_at": v.created_at.isoformat(),
    }


def _snapshot_payload(v: WorkItemVersion) -> dict[str, Any]:
    return {
        **_version_payload(v),
        "snapshot": v.snapshot,
    }


@router.get("/work-items/{work_item_id}/versions")
async def list_versions(
    work_item_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    before: int | None = Query(default=None),
    include_archived: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
    svc: VersioningService = Depends(get_versioning_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)

    versions = await svc.list_for_work_item(
        work_item_id,
        workspace_id,
        include_archived=include_archived,
        limit=limit + 1,  # extra for has_more
        before_version=before,
    )

    has_more = len(versions) > limit
    if has_more:
        versions = versions[:limit]

    next_cursor: str | None = str(versions[-1].version_number) if has_more and versions else None

    return {
        "data": [_version_payload(v) for v in versions],
        "meta": {"has_more": has_more, "next_cursor": next_cursor},
    }


@router.get("/work-items/{work_item_id}/versions/diff")
async def diff_versions(
    work_item_id: UUID,
    from_version: int = Query(alias="from"),
    to_version: int = Query(alias="to"),
    current_user: CurrentUser = Depends(get_current_user),
    svc: VersioningService = Depends(get_versioning_service),
    diff_svc: DiffService = Depends(get_diff_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)

    if from_version > to_version:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_DIFF_RANGE",
                    "message": "from must be <= to",
                    "details": {},
                }
            },
        )

    v_from = await svc.get_by_number(work_item_id, from_version, workspace_id)
    if v_from is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"version {from_version} not found", "details": {}}},
        )

    v_to = await svc.get_by_number(work_item_id, to_version, workspace_id)
    if v_to is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"version {to_version} not found", "details": {}}},
        )

    diff = diff_svc.compute_version_diff(v_from.snapshot, v_to.snapshot)
    return {
        "data": {
            "from_version": from_version,
            "to_version": to_version,
            **diff,
        }
    }


@router.get("/work-items/{work_item_id}/versions/{version_number}/diff")
async def diff_vs_previous(
    work_item_id: UUID,
    version_number: int,
    current_user: CurrentUser = Depends(get_current_user),
    svc: VersioningService = Depends(get_versioning_service),
    diff_svc: DiffService = Depends(get_diff_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)

    current = await svc.get_by_number(work_item_id, version_number, workspace_id)
    if current is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "version not found", "details": {}}},
        )

    if version_number <= 1:
        # First version: diff against empty snapshot
        empty_snapshot: dict[str, Any] = {
            "schema_version": 1,
            "work_item": {},
            "sections": [],
            "task_node_ids": [],
        }
        diff = diff_svc.compute_version_diff(empty_snapshot, current.snapshot)
    else:
        prev = await svc.get_by_number(work_item_id, version_number - 1, workspace_id)
        prev_snapshot = prev.snapshot if prev else {"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []}
        diff = diff_svc.compute_version_diff(prev_snapshot, current.snapshot)

    return {
        "data": {
            "from_version": version_number - 1 if version_number > 1 else None,
            "to_version": version_number,
            **diff,
        }
    }


@router.get("/work-items/{work_item_id}/versions/{version_number}")
async def get_version(
    work_item_id: UUID,
    version_number: int,
    current_user: CurrentUser = Depends(get_current_user),
    svc: VersioningService = Depends(get_versioning_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)

    version = await svc.get_by_number(work_item_id, version_number, workspace_id)
    if version is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "version not found", "details": {}}},
        )

    return {"data": _snapshot_payload(version)}
