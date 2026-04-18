from typing import Any, Protocol


class PuppetClientError(Exception):
    pass


class PuppetClient(Protocol):
    async def index_document(
        self, doc_id: str, content: str, tags: list[str]
    ) -> dict[str, Any]: ...

    async def search(self, query: str, tags: list[str]) -> list[dict[str, Any]]: ...

    async def delete_document(self, doc_id: str) -> None: ...

    async def health(self) -> dict[str, Any]: ...
