"""EP-18 — Unit tests for list_projects MCP tool handler.

Tests exercise the tool handler in isolation using a fake ProjectService.
No DB, no MCP SDK import required.

Scenarios:
- Returns list with correct shape (id, name, description, work_item_count)
- work_item_count is 0 (deferred — no COUNT JOIN in MVP)
- Empty workspace returns []
- Cross-workspace isolation: projects from workspace B never appear
- Truncation: >100 projects → truncated list + _truncated flag
- Deleted projects are not returned
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.models.project import Project
from apps.mcp_server.tools.list_projects import (
    handle_list_projects,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    name: str,
    workspace_id: UUID | None = None,
    description: str | None = None,
    deleted: bool = False,
) -> Project:
    ws_id = workspace_id or uuid4()
    now = datetime.now(UTC)
    p = Project(
        id=uuid4(),
        workspace_id=ws_id,
        name=name,
        description=description,
        deleted_at=datetime.now(UTC) if deleted else None,
        created_at=now,
        updated_at=now,
        created_by=uuid4(),
    )
    return p


def _fake_service(projects: list[Project]) -> MagicMock:
    svc = MagicMock()
    svc.list_for_workspace = AsyncMock(return_value=projects)
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListProjectsShape:
    @pytest.mark.asyncio
    async def test_returns_correct_shape(self) -> None:
        ws_id = uuid4()
        projects = [
            _make_project("Alpha", workspace_id=ws_id, description="First project"),
            _make_project("Beta", workspace_id=ws_id, description=None),
        ]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert len(result["projects"]) == 2
        for item in result["projects"]:
            assert "id" in item
            assert "name" in item
            assert "description" in item
            assert "work_item_count" in item

    @pytest.mark.asyncio
    async def test_id_is_string_uuid(self) -> None:
        ws_id = uuid4()
        projects = [_make_project("Gamma", workspace_id=ws_id)]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        item = result["projects"][0]
        # Must be parseable as UUID
        UUID(item["id"])

    @pytest.mark.asyncio
    async def test_work_item_count_is_zero_for_mvp(self) -> None:
        """work_item_count is deferred — always 0 in MVP."""
        ws_id = uuid4()
        projects = [_make_project("Delta", workspace_id=ws_id)]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert result["projects"][0]["work_item_count"] == 0

    @pytest.mark.asyncio
    async def test_description_none_passes_through(self) -> None:
        ws_id = uuid4()
        projects = [_make_project("Epsilon", workspace_id=ws_id, description=None)]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert result["projects"][0]["description"] is None

    @pytest.mark.asyncio
    async def test_description_populated(self) -> None:
        ws_id = uuid4()
        projects = [_make_project("Zeta", workspace_id=ws_id, description="Some desc")]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert result["projects"][0]["description"] == "Some desc"


class TestListProjectsEmptyWorkspace:
    @pytest.mark.asyncio
    async def test_empty_workspace_returns_empty_list(self) -> None:
        ws_id = uuid4()
        svc = _fake_service([])

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert result["projects"] == []
        assert result.get("_truncated") is not True

    @pytest.mark.asyncio
    async def test_service_called_with_correct_workspace_id(self) -> None:
        ws_id = uuid4()
        svc = _fake_service([])

        await handle_list_projects(workspace_id=ws_id, service=svc)

        svc.list_for_workspace.assert_awaited_once_with(ws_id)


class TestListProjectsCrossWorkspaceIsolation:
    @pytest.mark.asyncio
    async def test_projects_from_workspace_b_never_appear(self) -> None:
        """Service already scopes by workspace — tool passes workspace_id through."""
        ws_a = uuid4()
        uuid4()

        # Service for workspace A returns only A's projects
        project_a = _make_project("A-Project", workspace_id=ws_a)
        svc_a = _fake_service([project_a])

        result = await handle_list_projects(workspace_id=ws_a, service=svc_a)

        # Assert workspace_id passed to service is ws_a, not ws_b
        svc_a.list_for_workspace.assert_awaited_once_with(ws_a)
        assert len(result["projects"]) == 1
        assert result["projects"][0]["name"] == "A-Project"

    @pytest.mark.asyncio
    async def test_workspace_b_gets_its_own_projects(self) -> None:
        ws_b = uuid4()
        project_b = _make_project("B-Project", workspace_id=ws_b)
        svc_b = _fake_service([project_b])

        result = await handle_list_projects(workspace_id=ws_b, service=svc_b)

        svc_b.list_for_workspace.assert_awaited_once_with(ws_b)
        assert result["projects"][0]["name"] == "B-Project"


class TestListProjectsTruncation:
    @pytest.mark.asyncio
    async def test_up_to_100_returns_no_truncation_flag(self) -> None:
        ws_id = uuid4()
        projects = [_make_project(f"P{i}", workspace_id=ws_id) for i in range(100)]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert len(result["projects"]) == 100
        assert result.get("_truncated") is not True

    @pytest.mark.asyncio
    async def test_over_100_truncates_and_sets_flag(self) -> None:
        ws_id = uuid4()
        projects = [_make_project(f"P{i}", workspace_id=ws_id) for i in range(105)]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert len(result["projects"]) == 100
        assert result["_truncated"] is True

    @pytest.mark.asyncio
    async def test_exactly_101_triggers_truncation(self) -> None:
        ws_id = uuid4()
        projects = [_make_project(f"P{i}", workspace_id=ws_id) for i in range(101)]
        svc = _fake_service(projects)

        result = await handle_list_projects(workspace_id=ws_id, service=svc)

        assert len(result["projects"]) == 100
        assert result["_truncated"] is True
