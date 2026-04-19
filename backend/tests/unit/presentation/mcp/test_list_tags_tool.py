"""EP-18 — Unit tests for list_tags MCP tool handler.

Tests exercise the handler in isolation using fakes.
No DB, no MCP SDK required.

Scenarios:
- Happy path: returns list with expected keys per tag
- include_archived=False (default) excludes archived tags
- include_archived=True includes all tags
- Empty workspace returns empty list
- Workspace isolation: only tags for the bound workspace_id are returned
- Tag shape: id, name, color, archived are strings/bools as expected
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.models.tag import Tag
from apps.mcp_server.tools.list_tags import handle_list_tags

WORKSPACE_ID = uuid4()
OTHER_WORKSPACE_ID = uuid4()

_EXPECTED_TAG_KEYS = {"id", "name", "color", "archived"}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeTagRepository:
    def __init__(self, tags: list[Tag] | None = None) -> None:
        self._tags = tags or []

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Tag]:
        return [t for t in self._tags if t.workspace_id == workspace_id and not t.is_archived]

    async def list_all_for_workspace(self, workspace_id: UUID) -> list[Tag]:
        return [t for t in self._tags if t.workspace_id == workspace_id]


def _make_tag(
    workspace_id: UUID = WORKSPACE_ID,
    name: str = "feature",
    archived: bool = False,
    color: str | None = "#ff0000",
) -> Tag:
    tag = Tag(
        id=uuid4(),
        workspace_id=workspace_id,
        name=name,
        color=color,
        archived_at=datetime.now(UTC) if archived else None,
        created_at=datetime.now(UTC),
        created_by=uuid4(),
    )
    return tag


# ---------------------------------------------------------------------------
# Shape tests
# ---------------------------------------------------------------------------


class TestListTagsShape:
    @pytest.mark.asyncio
    async def test_happy_path_returns_list(self) -> None:
        tag = _make_tag()
        repo = FakeTagRepository([tag])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_tag_has_required_keys(self) -> None:
        tag = _make_tag()
        repo = FakeTagRepository([tag])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result
        assert _EXPECTED_TAG_KEYS.issubset(set(result[0].keys()))

    @pytest.mark.asyncio
    async def test_tag_id_is_string(self) -> None:
        tag = _make_tag()
        repo = FakeTagRepository([tag])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result[0]["id"], str)
        assert result[0]["id"] == str(tag.id)

    @pytest.mark.asyncio
    async def test_tag_archived_false_for_active(self) -> None:
        tag = _make_tag(archived=False)
        repo = FakeTagRepository([tag])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["archived"] is False

    @pytest.mark.asyncio
    async def test_tag_color_none_allowed(self) -> None:
        tag = _make_tag(color=None)
        repo = FakeTagRepository([tag])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["color"] is None


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------


class TestListTagsFilter:
    @pytest.mark.asyncio
    async def test_include_archived_false_excludes_archived(self) -> None:
        active = _make_tag(name="active", archived=False)
        archived = _make_tag(name="archived", archived=True)
        repo = FakeTagRepository([active, archived])

        result = await handle_list_tags(
            arguments={"include_archived": False},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert len(result) == 1
        assert result[0]["name"] == "active"

    @pytest.mark.asyncio
    async def test_default_excludes_archived(self) -> None:
        active = _make_tag(name="active", archived=False)
        archived = _make_tag(name="archived", archived=True)
        repo = FakeTagRepository([active, archived])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_include_archived_true_returns_all(self) -> None:
        active = _make_tag(name="active", archived=False)
        archived = _make_tag(name="archived", archived=True)
        repo = FakeTagRepository([active, archived])

        result = await handle_list_tags(
            arguments={"include_archived": True},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_archived_tag_has_archived_true(self) -> None:
        tag = _make_tag(archived=True)
        repo = FakeTagRepository([tag])

        result = await handle_list_tags(
            arguments={"include_archived": True},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["archived"] is True


# ---------------------------------------------------------------------------
# Empty + isolation
# ---------------------------------------------------------------------------


class TestListTagsIsolation:
    @pytest.mark.asyncio
    async def test_empty_workspace_returns_empty_list(self) -> None:
        repo = FakeTagRepository([])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_other_workspace_tags_not_returned(self) -> None:
        tag_own = _make_tag(workspace_id=WORKSPACE_ID, name="own")
        tag_other = _make_tag(workspace_id=OTHER_WORKSPACE_ID, name="other")
        repo = FakeTagRepository([tag_own, tag_other])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        names = [r["name"] for r in result]
        assert "own" in names
        assert "other" not in names

    @pytest.mark.asyncio
    async def test_workspace_id_boundary_empty_other_ws(self) -> None:
        tag = _make_tag(workspace_id=OTHER_WORKSPACE_ID)
        repo = FakeTagRepository([tag])

        result = await handle_list_tags(
            arguments={},
            tag_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == []
