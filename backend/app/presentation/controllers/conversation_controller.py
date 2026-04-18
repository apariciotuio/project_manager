"""EP-03 Phase 7 — Conversation thread controller + WS proxy.

Routes:
  GET    /api/v1/threads                       — list user's threads
  POST   /api/v1/threads                       — get-or-create thread
  GET    /api/v1/threads/{thread_id}           — get thread pointer
  GET    /api/v1/threads/{thread_id}/history   — fetch history from Dundun
  DELETE /api/v1/threads/{thread_id}           — archive (soft-delete)
  WS     /ws/conversations/{thread_id}         — bidirectional proxy to Dundun

EP-22 extensions:
  - fe_to_upstream: attaches server-authoritative context.sections_snapshot
  - upstream_to_fe: validates signals.suggested_sections; drops invalid items
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi import status as http_status
from fastapi.responses import JSONResponse

from app.application.services.conversation_service import (
    ConversationService,
    ThreadNotFoundError,
)
from app.infrastructure.adapters.jwt_adapter import (
    JwtAdapter,
    TokenExpiredError,
    TokenInvalidError,
)
from app.presentation.dependencies import (
    get_conversation_service,
    get_current_user,
    get_dundun_client,
    get_jwt_adapter,
    get_thread_repo_for_ws,
)
from app.presentation.middleware.auth_middleware import CurrentUser
from app.presentation.schemas.dundun_signals import validate_signals
from app.presentation.schemas.thread_schemas import CreateThreadRequest, ThreadResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversations"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _not_found(resource: str = "thread") -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": f"{resource} not found", "details": {}}},
    )


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get("/threads")
async def list_threads(
    work_item_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> dict[str, Any]:
    threads = await service.list_for_user(current_user.id, work_item_id=work_item_id)
    return _ok([ThreadResponse.from_domain(t).model_dump(mode="json") for t in threads])


@router.post("/threads")
async def get_or_create_thread(
    body: CreateThreadRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> JSONResponse:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },  # noqa: E501
        )
    thread = await service.get_or_create_thread(
        current_user.workspace_id, current_user.id, body.work_item_id
    )
    data = ThreadResponse.from_domain(thread).model_dump(mode="json")
    return JSONResponse(
        status_code=http_status.HTTP_201_CREATED,
        content=_ok(data, "thread"),
    )


def _require_workspace(current_user: CurrentUser) -> UUID:
    """Return workspace_id from the JWT claims or raise 401.

    Thread endpoints are workspace-scoped — the JWT must carry the active
    workspace_id. Same pattern used by get_or_create_thread (SEC-AUTH-001).
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },  # noqa: E501
        )
    return current_user.workspace_id


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)
    try:
        thread = await service.get_thread_for_user(thread_id, current_user.id, workspace_id)
    except ThreadNotFoundError as exc:
        raise _not_found() from exc
    return _ok(ThreadResponse.from_domain(thread).model_dump(mode="json"))


@router.get("/threads/{thread_id}/history")
async def get_thread_history(
    thread_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)
    try:
        await service.get_thread_for_user(thread_id, current_user.id, workspace_id)
    except ThreadNotFoundError as exc:
        raise _not_found() from exc

    history = await service.get_history(thread_id)
    return _ok(history)


