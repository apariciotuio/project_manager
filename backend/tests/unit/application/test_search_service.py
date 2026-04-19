"""EP-09 — Unit tests for SearchService.

Tests use FakePuppetClient — no real Puppet, no DB.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.search_service import PuppetNotAvailableError, SearchService
from app.domain.ports.puppet import PuppetClientError
from tests.fakes.fake_puppet_client import FakePuppetClient


def _ws() -> uuid4:
    return uuid4()


def _service(puppet: FakePuppetClient | None = None) -> SearchService:
    return SearchService(puppet_client=puppet or FakePuppetClient())


def _ws_tag(ws_id) -> str:
    return f"wm_{ws_id}"


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_basic_search_returns_results(self) -> None:
        puppet = FakePuppetClient()
        ws = _ws()
        puppet.register_doc("doc-1", "authentication flow design", tags=[_ws_tag(ws)])
        puppet.register_doc("doc-2", "database schema migration", tags=[_ws_tag(ws)])

        svc = _service(puppet)
        result = await svc.search_work_items(workspace_id=ws, query="authentication")
        assert result.source == "puppet"
        assert len(result.items) == 1
        assert result.items[0]["doc_id"] == "doc-1"
        assert result.took_ms >= 0

    @pytest.mark.asyncio
    async def test_limit_applied(self) -> None:
        puppet = FakePuppetClient()
        ws = _ws()
        for i in range(10):
            puppet.register_doc(f"doc-{i}", f"feature {i}", tags=[_ws_tag(ws)])

        svc = _service(puppet)
        result = await svc.search_work_items(workspace_id=ws, query="feature", limit=3)
        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_zero_hits_returns_empty_result(self) -> None:
        puppet = FakePuppetClient()
        ws = _ws()
        # No docs registered
        svc = _service(puppet)
        result = await svc.search_work_items(workspace_id=ws, query="xyzzy nothing found")
        assert result.source == "puppet"
        assert result.items == []
        assert result.total == 0


class TestWorkspaceIsolation:
    @pytest.mark.asyncio
    async def test_workspace_tag_always_enforced(self) -> None:
        puppet = FakePuppetClient()
        ws1 = _ws()
        ws2 = _ws()
        puppet.register_doc("ws1-doc", "auth flow", tags=[_ws_tag(ws1)])
        puppet.register_doc("ws2-doc", "auth flow", tags=[_ws_tag(ws2)])

        svc = _service(puppet)
        result = await svc.search_work_items(workspace_id=ws1, query="auth")
        ids = {i["doc_id"] for i in result.items}
        assert "ws1-doc" in ids
        assert "ws2-doc" not in ids  # workspace isolation enforced

    @pytest.mark.asyncio
    async def test_additional_tags_prefixed_with_workspace(self) -> None:
        """Additional facet tags must be namespaced under workspace tag."""
        puppet = FakePuppetClient()
        ws = _ws()
        ws_tag = _ws_tag(ws)
        # Doc tagged with workspace + extra tag
        puppet.register_doc("d1", "draft item", tags=[ws_tag, f"{ws_tag}:state:draft"])

        svc = _service(puppet)
        result = await svc.search_work_items(
            workspace_id=ws,
            query="draft",
            additional_tags=["state:draft"],  # caller supplies without ws prefix
        )
        # The service must prefix additional_tags with ws_tag
        # FakePuppetClient uses tag intersection, so the doc must match ALL tags
        # Since we prefix "state:draft" → "wm_{ws}:state:draft", and doc has that tag, it matches
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_caller_cannot_bypass_workspace_with_foreign_category(self) -> None:
        puppet = FakePuppetClient()
        ws = _ws()
        other_ws = _ws()
        puppet.register_doc("foreign", "secret", tags=[_ws_tag(other_ws)])

        svc = _service(puppet)
        # Even passing the other workspace's tag as additional_tags, it gets prefixed and won't match
        result = await svc.search_work_items(
            workspace_id=ws,
            query="secret",
            additional_tags=[_ws_tag(other_ws)],
        )
        assert result.items == []


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_short_query_raises_value_error(self) -> None:
        svc = _service()
        ws = _ws()
        with pytest.raises(ValueError, match="at least 2 characters"):
            await svc.search_work_items(workspace_id=ws, query="x")

    @pytest.mark.asyncio
    async def test_empty_query_raises_value_error(self) -> None:
        svc = _service()
        ws = _ws()
        with pytest.raises(ValueError):
            await svc.search_work_items(workspace_id=ws, query="")

    @pytest.mark.asyncio
    async def test_whitespace_only_query_raises_value_error(self) -> None:
        svc = _service()
        ws = _ws()
        with pytest.raises(ValueError):
            await svc.search_work_items(workspace_id=ws, query="   ")

    @pytest.mark.asyncio
    async def test_puppet_error_raises_not_available(self) -> None:
        class FailingPuppet:
            async def search(self, query, tags):
                raise PuppetClientError("Puppet is down")

            async def index_document(self, *a, **kw):
                pass

            async def delete_document(self, *a, **kw):
                pass

            async def health(self):
                return {"status": "error"}

        svc = SearchService(puppet_client=FailingPuppet())  # type: ignore[arg-type]
        ws = _ws()
        with pytest.raises(PuppetNotAvailableError):
            await svc.search_work_items(workspace_id=ws, query="some query")
