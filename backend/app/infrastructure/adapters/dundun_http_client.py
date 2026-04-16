"""Dundun HTTP + WebSocket adapter.

HTTP transport: POST /api/v1/webhooks/dundun/chat (async invoke, 202 + request_id).
WS transport: connects to Dundun /ws/chat and yields frames as dicts.

Dundun API reference (memory/reference_dundun_api.md v0.1.1):
  - No read/history endpoint. get_history() returns [] and logs a TODO.
  - Async invoke endpoint: POST /api/v1/webhooks/dundun/chat
  - WS endpoint not documented in v0.1.1; chat_ws is speculative per design §2.2.

All outbound calls carry:
  Authorization: Bearer <service_key>
  X-Caller-Role: employee
  X-User-Id: <user_id>
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import httpx
import websockets

from app.domain.ports.dundun import (
    DundunAuthError,
    DundunClientError,
    DundunNotFoundError,
    DundunServerError,
)

logger = logging.getLogger(__name__)

_INVOKE_PATH = "/api/v1/webhooks/dundun/chat"
_WS_CHAT_PATH = "/ws/chat"


def _map_http_error(status: int, body: str) -> DundunClientError:
    if status in (401, 403):
        return DundunAuthError(f"Dundun auth error {status}: {body}")
    if status == 404:
        return DundunNotFoundError(f"Dundun not found: {body}")
    if status >= 500:
        return DundunServerError(f"Dundun server error {status}: {body}")
    return DundunClientError(f"Dundun client error {status}: {body}")


class DundunHTTPClient:
    """Real implementation of the DundunClient protocol.

    Args:
        base_url: Dundun service base URL, e.g. "http://dundun.internal".
        service_key: Bearer token for outbound auth (DUNDUN_SERVICE_KEY).
        http_timeout: Seconds before HTTP calls time out (DUNDUN_HTTP_TIMEOUT).
        transport: Optional httpx transport override (used in tests).
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_key: str,
        http_timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._http_timeout = http_timeout
        self._transport = transport
        # WebSocket base URL: swap http(s) → ws(s)
        self._ws_base = (
            base_url.rstrip("/")
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        )

    def _build_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._http_timeout,
            transport=self._transport,
        )

    def _common_headers(self, user_id: UUID) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._service_key}",
            "X-Caller-Role": "employee",
            "X-User-Id": str(user_id),
            "Content-Type": "application/json",
        }

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

        Dundun body contract (reference_dundun_api.md):
          conversation_id, request_id (omitted — Dundun generates it),
          message (= serialized payload), callback_url, caller_role,
          customer_id (= user_id), source_workflow_id (= agent name).
        """
        body: dict[str, Any] = {
            "callback_url": callback_url,
            "caller_role": "employee",
            "source_workflow_id": agent,
            "customer_id": str(user_id),
        }
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        if work_item_id is not None:
            body["work_item_id"] = str(work_item_id)
        # Merge caller payload last (must not override reserved keys above)
        body.update({k: v for k, v in payload.items() if k not in body})

        async with self._build_http_client() as client:
            response = await client.post(
                _INVOKE_PATH,
                content=json.dumps(body).encode(),
                headers=self._common_headers(user_id),
            )

        if response.status_code >= 400:
            raise _map_http_error(response.status_code, response.text)

        return response.json()  # type: ignore[no-any-return]

    async def get_history(self, conversation_id: str) -> list[dict[str, Any]]:
        """Return conversation history.

        TODO: Dundun v0.1.1 has no read API (reference_dundun_api.md).
        The platform must persist each user/assistant exchange locally.
        This returns [] until Dundun publishes a history endpoint.
        """
        logger.debug(
            "get_history called for conversation_id=%s — Dundun has no read API; returning []",
            conversation_id,
        )
        return []

    async def chat_ws(
        self,
        *,
        conversation_id: str,
        user_id: UUID,
        work_item_id: UUID | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Connect to Dundun /ws/chat and yield parsed JSON frames.

        NOTE: Dundun v0.1.1 does not document a WS endpoint. This is speculative
        per design.md §2.2 (WS proxy). The implementation will be updated when
        Dundun publishes the WS contract.

        Frames are expected to be JSON strings; non-JSON frames are logged and skipped.
        """
        ws_url = f"{self._ws_base}{_WS_CHAT_PATH}?conversation_id={conversation_id}"
        extra_headers = {
            "Authorization": f"Bearer {self._service_key}",
            "X-Caller-Role": "employee",
            "X-User-Id": str(user_id),
        }
        if work_item_id is not None:
            extra_headers["X-Work-Item-Id"] = str(work_item_id)

        async with websockets.connect(ws_url, additional_headers=extra_headers) as ws:
            async for raw_frame in ws:
                if isinstance(raw_frame, bytes):
                    raw_frame = raw_frame.decode("utf-8")
                try:
                    frame: dict[str, Any] = json.loads(raw_frame)
                    yield frame
                except json.JSONDecodeError:
                    logger.warning("Dundun WS: non-JSON frame received, skipping: %r", raw_frame)
