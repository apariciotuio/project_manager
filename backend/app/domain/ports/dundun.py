from typing import Any, Protocol


class DundunClientError(Exception):
    pass


class DundunClient(Protocol):
    async def invoke_agent(self, agent_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    async def send_message(self, thread_id: str, content: str) -> dict[str, Any]:
        ...
