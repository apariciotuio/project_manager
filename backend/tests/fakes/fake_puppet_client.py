from typing import Any


class FakePuppetClient:
    """In-memory fake implementing PuppetClient protocol.

    Search does substring match filtered by tags intersection.
    delete_document is idempotent (404 → no-op) matching PuppetHTTPClient behaviour.
    """

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        # Track calls for test assertions
        self.index_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []

    def register_doc(self, doc_id: str, content: str, tags: list[str]) -> None:
        self._docs[doc_id] = {"doc_id": doc_id, "content": content, "tags": tags}

    async def index_document(
        self, doc_id: str, content: str, tags: list[str]
    ) -> dict[str, Any]:
        self._docs[doc_id] = {"doc_id": doc_id, "content": content, "tags": tags}
        self.index_calls.append({"doc_id": doc_id, "content": content, "tags": tags})
        return {"doc_id": doc_id, "status": "indexed"}

    async def search(self, query: str, tags: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for doc in self._docs.values():
            doc_tags: list[str] = doc["tags"]
            tag_match = not tags or bool(set(tags) & set(doc_tags))
            content_match = query.lower() in doc["content"].lower()
            if tag_match and content_match:
                results.append(doc)
        return results

    async def delete_document(self, doc_id: str) -> None:
        """Idempotent — silently ignores missing doc_id (mirrors PuppetHTTPClient 404 handling)."""
        self.delete_calls.append(doc_id)
        self._docs.pop(doc_id, None)

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "doc_count": len(self._docs)}
