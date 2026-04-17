"""EP-05 — Task hierarchy + dependency controller.

Routes:
  GET    /api/v1/work-items/{id}/task-tree
  POST   /api/v1/work-items/{id}/tasks
  PATCH  /api/v1/tasks/{id}
  DELETE /api/v1/tasks/{id}
  POST   /api/v1/tasks/{id}/start
  POST   /api/v1/tasks/{id}/mark-done
  POST   /api/v1/tasks/{id}/reopen
  POST   /api/v1/tasks/{id}/dependencies
  DELETE /api/v1/dependencies/{id}
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.completion_rollup_service import CompletionRollupService
from app.application.services.dependency_service import (
    DependencyCycleError,
    DependencyNotFoundError,
    DependencyService,
)
from app.application.services.task_service import (
    TaskNodeNotFoundError,
    TaskService,
)
from app.domain.models.task_node import PredecessorNotDoneError, TaskNode
from app.presentation.dependencies import get_current_user, get_dependency_service, get_task_service
from app.presentation.middleware.auth_middleware import CurrentUser

_rollup_service = CompletionRollupService()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateTaskRequest(BaseModel):
    title: str
    parent_id: UUID | None = None
    display_order: int = 0
    description: str = ""


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    description: str | None = None


class MoveTaskRequest(BaseModel):
    new_parent_id: UUID | None = None
    new_order: int = 0


class AddDependencyRequest(BaseModel):
    target_id: UUID


class SplitTaskRequest(BaseModel):
    title_a: str
    title_b: str
    description_a: str = ""
    description_b: str = ""


class MergeTaskRequest(BaseModel):
    source_ids: list[UUID]
    title: str
    description: str = ""


class ReorderTaskRequest(BaseModel):
    ordered_ids: list[UUID]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _node_payload(node: TaskNode) -> dict[str, Any]:
    return {
        "id": str(node.id),
        "work_item_id": str(node.work_item_id),
        "parent_id": str(node.parent_id) if node.parent_id else None,
        "title": node.title,
        "description": node.description,
        "display_order": node.display_order,
        "status": node.status.value,
        "generation_source": node.generation_source.value,
        "materialized_path": node.materialized_path,
        "created_at": node.created_at.isoformat(),
        "updated_at": node.updated_at.isoformat(),
        "created_by": str(node.created_by),
        "updated_by": str(node.updated_by),
    }


def _build_tree(
    nodes: list[TaskNode],
    rollup_map: dict[UUID, str] | None = None,
) -> list[dict[str, Any]]:
    """Convert flat list (ordered by materialized_path) into nested structure.

    rollup_map: optional pre-computed {node_id: rollup_status} injected per node.
    """
    children_map: dict[UUID | None, list[TaskNode]] = {}
    for node in nodes:
        children_map.setdefault(node.parent_id, []).append(node)

    def _nest(parent_id: UUID | None) -> list[dict[str, Any]]:
        result = []
        for n in children_map.get(parent_id, []):
            payload = _node_payload(n)
            if rollup_map is not None:
                payload["rollup_status"] = rollup_map.get(n.id, "draft")
            payload["children"] = _nest(n.id)
            result.append(payload)
        return result

    return _nest(None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/work-items/{work_item_id}/task-tree")
async def get_task_tree(
    work_item_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    nodes = await service.get_tree(work_item_id)
    # Compute rollup_status for each node (pure, on-demand)
    enriched = _rollup_service.enrich_tree(nodes)
    rollup_map = {UUID(e["id"]): e["rollup_status"] for e in enriched}
    return _ok({"work_item_id": str(work_item_id), "tree": _build_tree(nodes, rollup_map)})


@router.get("/tasks/{node_id}")
async def get_task(
    node_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    """Return single task node with breadcrumb [{id, title}, …] from root to parent."""
    result = await service.get_node_with_breadcrumb(node_id)
    if result is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"task {node_id} not found", "details": {}}},
        )
    node, breadcrumb = result
    payload = _node_payload(node)
    payload["breadcrumb"] = breadcrumb
    return _ok(payload)


@router.get("/work-items/{work_item_id}/tasks/search")
async def search_tasks(
    work_item_id: UUID,
    q: str = "",
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    """Search tasks by title within a work item. Returns flat list [{id, title}]. q < 2 chars → []."""
    results = await service.search_tasks(work_item_id=work_item_id, q=q)
    return _ok(results)


@router.post("/work-items/{work_item_id}/tasks", status_code=http_status.HTTP_201_CREATED)
async def create_task(
    work_item_id: UUID,
    body: CreateTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        node = await service.create_node(
            work_item_id=work_item_id,
            parent_id=body.parent_id,
            title=body.title,
            display_order=body.display_order,
            actor_id=current_user.id,
            description=body.description,
        )
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_node_payload(node))


@router.patch("/tasks/{node_id}")
async def update_task(
    node_id: UUID,
    body: UpdateTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        node = await service.update_node(
            node_id=node_id,
            title=body.title,
            description=body.description,
            actor_id=current_user.id,
        )
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_node_payload(node))


@router.delete("/tasks/{node_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_task(
    node_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> None:
    try:
        await service.delete_node(node_id)
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc


@router.post("/tasks/{node_id}/start")
async def start_task(
    node_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        node = await service.start(node_id=node_id, actor_id=current_user.id)
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_node_payload(node))


@router.post("/tasks/{node_id}/mark-done")
async def mark_done_task(
    node_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        node = await service.mark_done(node_id=node_id, actor_id=current_user.id)
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except PredecessorNotDoneError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "PREDECESSOR_NOT_DONE",
                    "message": str(exc),
                    "details": {},
                }
            },
        ) from exc
    return _ok(_node_payload(node))


@router.post("/tasks/{node_id}/reopen")
async def reopen_task(
    node_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        node = await service.reopen(node_id=node_id, actor_id=current_user.id)
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_node_payload(node))


@router.post("/tasks/{node_id}/split", status_code=http_status.HTTP_201_CREATED)
async def split_task(
    node_id: UUID,
    body: SplitTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        a, b = await service.split(
            task_id=node_id,
            title_a=body.title_a,
            title_b=body.title_b,
            description_a=body.description_a,
            description_b=body.description_b,
            actor_id=current_user.id,
        )
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        ) from exc
    return _ok({"a": _node_payload(a), "b": _node_payload(b)})


@router.post(
    "/work-items/{work_item_id}/tasks/merge",
    status_code=http_status.HTTP_201_CREATED,
)
async def merge_tasks(
    work_item_id: UUID,
    body: MergeTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        merged = await service.merge(
            source_ids=body.source_ids,
            title=body.title,
            description=body.description,
            actor_id=current_user.id,
        )
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_node_payload(merged))


@router.patch("/work-items/{work_item_id}/tasks/reorder")
async def reorder_tasks(
    work_item_id: UUID,
    body: ReorderTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> dict[str, Any]:
    try:
        nodes = await service.reorder(
            work_item_id=work_item_id,
            ordered_ids=body.ordered_ids,
            actor_id=current_user.id,
        )
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_TASK_IDS", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        ) from exc
    return _ok({"ordered_ids": [str(n.id) for n in nodes]})


@router.get("/work-items/{work_item_id}/tasks/blocked")
async def get_blocked_tasks(
    work_item_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    dep_service: DependencyService = Depends(get_dependency_service),
) -> dict[str, Any]:
    blocked = await dep_service.get_blocked_tasks(work_item_id)
    return _ok([
        {
            "id": str(item["id"]),
            "title": item["title"],
            "status": item["status"],
            "blocked_by": [str(b) for b in item["blocked_by"]],
        }
        for item in blocked
    ])


@router.post("/tasks/{node_id}/dependencies", status_code=http_status.HTTP_201_CREATED)
async def add_dependency(
    node_id: UUID,
    body: AddDependencyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    dep_service: DependencyService = Depends(get_dependency_service),
) -> dict[str, Any]:
    try:
        dep = await dep_service.add(
            source_id=node_id,
            target_id=body.target_id,
            actor_id=current_user.id,
        )
    except TaskNodeNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except DependencyCycleError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "CYCLE_DETECTED",
                    "message": str(exc),
                    "details": {},
                }
            },
        ) from exc
    return _ok(
        {
            "id": str(dep.id),
            "source_id": str(dep.source_id),
            "target_id": str(dep.target_id),
            "created_at": dep.created_at.isoformat(),
            "created_by": str(dep.created_by),
        }
    )


@router.delete("/dependencies/{dep_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def remove_dependency(
    dep_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    dep_service: DependencyService = Depends(get_dependency_service),
) -> None:
    try:
        await dep_service.remove(dep_id)
    except DependencyNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
