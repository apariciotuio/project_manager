"""EP-09 — Unit tests for SavedSearchService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.saved_search_service import (
    SavedSearchForbidden,
    SavedSearchNotFound,
    SavedSearchService,
)
from app.domain.models.saved_search import SavedSearch


class FakeSavedSearchRepo:
    def __init__(self) -> None:
        self._store: dict = {}

    async def create(self, saved_search: SavedSearch) -> SavedSearch:
        self._store[saved_search.id] = saved_search
        return saved_search

    async def get(self, saved_search_id) -> SavedSearch | None:
        return self._store.get(saved_search_id)

    async def list_for_user(self, user_id, workspace_id) -> list[SavedSearch]:
        return [
            s
            for s in self._store.values()
            if s.workspace_id == workspace_id and (s.user_id == user_id or s.is_shared)
        ]

    async def list_for_workspace(self, workspace_id) -> list[SavedSearch]:
        return [s for s in self._store.values() if s.workspace_id == workspace_id]

    async def update(self, saved_search: SavedSearch) -> SavedSearch:
        self._store[saved_search.id] = saved_search
        return saved_search

    async def delete(self, saved_search_id) -> None:
        self._store.pop(saved_search_id, None)


def _service() -> tuple[SavedSearchService, FakeSavedSearchRepo]:
    repo = FakeSavedSearchRepo()
    return SavedSearchService(repo=repo), repo


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_happy_path(self) -> None:
        svc, _ = _service()
        uid = uuid4()
        wsid = uuid4()
        result = await svc.create(
            user_id=uid, workspace_id=wsid, name="my search", query_params={"state": ["draft"]}
        )
        assert result.name == "my search"
        assert result.query_params == {"state": ["draft"]}
        assert result.user_id == uid
        assert result.workspace_id == wsid
        assert result.is_shared is False

    @pytest.mark.asyncio
    async def test_create_shared(self) -> None:
        svc, _ = _service()
        result = await svc.create(
            user_id=uuid4(), workspace_id=uuid4(), name="shared", is_shared=True
        )
        assert result.is_shared is True

    @pytest.mark.asyncio
    async def test_create_empty_name_raises(self) -> None:
        svc, _ = _service()
        with pytest.raises(ValueError):
            await svc.create(user_id=uuid4(), workspace_id=uuid4(), name="  ")


class TestList:
    @pytest.mark.asyncio
    async def test_list_returns_own_and_shared(self) -> None:
        svc, repo = _service()
        uid1 = uuid4()
        uid2 = uuid4()
        wsid = uuid4()
        # uid1's own
        s1 = await svc.create(user_id=uid1, workspace_id=wsid, name="mine")
        # uid2's shared
        s2 = await svc.create(user_id=uid2, workspace_id=wsid, name="shared one", is_shared=True)
        # uid2's private
        await svc.create(user_id=uid2, workspace_id=wsid, name="private")

        results = await svc.list(user_id=uid1, workspace_id=wsid)
        ids = {r.id for r in results}
        assert s1.id in ids
        assert s2.id in ids
        # uid2's private should NOT appear
        assert len(ids) == 2

    @pytest.mark.asyncio
    async def test_list_different_workspace_excluded(self) -> None:
        svc, _ = _service()
        uid = uuid4()
        ws1 = uuid4()
        ws2 = uuid4()
        await svc.create(user_id=uid, workspace_id=ws1, name="ws1 search")
        results = await svc.list(user_id=uid, workspace_id=ws2)
        assert results == []


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_name(self) -> None:
        svc, _ = _service()
        uid = uuid4()
        entity = await svc.create(user_id=uid, workspace_id=uuid4(), name="old name")
        updated = await svc.update(
            saved_search_id=entity.id, requesting_user_id=uid, name="new name"
        )
        assert updated.name == "new name"

    @pytest.mark.asyncio
    async def test_update_is_shared(self) -> None:
        svc, _ = _service()
        uid = uuid4()
        entity = await svc.create(user_id=uid, workspace_id=uuid4(), name="x")
        updated = await svc.update(
            saved_search_id=entity.id, requesting_user_id=uid, is_shared=True
        )
        assert updated.is_shared is True

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self) -> None:
        svc, _ = _service()
        with pytest.raises(SavedSearchNotFound):
            await svc.update(saved_search_id=uuid4(), requesting_user_id=uuid4())

    @pytest.mark.asyncio
    async def test_update_other_user_forbidden(self) -> None:
        svc, _ = _service()
        uid = uuid4()
        entity = await svc.create(user_id=uid, workspace_id=uuid4(), name="x")
        with pytest.raises(SavedSearchForbidden):
            await svc.update(saved_search_id=entity.id, requesting_user_id=uuid4())


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_own(self) -> None:
        svc, _ = _service()
        uid = uuid4()
        entity = await svc.create(user_id=uid, workspace_id=uuid4(), name="to delete")
        await svc.delete(saved_search_id=entity.id, requesting_user_id=uid)
        assert await svc.get(entity.id) is None

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self) -> None:
        svc, _ = _service()
        with pytest.raises(SavedSearchNotFound):
            await svc.delete(saved_search_id=uuid4(), requesting_user_id=uuid4())

    @pytest.mark.asyncio
    async def test_delete_other_user_forbidden(self) -> None:
        svc, _ = _service()
        uid = uuid4()
        entity = await svc.create(user_id=uid, workspace_id=uuid4(), name="x")
        with pytest.raises(SavedSearchForbidden):
            await svc.delete(saved_search_id=entity.id, requesting_user_id=uuid4())
