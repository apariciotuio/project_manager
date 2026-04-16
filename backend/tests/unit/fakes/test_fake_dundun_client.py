"""Unit tests for FakeDundunClient.

Verifies the fake correctly records invocations, yields configured frames,
returns history stubs, and injects errors on demand.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.ports.dundun import DundunAuthError, DundunClientError, DundunNotFoundError
from tests.fakes.fake_dundun_client import FakeDundunClient

USER_ID = uuid4()
CONV_ID = "conv-test-1"
WORK_ITEM_ID = uuid4()
CALLBACK_URL = "http://platform.test/api/v1/dundun/callback"


class TestFakeDundunClientInvokeAgent:
    @pytest.mark.asyncio
    async def test_returns_request_id_dict(self) -> None:
        fake = FakeDundunClient()
        result = await fake.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=CONV_ID,
            work_item_id=WORK_ITEM_ID,
            callback_url=CALLBACK_URL,
            payload={"key": "value"},
        )
        assert "request_id" in result
        assert result["request_id"].startswith("fake-")

    @pytest.mark.asyncio
    async def test_records_invocation(self) -> None:
        fake = FakeDundunClient()
        await fake.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=CONV_ID,
            work_item_id=WORK_ITEM_ID,
            callback_url=CALLBACK_URL,
            payload={"key": "value"},
        )
        assert len(fake.invocations) == 1

    @pytest.mark.asyncio
    async def test_records_multiple_invocations(self) -> None:
        fake = FakeDundunClient()
        for _ in range(3):
            await fake.invoke_agent(
                agent="wm_gap_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )
        assert len(fake.invocations) == 3

    @pytest.mark.asyncio
    async def test_invocation_records_all_fields(self) -> None:
        fake = FakeDundunClient()
        await fake.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=CONV_ID,
            work_item_id=WORK_ITEM_ID,
            callback_url=CALLBACK_URL,
            payload={"data": 1},
        )
        call = fake.invocations[0]
        assert call[0] == "wm_suggestion_agent"  # agent
        assert call[1] == USER_ID                 # user_id
        assert call[2] == CONV_ID                 # conversation_id
        assert call[3] == WORK_ITEM_ID            # work_item_id
        assert call[4] == CALLBACK_URL            # callback_url

    @pytest.mark.asyncio
    async def test_request_ids_are_unique(self) -> None:
        fake = FakeDundunClient()
        results = [
            await fake.invoke_agent(
                agent="agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )
            for _ in range(5)
        ]
        ids = [r["request_id"] for r in results]
        assert len(set(ids)) == 5

    @pytest.mark.asyncio
    async def test_next_error_is_raised_and_cleared(self) -> None:
        fake = FakeDundunClient()
        fake.next_error = DundunAuthError("injected auth error")

        with pytest.raises(DundunAuthError, match="injected auth error"):
            await fake.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

        # Error cleared after raising — next call succeeds
        result = await fake.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=USER_ID,
            conversation_id=None,
            work_item_id=None,
            callback_url=CALLBACK_URL,
            payload={},
        )
        assert "request_id" in result

    @pytest.mark.asyncio
    async def test_next_error_not_recorded_in_invocations(self) -> None:
        fake = FakeDundunClient()
        fake.next_error = DundunNotFoundError("not found")

        with pytest.raises(DundunNotFoundError):
            await fake.invoke_agent(
                agent="wm_suggestion_agent",
                user_id=USER_ID,
                conversation_id=None,
                work_item_id=None,
                callback_url=CALLBACK_URL,
                payload={},
            )

        assert len(fake.invocations) == 0


class TestFakeDundunClientChatWs:
    @pytest.mark.asyncio
    async def test_yields_configured_frames(self) -> None:
        fake = FakeDundunClient()
        expected = [
            {"type": "progress", "content": "thinking"},
            {"type": "response", "content": "done", "message_id": "m1"},
        ]
        fake.chat_frames = list(expected)

        received = []
        async for frame in fake.chat_ws(
            conversation_id=CONV_ID,
            user_id=USER_ID,
            work_item_id=None,
        ):
            received.append(frame)

        assert received == expected

    @pytest.mark.asyncio
    async def test_yields_empty_when_no_frames_configured(self) -> None:
        fake = FakeDundunClient()

        received = []
        async for frame in fake.chat_ws(
            conversation_id=CONV_ID,
            user_id=USER_ID,
            work_item_id=None,
        ):
            received.append(frame)

        assert received == []

    @pytest.mark.asyncio
    async def test_frames_cleared_after_iteration(self) -> None:
        fake = FakeDundunClient()
        fake.chat_frames = [{"type": "progress", "content": "x"}]

        # consume once
        async for _ in fake.chat_ws(
            conversation_id=CONV_ID,
            user_id=USER_ID,
            work_item_id=None,
        ):
            pass

        # second iteration yields nothing (frames are consumed)
        received = []
        async for frame in fake.chat_ws(
            conversation_id=CONV_ID,
            user_id=USER_ID,
            work_item_id=None,
        ):
            received.append(frame)

        assert received == []

    @pytest.mark.asyncio
    async def test_next_error_raised_in_chat_ws(self) -> None:
        fake = FakeDundunClient()
        fake.chat_frames = [{"type": "progress"}]
        fake.next_error = DundunClientError("ws error")

        with pytest.raises(DundunClientError, match="ws error"):
            async for _ in fake.chat_ws(
                conversation_id=CONV_ID,
                user_id=USER_ID,
                work_item_id=None,
            ):
                pass


class TestFakeDundunClientGetHistory:
    @pytest.mark.asyncio
    async def test_returns_empty_by_default(self) -> None:
        fake = FakeDundunClient()
        result = await fake.get_history(CONV_ID)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_configured_history(self) -> None:
        fake = FakeDundunClient()
        fake.history_by_conversation[CONV_ID] = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = await fake.get_history(CONV_ID)
        assert len(result) == 2
        assert result[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_unknown_conversation_id_returns_empty(self) -> None:
        fake = FakeDundunClient()
        fake.history_by_conversation["other-conv"] = [{"role": "user", "content": "x"}]
        result = await fake.get_history("unknown-conv")
        assert result == []
