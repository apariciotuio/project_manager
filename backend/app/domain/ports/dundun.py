"""Dundun integration port — Protocol, typed errors.

Dundun reference (memory/reference_dundun_api.md):
  - POST /api/v1/webhooks/dundun/chat  — async invoke, returns 202 + {request_id}
  - POST /api/v1/dundun/chat           — sync chat (not used here)
  - No read/history endpoint exists    — Dundun owns thread history; platform persists
                                         locally per-turn for display.

Deviation from design.md §2.1:
  `get_history` is a no-op stub returning [] with a TODO. Dundun has no read API.
  The design assumed a future history endpoint that does not exist in v0.1.1.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class DundunClientError(Exception):
    """Base error for all Dundun client failures."""


class DundunNotFoundError(DundunClientError):
    """Dundun returned 404."""


class DundunAuthError(DundunClientError):
    """Dundun returned 401 or 403."""


class DundunServerError(DundunClientError):
    """Dundun returned 5xx."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class DundunClient(Protocol):
    """Outbound port to Dundun.

    HTTP transport: POST /api/v1/webhooks/dundun/chat (async, 202 + request_id).
    WS transport: Dundun /ws/chat (if/when available — currently undocumented).

    All calls carry:
      Authorization: Bearer <service_key>
      X-Caller-Role: employee
      X-User-Id: <user_id>
    """

    async def invoke_agent(
        self,
        *,
        agent: str,
        user_id: UUID,
        conversation_id: str | None,
        work_item_id: UUID | None,
        callback_url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST /api/v1/webhooks/dundun/chat — async invocation.

        Dundun returns 202 immediately with {"request_id": "<uuid>"}.
        The actual result arrives later via POST to callback_url.
        """
        ...

    def chat_ws(
        self,
        *,
        conversation_id: str,
        user_id: UUID,
        work_item_id: UUID | None,
    ) -> AbstractAsyncContextManager["DundunWSBridge"]:
        """Open a WebSocket to Dundun /ws/chat as a bidirectional channel.

        Returns an async context manager yielding a DundunWSBridge with send/recv.
        Bidirectional — client frames go upstream via .send(), Dundun frames
        come back via .recv() (None on upstream close).

        NOTE: Dundun's public OpenAPI v0.1.1 does not document a WS endpoint.
        This method is specified in design.md §2.2 (WS proxy) for a future
        Dundun WS transport. Implementations SHOULD raise NotImplementedError
        until Dundun publishes the WS contract.
        """
        ...


class DundunWSBridge(Protocol):
    """Bidirectional handle over a live Dundun WS connection."""

    async def send(self, frame: dict[str, Any]) -> None:
        """Push a frame upstream to Dundun (JSON-encoded under the hood)."""
        ...

    async def recv(self) -> dict[str, Any] | None:
        """Pull the next frame from Dundun; None when upstream closes."""
        ...

    async def get_history(self, conversation_id: str) -> list[dict[str, Any]]:
        """Fetch conversation history.

        TODO: Dundun v0.1.1 has no read API (reference_dundun_api.md).
        Platform must persist each turn locally for display.
        This method returns [] until Dundun exposes a history endpoint.
        Callers must NOT rely on this for display — use the local thread store.
        """
        ...
