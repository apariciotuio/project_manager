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
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4


class FakeDundunClient:
    """Deterministic in-memory fake for DundunClient."""

    def __init__(self) -> None:
        # Records of (agent, user_id, conversation_id, work_item_id, callback_url, payload)
        self.invocations: list[tuple[str, UUID, str | None, UUID | None, str, dict[str, Any]]] = []
        # Frames seeded for the next chat_ws bridge to deliver via recv()
        self.chat_frames: list[dict[str, Any]] = []
        # Every bridge opened via chat_ws is tracked so tests can inspect .sent
        self.ws_bridges: list[FakeDundunWSBridge] = []
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

    @asynccontextmanager
    async def chat_ws(
        self,
        *,
        conversation_id: str,  # noqa: ARG002
        user_id: UUID,  # noqa: ARG002
        work_item_id: UUID | None,  # noqa: ARG002
    ) -> AsyncIterator[FakeDundunWSBridge]:
        self._check_error()
        frames = list(self.chat_frames)
        self.chat_frames = []
        bridge = FakeDundunWSBridge(downstream_frames=frames)
        self.ws_bridges.append(bridge)
        try:
            yield bridge
        finally:
            pass


    async def get_history(self, conversation_id: str) -> list[dict[str, Any]]:
        self._check_error()
        return list(self.history_by_conversation.get(conversation_id, []))

    def queue_ws_response_with_signals(self, signals: dict[str, Any]) -> None:
        """Seed a response frame with the given signals into chat_frames.

        Integration tests use this to simulate Dundun emitting structured signals
        (e.g. suggested_sections) so the inbound proxy validation path can be exercised.
        """
        self.chat_frames.append(
            {
                "type": "response",
                "response": "Assistant reply with signals.",
                "signals": signals,
            }
        )


class FakeDundunWSBridge:
    """Bidirectional fake handle — tests can seed downstream frames and inspect
    client-side frames captured via send()."""

    def __init__(self, *, downstream_frames: list[dict[str, Any]]) -> None:
        self.downstream: list[dict[str, Any]] = list(downstream_frames)
        self.sent: list[dict[str, Any]] = []

    async def send(self, frame: dict[str, Any]) -> None:
        self.sent.append(frame)

    async def recv(self) -> dict[str, Any] | None:
        if not self.downstream:
            return None
        return self.downstream.pop(0)
