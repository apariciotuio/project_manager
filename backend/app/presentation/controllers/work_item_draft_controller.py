"""EP-02 — WorkItemDraft controller (pre-creation drafts).

Routes:
  GET  /work-item-drafts          — get current draft for user+workspace
  POST /work-item-drafts          — upsert draft (versioned)
  DELETE /work-item-drafts/{id}  — discard draft
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.application.services.draft_service import DraftService
from app.domain.models.work_item_draft import WorkItemDraft
from app.domain.value_objects.draft_conflict import DraftConflict
from app.presentation.dependencies import get_current_user, get_draft_service_unscoped
from app.presentation.middleware.auth_middleware import CurrentUser
from app.presentation.schemas.draft_schemas import (
    UpsertDraftRequest,
    WorkItemDraftResponse,
)

router = APIRouter(tags=["work-item-drafts"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


@router.get("/work-item-drafts")
async def get_work_item_draft(
    workspace_id: UUID = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: DraftService = Depends(get_draft_service_unscoped),
) -> dict[str, Any]:
    draft = await service.get_pre_creation_draft(current_user.id, workspace_id)
    if draft is None:
        return _ok(None)
    return _ok(WorkItemDraftResponse.from_domain(draft).model_dump(mode="json"))


@router.post("/work-item-drafts")
async def upsert_work_item_draft(
    body: UpsertDraftRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: DraftService = Depends(get_draft_service_unscoped),
) -> dict[str, Any]:
    from fastapi import HTTPException

    result = await service.upsert_pre_creation_draft(
        user_id=current_user.id,
        workspace_id=body.workspace_id,
        data=body.data,
        local_version=body.local_version,
    )

    if isinstance(result, DraftConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "DRAFT_VERSION_CONFLICT",
                    "message": "Server has a newer version of this draft",
                    "details": {
                        "server_version": result.server_version,
                        "server_data": result.server_data,
                    },
                }
            },
        )

    assert isinstance(result, WorkItemDraft)
    return _ok({"draft_id": str(result.id), "local_version": result.local_version})


@router.delete("/work-item-drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_item_draft(
    draft_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: DraftService = Depends(get_draft_service_unscoped),
) -> Response:
    await service.discard_pre_creation_draft(user_id=current_user.id, draft_id=draft_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
