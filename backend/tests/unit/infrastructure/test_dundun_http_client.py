"""Unit tests for DundunHTTPClient.

Uses httpx.MockTransport for HTTP; monkeypatches websockets.connect for WS.
No real network calls.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.domain.ports.dundun import (
    DundunAuthError,
    DundunClientError,
    DundunNotFoundError,
    DundunServerError,
)
from app.infrastructure.adapters.dundun_http_client import DundunHTTPClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_URL = "http://dundun.test"
SERVICE_KEY = "test-service-key"
TIMEOUT = 5.0

USER_ID = uuid4()
CONV_ID = "conv-abc"
WORK_ITEM_ID = uuid4()
CALLBACK_URL = "http://platform.test/api/v1/dundun/callback"


def _make_client(transport: httpx.AsyncBaseTransport) -> DundunHTTPClient:
    return DundunHTTPClient(
        base_url=BASE_URL,
        service_key=SERVICE_KEY,
        http_timeout=TIMEOUT,
        transport=transport,
    )


def _mock_transport(status: int, body: dict[str, Any]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# invoke_agent — happy path
# ---------------------------------------------------------------------------


class TestInvokeAgentHappyPath:
    @pytest.mark.asyncio
    async def test_returns_request_id_on_202(self) -> None:
        transport = _mock_transport(202, {"request_id": "req-123"})
        client = _make_client(transport)

        result = await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=CONV_ID,
            work_item_id=WORK_ITEM_ID,
            callback_url=CALLBACK_URL,
            payload={"key": "value"},
        )

        assert result == {"request_id": "req-123"}

    @pytest.mark.asyncio
    async def test_posts_to_correct_endpoint(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"request_id": "req-x"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        await client.invoke_agent(
            agent="wm_gap_agent",
            user_id=USER_ID,
            conversation_id=None,
            work_item_id=None,
            callback_url=CALLBACK_URL,
            payload={},
        )

        assert len(captured) == 1
        req = captured[0]
        assert req.method == "POST"
        assert req.url.path == "/api/v1/webhooks/dundun/chat"

    @pytest.mark.asyncio
    async def test_request_headers_carry_auth_and_user(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"request_id": "req-y"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=CONV_ID,
            work_item_id=WORK_ITEM_ID,
            callback_url=CALLBACK_URL,
            payload={},
        )

        req = captured[0]
        assert req.headers["Authorization"] == f"Bearer {SERVICE_KEY}"
        assert req.headers["X-Caller-Role"] == "employee"
        assert req.headers["X-User-Id"] == str(USER_ID)

    @pytest.mark.asyncio
    async def test_callback_url_in_request_body(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"request_id": "req-z"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=CONV_ID,
            work_item_id=WORK_ITEM_ID,
            callback_url=CALLBACK_URL,
            payload={"extra": "data"},
        )

        body = json.loads(captured[0].content)
        assert body["callback_url"] == CALLBACK_URL

    @pytest.mark.asyncio
    async def test_conversation_id_in_body_when_provided(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"request_id": "req-w"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=CONV_ID,
            work_item_id=None,
            callback_url=CALLBACK_URL,
            payload={},
        )

        body = json.loads(captured[0].content)
        assert body["conversation_id"] == CONV_ID

    @pytest.mark.asyncio
    async def test_conversation_id_absent_when_none(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"request_id": "req-v"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=None,
            work_item_id=None,
            callback_url=CALLBACK_URL,
            payload={},
        )

        body = json.loads(captured[0].content)
        assert "conversation_id" not in body

    @pytest.mark.asyncio
    async def test_work_item_id_in_body_when_provided(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"request_id": "req-u"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=None,
            work_item_id=WORK_ITEM_ID,
            callback_url=CALLBACK_URL,
            payload={},
        )

        body = json.loads(captured[0].content)
        assert body["work_item_id"] == str(WORK_ITEM_ID)

    @pytest.mark.asyncio
    async def test_caller_role_in_body(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"request_id": "req-t"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=None,
            work_item_id=None,
            callback_url=CALLBACK_URL,
            payload={},
        )

        body = json.loads(captured[0].content)
        assert body["caller_role"] == "employee"


# ---------------------------------------------------------------------------
# invoke_agent — error mapping
# ---------------------------------------------------------------------------


class TestInvokeAgentErrorMapping:
    @pytest.mark.asyncio
    async def test_401_raises_dundun_auth_error(self) -> None:
        transport = _mock_transport(401, {"detail": "Unauthorized"})
        client = _make_client(transport)

        with pytest.raises(DundunAuthError):
            await client.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

    @pytest.mark.asyncio
    async def test_403_raises_dundun_auth_error(self) -> None:
        transport = _mock_transport(403, {"detail": "Forbidden"})
        client = _make_client(transport)

        with pytest.raises(DundunAuthError):
            await client.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

    @pytest.mark.asyncio
    async def test_404_raises_dundun_not_found_error(self) -> None:
        transport = _mock_transport(404, {"detail": "Not found"})
        client = _make_client(transport)

        with pytest.raises(DundunNotFoundError):
            await client.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

    @pytest.mark.asyncio
    async def test_500_raises_dundun_server_error(self) -> None:
        transport = _mock_transport(500, {"detail": "Internal server error"})
        client = _make_client(transport)

        with pytest.raises(DundunServerError):
            await client.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

    @pytest.mark.asyncio
    async def test_503_raises_dundun_server_error(self) -> None:
        transport = _mock_transport(503, {"detail": "Service unavailable"})
        client = _make_client(transport)

        with pytest.raises(DundunServerError):
            await client.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

    @pytest.mark.asyncio
    async def test_422_raises_base_dundun_client_error(self) -> None:
        transport = _mock_transport(422, {"detail": "Validation error"})
        client = _make_client(transport)

        with pytest.raises(DundunClientError):
            await client.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

    @pytest.mark.asyncio
    async def test_400_raises_base_dundun_client_error(self) -> None:
        transport = _mock_transport(400, {"detail": "Bad request"})
        client = _make_client(transport)

        with pytest.raises(DundunClientError):
            await client.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

    @pytest.mark.asyncio
    async def test_200_also_returns_body(self) -> None:
        """Dundun should return 202 but be lenient — 200 is also accepted."""
        transport = _mock_transport(200, {"request_id": "req-200"})
        client = _make_client(transport)

        result = await client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=None,
            work_item_id=None,
            callback_url=CALLBACK_URL,
            payload={},
        )

        assert result["request_id"] == "req-200"


# ---------------------------------------------------------------------------
# get_history — returns empty list (no Dundun read API)
# ---------------------------------------------------------------------------


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self) -> None:
        """Dundun v0.1.1 has no read API. get_history always returns []."""
        transport = _mock_transport(200, {})  # never called
        client = _make_client(transport)

        result = await client.get_history(CONV_ID)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_regardless_of_conversation_id(self) -> None:
        transport = _mock_transport(200, {})
        client = _make_client(transport)

        result = await client.get_history("any-conversation-id")

        assert result == []


# ---------------------------------------------------------------------------
# Helpers for WS mocking
# ---------------------------------------------------------------------------


class _AsyncWsMock:
    """Minimal async context manager exposing recv() / send() — mirrors the
    subset of the websockets client contract that DundunHTTPClient uses."""

    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)
        self.sent: list[str] = []
        self.connect_uri: str = ""
        self.connect_kwargs: dict[str, Any] = {}

    async def __aenter__(self) -> _AsyncWsMock:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def recv(self) -> str:
        if not self._frames:
            from websockets import ConnectionClosed as _CC
            raise _CC(None, None)
        return self._frames.pop(0)

    async def send(self, payload: str) -> None:
        self.sent.append(payload)


def _make_ws_connect(frames: list[str]) -> tuple[_AsyncWsMock, MagicMock]:
    """Return (ws_mock, connect_mock) pair for use with patch."""
    ws = _AsyncWsMock(frames)

    def connect_factory(uri: str, **kwargs: Any) -> _AsyncWsMock:
        ws.connect_uri = uri
        ws.connect_kwargs = kwargs
        return ws

    return ws, MagicMock(side_effect=connect_factory)


# ---------------------------------------------------------------------------
# chat_ws — async iterator yields frames; close propagates
# ---------------------------------------------------------------------------


class TestChatWs:
    @pytest.mark.asyncio
    async def test_yields_frames_from_upstream(self) -> None:
        raw_frames = [
            '{"type": "progress", "content": "thinking..."}',
            '{"type": "response", "content": "hello", "message_id": "m1"}',
        ]
        ws, connect_mock = _make_ws_connect(raw_frames)

        with patch(
            "app.infrastructure.adapters.dundun_http_client.websockets.connect",
            connect_mock,
        ):
            transport = _mock_transport(200, {})
            client = _make_client(transport)

            received: list[dict[str, Any]] = []
            async with client.chat_ws(
                conversation_id=CONV_ID,
                user_id=USER_ID,
                work_item_id=None,
            ) as bridge:
                while (frame := await bridge.recv()) is not None:
                    received.append(frame)

        assert len(received) == 2
        assert received[0] == {"type": "progress", "content": "thinking..."}
        assert received[1]["message_id"] == "m1"

    @pytest.mark.asyncio
    async def test_ws_connect_called_with_correct_headers(self) -> None:
        ws, connect_mock = _make_ws_connect([])

        with patch(
            "app.infrastructure.adapters.dundun_http_client.websockets.connect",
            connect_mock,
        ):
            transport = _mock_transport(200, {})
            client = _make_client(transport)

            async with client.chat_ws(
                conversation_id=CONV_ID,
                user_id=USER_ID,
                work_item_id=WORK_ITEM_ID,
            ):
                pass

        # connect was called; URI should contain conversation_id
        assert CONV_ID in ws.connect_uri
        # headers should include auth + caller role
        headers = ws.connect_kwargs.get("additional_headers", {})
        assert f"Bearer {SERVICE_KEY}" in headers.get("Authorization", "")
        assert headers.get("X-Caller-Role") == "employee"
        assert headers.get("X-User-Id") == str(USER_ID)

    @pytest.mark.asyncio
    async def test_yields_no_frames_when_empty(self) -> None:
        ws, connect_mock = _make_ws_connect([])

        with patch(
            "app.infrastructure.adapters.dundun_http_client.websockets.connect",
            connect_mock,
        ):
            transport = _mock_transport(200, {})
            client = _make_client(transport)

            received = []
            async with client.chat_ws(
                conversation_id=CONV_ID,
                user_id=USER_ID,
                work_item_id=None,
            ) as bridge:
                while (frame := await bridge.recv()) is not None:
                    received.append(frame)

        assert received == []
