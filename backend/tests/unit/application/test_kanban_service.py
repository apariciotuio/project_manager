"""EP-09 — Unit tests for KanbanService.

RED phase: fail until KanbanService is implemented.
"""
from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._db_calls: int = 0

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _Item:
    def __init__(
        self,
        id: UUID,
        state: str = "draft",
        owner_id: UUID | None = None,
        parent_work_item_id: UUID | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self.id = id
        self.state = state
        self.title = "T"
        self.type = "story"
        self.owner_id = owner_id or uuid4()
        self.parent_work_item_id = parent_work_item_id
        self.tags = tags or []
        self.completeness_score = 50
        self.attachment_count = 0
        self.updated_at = None


class FakeSession:
    def __init__(self, items: list[object]) -> None:
        self._items = items
        self.call_count = 0

    async def execute(self, stmt: object) -> "_FR":
        self.call_count += 1
        return _FR(self._items)


class _FR:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def scalars(self) -> "_SR":
        return _SR(self._items)

    def all(self) -> list[object]:
        return self._items


class _SR:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


FSM_ORDER = ["draft", "in_clarification", "in_review", "partially_validated", "ready"]


class TestKanbanGroupByState:
    @pytest.mark.asyncio
    async def test_columns_in_fsm_order(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        items = [_Item(uuid4(), state=s) for s in FSM_ORDER]
        session = FakeSession(items=items)
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_board(workspace_id=ws_id, group_by="state")

        col_keys = [c["key"] for c in result["columns"]]
        for state in FSM_ORDER:
            assert state in col_keys
        assert col_keys == FSM_ORDER

    @pytest.mark.asyncio
    async def test_archived_not_in_columns(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        items = [_Item(uuid4(), state="archived")]
        session = FakeSession(items=items)
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_board(workspace_id=ws_id, group_by="state")

        col_keys = [c["key"] for c in result["columns"]]
        assert "archived" not in col_keys

    @pytest.mark.asyncio
    async def test_cards_per_column_capped_at_limit(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        items = [_Item(uuid4(), state="draft") for _ in range(30)]
        session = FakeSession(items=items)
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_board(workspace_id=ws_id, group_by="state", limit=5)

        draft_col = next(c for c in result["columns"] if c["key"] == "draft")
        assert len(draft_col["cards"]) <= 5

    @pytest.mark.asyncio
    async def test_total_count_in_column(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        items = [_Item(uuid4(), state="draft") for _ in range(3)]
        session = FakeSession(items=items)
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_board(workspace_id=ws_id, group_by="state")

        draft_col = next(c for c in result["columns"] if c["key"] == "draft")
        assert draft_col["total_count"] == 3


class TestKanbanGroupByOwner:
    @pytest.mark.asyncio
    async def test_one_column_per_owner(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        uid1 = uuid4()
        uid2 = uuid4()
        items = [
            _Item(uuid4(), owner_id=uid1),
            _Item(uuid4(), owner_id=uid1),
            _Item(uuid4(), owner_id=uid2),
        ]
        session = FakeSession(items=items)
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_board(workspace_id=ws_id, group_by="owner")

        col_keys = {c["key"] for c in result["columns"]}
        assert str(uid1) in col_keys
        assert str(uid2) in col_keys

    @pytest.mark.asyncio
    async def test_unowned_column_present_when_no_owner(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        items = [_Item(uuid4(), owner_id=None)]
        session = FakeSession(items=items)
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]

        # Patch item to have no owner
        items[0].owner_id = None  # type: ignore[assignment]
        result = await svc.get_board(workspace_id=ws_id, group_by="owner")

        col_keys = {c["key"] for c in result["columns"]}
        assert "unowned" in col_keys


class TestKanbanGroupByParent:
    @pytest.mark.asyncio
    async def test_orphan_items_in_no_parent_column(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        items = [_Item(uuid4(), parent_work_item_id=None)]
        session = FakeSession(items=items)
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_board(workspace_id=ws_id, group_by="parent")

        col_keys = {c["key"] for c in result["columns"]}
        assert "no_parent" in col_keys


class TestKanbanValidation:
    @pytest.mark.asyncio
    async def test_limit_over_25_raises_value_error(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        session = FakeSession(items=[])
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="limit"):
            await svc.get_board(workspace_id=ws_id, group_by="state", limit=26)

    @pytest.mark.asyncio
    async def test_invalid_group_by_raises_value_error(self) -> None:
        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        session = FakeSession(items=[])
        cache = FakeCache()
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="group_by"):
            await svc.get_board(workspace_id=ws_id, group_by="invalid")


class TestKanbanCache:
    @pytest.mark.asyncio
    async def test_warm_cache_skips_db(self) -> None:
        import hashlib

        from app.application.services.kanban_service import KanbanService

        ws_id = uuid4()
        cached_data = {
            "columns": [{"key": "draft", "label": "Draft", "total_count": 9, "cards": [], "next_cursor": None}],
            "group_by": "state",
        }
        cache = FakeCache()
        filter_hash = hashlib.sha256(b"state").hexdigest()
        cache_key = f"kanban:{ws_id}:state:{filter_hash}"
        await cache.set(cache_key, json.dumps(cached_data), 30)

        session = FakeSession(items=[])
        svc = KanbanService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_board(workspace_id=ws_id, group_by="state")

        assert result["columns"][0]["total_count"] == 9
        assert session.call_count == 0
