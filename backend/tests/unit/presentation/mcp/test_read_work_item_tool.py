"""EP-18 — Unit tests for read_work_item MCP tool handler.

Tests exercise the handler in isolation using mock WorkItemService and
inline FakeSectionRepository. No DB, no MCP SDK required.

Scenarios:
- Returns work item with all expected fields in correct types
- Sections are included with id, title, content_markdown
- Long section content is truncated at 2000 chars with "..." marker
- Returns {error: "not_found"} for unknown work item id
- Returns {error: "not_found"} for id in different workspace (cross-workspace isolation)
- Schema shape: all expected top-level keys present
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.exceptions import WorkItemNotFoundError
from app.domain.models.section import Section
from app.domain.models.section_type import SectionType
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.work_item_type import WorkItemType
from apps.mcp_server.tools.read_work_item import handle_read_work_item

WORKSPACE_ID = uuid4()
_EXPECTED_KEYS = {
    "id",
    "title",
    "description",
    "state",
    "type",
    "priority",
    "owner",
    "project",
    "completeness_score",
    "external_jira_key",
    "sections",
    "created_at",
    "updated_at",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_work_item(
    workspace_id: UUID | None = None,
    title: str = "Test work item title",
    description: str | None = "Some description",
    priority: Priority | None = None,
    external_jira_key: str | None = None,
) -> WorkItem:
    uid = uuid4()
    item = WorkItem.create(
        title=title,
        type=WorkItemType.TASK,
        owner_id=uid,
        creator_id=uid,
        project_id=uid,
        description=description,
    )
    if external_jira_key is not None:
        item.external_jira_key = external_jira_key
    if priority is not None:
        item.priority = priority
    return item


def _make_section(
    work_item_id: UUID,
    section_type: SectionType = SectionType.SUMMARY,
    content: str = "Some section content",
    display_order: int = 0,
) -> Section:
    uid = uuid4()
    return Section.create(
        work_item_id=work_item_id,
        section_type=section_type,
        display_order=display_order,
        is_required=True,
        created_by=uid,
        content=content,
    )


def _fake_service_found(item: WorkItem) -> MagicMock:
    svc = MagicMock()
    svc.get = AsyncMock(return_value=item)
    return svc


def _fake_service_not_found() -> MagicMock:
    svc = MagicMock()
    svc.get = AsyncMock(side_effect=WorkItemNotFoundError(uuid4()))
    return svc


class FakeSectionRepository:
    """In-memory section repository for tests."""

    def __init__(self, sections: list[Section] | None = None) -> None:
        self._sections = sections or []

    async def get_by_work_item(self, work_item_id: UUID) -> list[Section]:
        return [s for s in self._sections if s.work_item_id == work_item_id]


# ---------------------------------------------------------------------------
# Schema shape tests
# ---------------------------------------------------------------------------


class TestReadWorkItemShape:
    @pytest.mark.asyncio
    async def test_all_expected_top_level_keys_present(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert set(result.keys()) == _EXPECTED_KEYS

    @pytest.mark.asyncio
    async def test_id_is_string_uuid(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        UUID(result["id"])  # raises if not valid UUID string

    @pytest.mark.asyncio
    async def test_state_and_type_are_strings(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert isinstance(result["state"], str)
        assert isinstance(result["type"], str)

    @pytest.mark.asyncio
    async def test_completeness_score_is_int(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert isinstance(result["completeness_score"], int)

    @pytest.mark.asyncio
    async def test_sections_is_list(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert isinstance(result["sections"], list)

    @pytest.mark.asyncio
    async def test_timestamps_are_strings(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)


# ---------------------------------------------------------------------------
# Section tests
# ---------------------------------------------------------------------------


class TestReadWorkItemSections:
    @pytest.mark.asyncio
    async def test_sections_included_with_expected_keys(self) -> None:
        item = _make_work_item()
        section = _make_section(item.id, content="Section body here")
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository([section])

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert len(result["sections"]) == 1
        s = result["sections"][0]
        assert set(s.keys()) == {"id", "title", "content_markdown"}

    @pytest.mark.asyncio
    async def test_section_content_included_verbatim_when_short(self) -> None:
        item = _make_work_item()
        content = "Short content that fits."
        section = _make_section(item.id, content=content)
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository([section])

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["sections"][0]["content_markdown"] == content

    @pytest.mark.asyncio
    async def test_section_content_truncated_at_2000_chars_with_marker(self) -> None:
        item = _make_work_item()
        long_content = "x" * 2500
        section = _make_section(item.id, content=long_content)
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository([section])

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        truncated = result["sections"][0]["content_markdown"]
        assert len(truncated) <= 2003  # 2000 chars + "..."
        assert truncated.endswith("...")
        assert truncated.startswith("x" * 100)

    @pytest.mark.asyncio
    async def test_content_exactly_2000_chars_not_truncated(self) -> None:
        item = _make_work_item()
        exact_content = "y" * 2000
        section = _make_section(item.id, content=exact_content)
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository([section])

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["sections"][0]["content_markdown"] == exact_content
        assert not result["sections"][0]["content_markdown"].endswith("...")

    @pytest.mark.asyncio
    async def test_multiple_sections_all_included(self) -> None:
        item = _make_work_item()
        sections = [
            _make_section(item.id, SectionType.SUMMARY, "Summary text", 0),
            _make_section(item.id, SectionType.CONTEXT, "Context text", 1),
            _make_section(item.id, SectionType.ACCEPTANCE_CRITERIA, "AC text", 2),
        ]
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository(sections)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert len(result["sections"]) == 3

    @pytest.mark.asyncio
    async def test_section_title_derived_from_section_type(self) -> None:
        item = _make_work_item()
        section = _make_section(item.id, SectionType.ACCEPTANCE_CRITERIA, "AC body")
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository([section])

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["sections"][0]["title"] == SectionType.ACCEPTANCE_CRITERIA.value

    @pytest.mark.asyncio
    async def test_no_sections_returns_empty_list(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository([])

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["sections"] == []


# ---------------------------------------------------------------------------
# Not-found and cross-workspace tests
# ---------------------------------------------------------------------------


class TestReadWorkItemNotFound:
    @pytest.mark.asyncio
    async def test_unknown_id_returns_not_found_error(self) -> None:
        svc = _fake_service_not_found()
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(uuid4()), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_not_found_does_not_query_sections(self) -> None:
        svc = _fake_service_not_found()
        called = []

        class TrackingSectionRepo:
            async def get_by_work_item(self, work_item_id: UUID) -> list[Section]:
                called.append(work_item_id)
                return []

        result = await handle_read_work_item(
            arguments={"work_item_id": str(uuid4()), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=TrackingSectionRepo(),
        )

        assert result == {"error": "not_found"}
        assert called == []

    @pytest.mark.asyncio
    async def test_cross_workspace_isolation_returns_not_found(self) -> None:
        """Service raises WorkItemNotFoundError when workspace_id doesn't match item's workspace."""
        # Service enforces workspace isolation; handler sees WorkItemNotFoundError → not_found
        svc = MagicMock()
        svc.get = AsyncMock(side_effect=WorkItemNotFoundError(uuid4()))
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(uuid4()), "workspace_id": str(uuid4())},
            service=svc,
            section_repo=section_repo,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_service_called_with_correct_workspace_id(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        svc.get.assert_called_once_with(item.id, WORKSPACE_ID)


# ---------------------------------------------------------------------------
# Field value tests
# ---------------------------------------------------------------------------


class TestReadWorkItemFieldValues:
    @pytest.mark.asyncio
    async def test_title_matches_work_item(self) -> None:
        item = _make_work_item(title="Important feature title")
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["title"] == "Important feature title"

    @pytest.mark.asyncio
    async def test_description_matches_work_item(self) -> None:
        item = _make_work_item(description="Feature description here")
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["description"] == "Feature description here"

    @pytest.mark.asyncio
    async def test_external_jira_key_included_when_set(self) -> None:
        item = _make_work_item(external_jira_key="PROJ-123")
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["external_jira_key"] == "PROJ-123"

    @pytest.mark.asyncio
    async def test_external_jira_key_is_none_when_not_set(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        assert result["external_jira_key"] is None

    @pytest.mark.asyncio
    async def test_owner_is_string_uuid(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        UUID(result["owner"])

    @pytest.mark.asyncio
    async def test_project_is_string_uuid(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section_repo = FakeSectionRepository()

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(WORKSPACE_ID)},
            service=svc,
            section_repo=section_repo,
        )

        UUID(result["project"])

    @pytest.mark.asyncio
    async def test_missing_work_item_id_raises(self) -> None:
        svc = _fake_service_not_found()
        section_repo = FakeSectionRepository()

        with pytest.raises((ValueError, KeyError)):
            await handle_read_work_item(
                arguments={"workspace_id": str(WORKSPACE_ID)},
                service=svc,
                section_repo=section_repo,
            )

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self) -> None:
        svc = _fake_service_not_found()
        section_repo = FakeSectionRepository()

        with pytest.raises(ValueError):
            await handle_read_work_item(
                arguments={"work_item_id": "not-a-uuid", "workspace_id": str(WORKSPACE_ID)},
                service=svc,
                section_repo=section_repo,
            )
