"""EP-13 — Puppet HTTP adapter.

Implements the PuppetClient protocol (app.domain.ports.puppet) against the
real Puppet RAG service.

TODO: Puppet platform-ingestion endpoints (/api/v1/documents upsert/delete) are
PENDING on the Puppet side as of 2026-04-17. The real implementation is stubbed
below. Once Puppet publishes their document-ingestion surface, replace the
_upsert_document / _delete_document stubs with real HTTP calls.
Reference: memory/reference_puppet_api.md — category-isolated Qdrant RAG,
no workspace concept; isolation via category = 'wm_<workspace_id>'.

Outbound auth: Authorization: Bearer <api_key>
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.domain.ports.puppet import PuppetClientError

logger = logging.getLogger(__name__)

_SEARCH_PATH = "/api/v1/search"
_HEALTH_PATH = "/api/v1/health"
# TODO: replace with real paths once Puppet publishes platform-ingestion endpoints
_DOCUMENTS_PATH = "/api/v1/documents"


class PuppetNotImplementedError(PuppetClientError):
    """Raised when Puppet returns 404 on a platform-ingestion endpoint (still PENDING)."""


class PuppetHTTPClient:
    """Real HTTP implementation of the PuppetClient protocol.

    Args:
        base_url: Puppet service base URL.
        api_key: Bearer token for outbound auth.
        http_timeout: Seconds before HTTP calls time out.
        transport: Optional httpx transport override (tests).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        http_timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http_timeout = http_timeout
        self._transport = transport

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._http_timeout,
            transport=self._transport,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _map_error(self, status: int, body: str) -> PuppetClientError:
        if status == 404:
            return PuppetNotImplementedError(
                f"Puppet platform-ingestion endpoint returned 404 — endpoint likely PENDING. "
                f"body={body!r}"
            )
        return PuppetClientError(f"Puppet error {status}: {body}")

    async def index_document(self, doc_id: str, content: str, tags: list[str]) -> dict[str, Any]:
        """Upsert a document into Puppet.

        TODO: Puppet platform-ingestion (/api/v1/documents) is PENDING.
        When available, this should PUT/POST to _DOCUMENTS_PATH with
        { doc_id, content, tags, category }.
        """
        body = {"doc_id": doc_id, "content": content, "tags": tags}
        async with self._build_client() as client:
            response = await client.put(
                f"{_DOCUMENTS_PATH}/{doc_id}",
                content=json.dumps(body).encode(),
                headers=self._headers(),
            )
        if response.status_code == 404:
            raise self._map_error(response.status_code, response.text)
        if response.status_code >= 400:
            raise PuppetClientError(
                f"Puppet index_document error {response.status_code}: {response.text}"
            )
        return response.json()  # type: ignore[no-any-return]

    async def delete_document(self, doc_id: str) -> None:
        """Delete a document from Puppet. 404 is treated as already-gone (idempotent).

        TODO: Puppet DELETE /api/v1/documents/{doc_id} is PENDING.
        """
        async with self._build_client() as client:
            response = await client.delete(
                f"{_DOCUMENTS_PATH}/{doc_id}",
                headers=self._headers(),
            )
        if response.status_code == 404:
            logger.debug("puppet delete_document: 404 for doc_id=%s — treating as gone", doc_id)
            return
        if response.status_code >= 400:
            raise PuppetClientError(
                f"Puppet delete_document error {response.status_code}: {response.text}"
            )

    async def search(self, query: str, tags: list[str]) -> list[dict[str, Any]]:
        """Search Puppet with category/tag filtering."""
        body: dict[str, Any] = {"query": query, "tags": tags}
        async with self._build_client() as client:
            response = await client.post(
                _SEARCH_PATH,
                content=json.dumps(body).encode(),
                headers=self._headers(),
            )
        if response.status_code >= 400:
            raise PuppetClientError(f"Puppet search error {response.status_code}: {response.text}")
        data: list[dict[str, Any]] = response.json()
        return data

    async def health(self) -> dict[str, Any]:
        async with self._build_client() as client:
            response = await client.get(_HEALTH_PATH, headers=self._headers())
        if response.status_code >= 400:
            raise PuppetClientError(f"Puppet health error {response.status_code}: {response.text}")
        return response.json()  # type: ignore[no-any-return]
