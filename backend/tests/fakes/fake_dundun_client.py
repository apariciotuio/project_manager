"""In-memory deterministic fake implementing the DundunClient protocol.

Used in all service and controller tests as the only fake at the Dundun boundary.
No real HTTP or WebSocket connections are made.

Usage:
    fake = FakeDundunClient()

    # Inspect recorded invocations
    await fake.invoke_agent(agent="wm_suggestion_agent", user_id=..., ...)
    assert fake.invocations[0][0] == "wm_suggestion_agent"

    # Configure WS frames
    fake.chat_frames = [{"type": "progress", "content": "thinking"}]
    async for frame in fake.chat_ws(...):
        ...  # yields configured frames

    # Configure history
    fake.history_by_conversation["conv-1"] = [{"role": "user", "content": "hello"}]

    # Inject errors
    fake.next_error = DundunAuthError("test error")
    await fake.invoke_agent(...)  # raises DundunAuthError
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4


class FakeDundunClient:
    """Deterministic in-memory fake for DundunClient."""

    def __init__(self) -> None:
        # Records of (agent, user_id, conversation_id, work_item_id, callback_url, payload)
        self.invocations: list[tuple[str, UUID, str | None, UUID | None, str, dict[str, Any]]] = []
        # Frames to yield from chat_ws; cleared after each iteration
        self.chat_frames: list[dict[str, Any]] = []
        # Synthetic history store per conversation_id
        self.history_by_conversation: dict[str, list[dict[str, Any]]] = {}
        # Set to raise on the next call (any method); cleared after raising
        self.next_error: Exception | None = None

    def _check_error(self) -> None:
        if self.next_error is not None:
            err = self.next_error
            self.next_error = None
            raise err

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
        self._check_error()
        self.invocations.append(
            (agent, user_id, conversation_id, work_item_id, callback_url, payload)
        )
        return {"request_id": f"fake-{uuid4()}"}

    async def chat_ws(
        self,
        *,
        conversation_id: str,  # noqa: ARG002
        user_id: UUID,  # noqa: ARG002
        work_item_id: UUID | None,  # noqa: ARG002
    ) -> AsyncIterator[dict[str, Any]]:
        self._check_error()
        frames = list(self.chat_frames)
        self.chat_frames = []
        for frame in frames:
            yield frame

    async def get_history(self, conversation_id: str) -> list[dict[str, Any]]:
        self._check_error()
        return list(self.history_by_conversation.get(conversation_id, []))
