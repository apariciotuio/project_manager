import hashlib
import json
from typing import Any

from app.domain.ports.dundun import DundunClientError


class FakeDundunClient:
    """In-memory fake implementing DundunClient protocol.

    Usage:
        fake = FakeDundunClient()
        fake.register_response("my_agent", {"key": "val"}, {"result": "ok"})
        result = await fake.invoke_agent("my_agent", {"key": "val"})
    """

    def __init__(self) -> None:
        self._responses: dict[str, dict[str, Any]] = {}
        self._sent_messages: list[dict[str, Any]] = []

    def _payload_key(self, agent_name: str, payload: dict[str, Any]) -> str:
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        return f"{agent_name}:{payload_hash}"

    def register_response(
        self,
        agent_name: str,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        key = self._payload_key(agent_name, payload)
        self._responses[key] = response

    async def invoke_agent(
        self, agent_name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        key = self._payload_key(agent_name, payload)
        if key not in self._responses:
            raise DundunClientError(
                f"No canned response for agent '{agent_name}' with payload {payload!r}. "
                "Register one via register_response()."
            )
        return self._responses[key]

    async def send_message(self, thread_id: str, content: str) -> dict[str, Any]:
        message: dict[str, Any] = {
            "thread_id": thread_id,
            "content": content,
            "status": "sent",
        }
        self._sent_messages.append(message)
        return message

    @property
    def sent_messages(self) -> list[dict[str, Any]]:
        return list(self._sent_messages)
