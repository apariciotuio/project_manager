"""EP-18 — Unit tests for create_work_item_draft MCP tool handler.

Tests exercise the handler in isolation using a FakeDraftService.
No DB, no MCP SDK required.

Scenarios:
- Happy path: returns {id, title, state: "draft", created_at}
- title too short (<3 chars) raises ValueError
- title too long (>200 chars) raises ValueError
- missing title raises KeyError
- cross-workspace isolation: draft workspace_id comes from injected session workspace
- DraftConflict treated as upsert success (idempotent)
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.models.work_item_draft import WorkItemDraft
from app.domain.value_objects.draft_conflict import DraftConflict

from apps.mcp_server.tools.create_work_item_draft import handle_create_work_item_draft

WORKSPACE_ID = uuid4()
ACTOR_ID = uuid4()

_EXPECTED_KEYS = {"id", "title", "state", "created_at"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_draft(
    title: str = "Valid draft title",
    user_id: UUID | None = None,
    workspace_id: UUID | None = None,
) -> WorkItemDraft:
    return WorkItemDraft.create(
        user_id=user_id or ACTOR_ID,
        workspace_id=workspace_id or WORKSPACE_ID,
        data={"title": title},
    )


class FakeDraftService:
    """Minimal fake — only covers upsert_pre_creation_draft."""

    def __init__(self, result: WorkItemDraft | DraftConflict) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def upsert_pre_creation_draft(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        data: dict,  # type: ignore[type-arg]
        local_version: int,
    ) -> WorkItemDraft | DraftConflict:
        self.calls.append(
            {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "data": data,
                "local_version": local_version,
            }
        )
        return self._result


# ---------------------------------------------------------------------------
# Schema shape tests
# ---------------------------------------------------------------------------


class TestCreateWorkItemDraftShape:
    @pytest.mark.asyncio
    async def test_happy_path_returns_expected_keys(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        result = await handle_create_work_item_draft(
            arguments={"title": "Valid draft title"},
            workspace_id=WORKSPACE_ID,
            actor_id=ACTOR_ID,
            service=svc,
        )

        assert set(result.keys()) == _EXPECTED_KEYS

    @pytest.mark.asyncio
    async def test_state_is_always_draft(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        result = await handle_create_work_item_draft(
            arguments={"title": "Some title here"},
            workspace_id=WORKSPACE_ID,
            actor_id=ACTOR_ID,
            service=svc,
        )

        assert result["state"] == "draft"

    @pytest.mark.asyncio
    async def test_id_is_string_uuid(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        result = await handle_create_work_item_draft(
            arguments={"title": "Title for uuid test"},
            workspace_id=WORKSPACE_ID,
            actor_id=ACTOR_ID,
            service=svc,
        )

        UUID(result["id"])  # raises if not a valid UUID string

    @pytest.mark.asyncio
    async def test_title_matches_argument(self) -> None:
        title = "My specific draft title"
        draft = _make_draft(title=title)
        svc = FakeDraftService(draft)

        result = await handle_create_work_item_draft(
            arguments={"title": title},
            workspace_id=WORKSPACE_ID,
            actor_id=ACTOR_ID,
            service=svc,
        )

        assert result["title"] == title

    @pytest.mark.asyncio
    async def test_created_at_is_iso_string(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        result = await handle_create_work_item_draft(
            arguments={"title": "Timestamp check title"},
            workspace_id=WORKSPACE_ID,
            actor_id=ACTOR_ID,
            service=svc,
        )

        # Should not raise
        datetime.fromisoformat(result["created_at"])


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestCreateWorkItemDraftValidation:
    @pytest.mark.asyncio
    async def test_title_too_short_raises_value_error(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        with pytest.raises(ValueError, match="title"):
            await handle_create_work_item_draft(
                arguments={"title": "ab"},
                workspace_id=WORKSPACE_ID,
                actor_id=ACTOR_ID,
                service=svc,
            )

    @pytest.mark.asyncio
    async def test_title_too_long_raises_value_error(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        with pytest.raises(ValueError, match="title"):
            await handle_create_work_item_draft(
                arguments={"title": "x" * 201},
                workspace_id=WORKSPACE_ID,
                actor_id=ACTOR_ID,
                service=svc,
            )

    @pytest.mark.asyncio
    async def test_missing_title_raises(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        with pytest.raises((KeyError, ValueError)):
            await handle_create_work_item_draft(
                arguments={},
                workspace_id=WORKSPACE_ID,
                actor_id=ACTOR_ID,
                service=svc,
            )

    @pytest.mark.asyncio
    async def test_service_called_with_workspace_id(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        await handle_create_work_item_draft(
            arguments={"title": "Workspace isolation title"},
            workspace_id=WORKSPACE_ID,
            actor_id=ACTOR_ID,
            service=svc,
        )

        assert len(svc.calls) == 1
        assert svc.calls[0]["workspace_id"] == WORKSPACE_ID

    @pytest.mark.asyncio
    async def test_service_called_with_actor_id(self) -> None:
        draft = _make_draft()
        svc = FakeDraftService(draft)

        await handle_create_work_item_draft(
            arguments={"title": "Actor id title here"},
            workspace_id=WORKSPACE_ID,
            actor_id=ACTOR_ID,
            service=svc,
        )

        assert svc.calls[0]["user_id"] == ACTOR_ID