@router.delete("/threads/{thread_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def archive_thread(
    thread_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> None:
    workspace_id = _require_workspace(current_user)
    try:
        await service.get_thread_for_user(thread_id, current_user.id, workspace_id)
    except ThreadNotFoundError as exc:
        raise _not_found() from exc

    await service.archive_thread(thread_id)


# ---------------------------------------------------------------------------
# WebSocket proxy
# ---------------------------------------------------------------------------


async def _authenticate_ws(token: str | None, jwt_adapter: JwtAdapter) -> CurrentUser | None:
    """Validate JWT from WS query param. Returns CurrentUser or None."""
    if not token:
        return None

    try:
        claims = jwt_adapter.decode(token)
        workspace_id = UUID(claims["workspace_id"]) if claims.get("workspace_id") else None
        return CurrentUser(
            id=UUID(claims["sub"]),
            email=claims["email"],
            workspace_id=workspace_id,
            is_superadmin=bool(claims.get("is_superadmin", False)),
        )
    except (TokenExpiredError, TokenInvalidError, KeyError, ValueError):
        return None


@router.websocket("/ws/conversations/{thread_id}")
async def conversation_ws(
    websocket: WebSocket,
    thread_id: UUID,
    token: str | None = Query(default=None),
    jwt_adapter: JwtAdapter = Depends(get_jwt_adapter),
) -> None:
    """Bidirectional WebSocket proxy between the FE and Dundun /ws/chat."""
    # 1. Authenticate
    user = await _authenticate_ws(token, jwt_adapter)
    if user is None:
        await websocket.close(code=4401)
        return

    # 2. Resolve thread and verify IDOR (user + workspace scope — SEC-AUTH-001)
    async for thread_repo in get_thread_repo_for_ws():
        thread = await thread_repo.get_by_id(thread_id)
        if thread is None or thread.user_id != user.id or thread.workspace_id != user.workspace_id:
            await websocket.close(code=4403)
            return

        # 3. Accept the upgrade
        await websocket.accept()

        # 4. Open upstream to Dundun and pump frames bidirectionally
        dundun = get_dundun_client()
        try:
            # Build snapshot provider once per WS connection (not per message).
            # Deferred imports per MEMORY.md lru_cache trap.
            from app.infrastructure.persistence.database import (  # noqa: PLC0415
                get_session_factory,
            )
            from app.infrastructure.persistence.section_repository_impl import (  # noqa: PLC0415
                SectionRepositoryImpl,
            )

            _conn_session_factory = get_session_factory()

            async def _get_snapshot(
                wid: UUID | None,
                _factory: object = _conn_session_factory,
            ) -> dict[str, str] | None:
                if wid is None:
                    return None
                async with _factory() as _s:  # type: ignore[operator]
                    repo = SectionRepositoryImpl(_s)
                    sections = await repo.get_by_work_item(wid)
                    return {sec.section_type.value: sec.content for sec in sections}

            async with _UpstreamWS(
                dundun, thread.dundun_conversation_id, user.id, thread.work_item_id
            ) as upstream:
                await _pump(
                    websocket,
                    upstream,
                    work_item_id=thread.work_item_id,
                    snapshot_provider=_get_snapshot,
                )
        except WebSocketDisconnect:
            logger.debug("ws_proxy: client disconnected thread=%s", thread_id)
        except Exception:
            logger.exception("ws_proxy: unexpected error thread=%s", thread_id)
            with contextlib.suppress(Exception):
                await websocket.close(code=1011)
        return


class _UpstreamWS:
    """Async context manager wrapping DundunClient.chat_ws (now a bidirectional
    context manager yielding a bridge with send/recv).

    Previous version treated chat_ws as a pull-only async generator and called
    asend() for upstream frames — a no-op on a generator that never consumes
    its sent values. This wrapper now defers to the bridge's real send/recv.
    """

    def __init__(
        self,
        dundun_client: Any,
        conversation_id: str,
        user_id: UUID,
        work_item_id: UUID | None,
    ) -> None:
        self._dundun = dundun_client
        self._conv_id = conversation_id
        self._user_id = user_id
        self._work_item_id = work_item_id
        self._cm: Any = None
        self._bridge: Any = None

    async def __aenter__(self) -> _UpstreamWS:
        self._cm = self._dundun.chat_ws(
            conversation_id=self._conv_id,
            user_id=self._user_id,
            work_item_id=self._work_item_id,
        )
        self._bridge = await self._cm.__aenter__()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._cm is not None:
            with contextlib.suppress(Exception):
                await self._cm.__aexit__(exc_type, exc, tb)

    async def receive(self) -> dict[str, Any] | None:
        """Get next frame from upstream; returns None when Dundun closes."""
        if self._bridge is None:
            return None
        return await self._bridge.recv()

    async def send(self, frame: dict[str, Any]) -> None:
        """Forward a client frame upstream."""
        if self._bridge is None:
            return
        try:
            await self._bridge.send(frame)
        except Exception:
            logger.debug("ws_proxy: upstream send error", exc_info=True)


_SnapshotProvider = Callable[[UUID | None], Awaitable[dict[str, str] | None]]

_SNAPSHOT_WARN_THRESHOLD = 50 * 1024  # 50 KB


async def _enrich_outbound_frame(
    frame: dict[str, Any],
    *,
    work_item_id: UUID | None,
    snapshot_provider: _SnapshotProvider,
) -> dict[str, Any]:
    """Attach server-authoritative context.sections_snapshot to outbound message frames.

    Only type==message frames are enriched. General threads (work_item_id=None)
    are forwarded verbatim. BE overrides any FE-supplied snapshot value.
    """
    if frame.get("type") != "message":
        return frame
    if work_item_id is None:
        return frame

    snapshot = await snapshot_provider(work_item_id)
    if snapshot is None:
        return frame

    # Log size observability (EP-22 §3.4)
    size = len(json.dumps(snapshot).encode())
    if size > _SNAPSHOT_WARN_THRESHOLD:
        logger.warning(
            "sections_snapshot_oversized work_item_id=%s size_bytes=%d",
            work_item_id,
            size,
        )
    else:
        logger.debug(
            "sections_snapshot_attached work_item_id=%s size_bytes=%d",
            work_item_id,
            size,
        )

    enriched = dict(frame)
    existing_context = dict(enriched.get("context") or {})
    existing_context["sections_snapshot"] = snapshot
    enriched["context"] = existing_context
    return enriched


def _enrich_inbound_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """Validate signals.suggested_sections on inbound response frames.

    Non-response frames are forwarded verbatim. Invalid items in
    suggested_sections are dropped with a warn log. All-invalid → empty list
    (field always present). Uses validate_signals from dundun_signals.
    """
    if frame.get("type") != "response":
        return frame

    raw_signals = frame.get("signals") or {}
    validated = validate_signals(raw_signals)

    enriched = dict(frame)
    enriched["signals"] = validated
    return enriched


async def _pump(
    websocket: WebSocket,
    upstream: _UpstreamWS,
    *,
    work_item_id: UUID | None = None,
    snapshot_provider: _SnapshotProvider | None = None,
) -> None:
    """Drive frames in both directions until either side closes."""

    async def fe_to_upstream() -> None:
        try:
            while True:
                msg = await websocket.receive_json()
                if snapshot_provider is not None:
                    msg = await _enrich_outbound_frame(
                        msg,
                        work_item_id=work_item_id,
                        snapshot_provider=snapshot_provider,
                    )
                await upstream.send(msg)
        except WebSocketDisconnect:
            pass

    async def upstream_to_fe() -> None:
        while True:
            frame = await upstream.receive()
            if frame is None:
                break
            frame = _enrich_inbound_frame(frame)
            await websocket.send_json(frame)

    tasks = [
        asyncio.create_task(fe_to_upstream()),
        asyncio.create_task(upstream_to_fe()),
    ]
    try:
        _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in _done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                raise exc
    except (asyncio.CancelledError, WebSocketDisconnect):
        pass
