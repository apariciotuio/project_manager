"""EP-18 — Unit tests for list_sections MCP tool handler.

Tests exercise the handler in isolation using a FakeSectionRepository and
mock WorkItemService. No DB, no MCP SDK required.

Scenarios:
- Happy path: returns list with expected keys per section
- content_preview is first 200 chars
- Long content truncated at 200 chars
- Content exactly 200 chars not truncated
- Empty sections list returned when none exist
- Cross-workspace isolation: unknown work_item_id returns not_found error
- section_type exposed as string
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.exceptions import WorkItemNotFoundError
from app.domain.models.section import Section
from app.domain.models.section_type import SectionType
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType
from apps.mcp_server.tools.list_sections import handle_list_sections

WORKSPACE_ID = uuid4()

_EXPECTED_SECTION_KEYS = {
    "id",
    "title",
    "section_type",
    "completeness",
    "content_preview",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_work_item() -> WorkItem:
    uid = uuid4()
    return WorkItem.create(
        title="Parent work item",
        type=WorkItemType.TASK,
        owner_id=uid,
        creator_id=uid,
        project_id=uid,
    )


def _make_section(
    work_item_id: UUID,
    section_type: SectionType = SectionType.SUMMARY,
    content: str = "Some section content",
    display_order: int = 0,
    is_required: bool = True,
) -> Section:
    uid = uuid4()
    return Section.create(
        work_item_id=work_item_id,
        section_type=section_type,
        display_order=display_order,
        is_required=is_required,
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


class FakeSectionRepo:
    def __init__(self, sections: list[Section] | None = None) -> None:
        self._sections = sections or []

    async def get_by_work_item(self, work_item_id: UUID) -> list[Section]:
        return [s for s in self._sections if s.work_item_id == work_item_id]


# ---------------------------------------------------------------------------
# Shape tests
# ---------------------------------------------------------------------------


class TestListSectionsShape:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_section_has_all_expected_keys(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result
        assert set(result[0].keys()) == _EXPECTED_SECTION_KEYS

    @pytest.mark.asyncio
    async def test_id_is_valid_uuid_string(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        UUID(result[0]["id"])  # raises ValueError if not a valid UUID string

    @pytest.mark.asyncio
    async def test_section_type_is_string(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id, SectionType.ACCEPTANCE_CRITERIA)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result[0]["section_type"], str)

    @pytest.mark.asyncio
    async def test_title_matches_section_type_value(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id, SectionType.CONTEXT)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["title"] == SectionType.CONTEXT.value


# ---------------------------------------------------------------------------
# Content preview tests
# ---------------------------------------------------------------------------


class TestListSectionsContentPreview:
    @pytest.mark.asyncio
    async def test_short_content_included_verbatim(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        content = "Short content"
        section = _make_section(item.id, content=content)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["content_preview"] == content

    @pytest.mark.asyncio
    async def test_long_content_truncated_at_200_chars(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        long_content = "x" * 500
        section = _make_section(item.id, content=long_content)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        preview = result[0]["content_preview"]
        assert len(preview) <= 200
        assert preview == long_content[:200]

    @pytest.mark.asyncio
    async def test_content_exactly_200_chars_not_truncated(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        exact_content = "y" * 200
        section = _make_section(item.id, content=exact_content)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["content_preview"] == exact_content

    @pytest.mark.asyncio
    async def test_empty_content_returns_empty_string_preview(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id, content="")
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["content_preview"] == ""


# ---------------------------------------------------------------------------
# Completeness tests
# ---------------------------------------------------------------------------


class TestListSectionsCompleteness:
    @pytest.mark.asyncio
    async def test_required_section_with_content_is_complete(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id, content="Some content", is_required=True)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["completeness"] is True

    @pytest.mark.asyncio
    async def test_required_section_without_content_is_incomplete(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id, content="", is_required=True)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["completeness"] is False

    @pytest.mark.asyncio
    async def test_optional_section_without_content_is_complete(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        section = _make_section(item.id, content="", is_required=False)
        repo = FakeSectionRepo([section])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["completeness"] is True


# ---------------------------------------------------------------------------
# Multiple sections
# ---------------------------------------------------------------------------


class TestListSectionsMultiple:
    @pytest.mark.asyncio
    async def test_multiple_sections_all_returned(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        sections = [
            _make_section(item.id, SectionType.SUMMARY, "Summary", 0),
            _make_section(item.id, SectionType.CONTEXT, "Context", 1),
            _make_section(item.id, SectionType.ACCEPTANCE_CRITERIA, "AC", 2),
        ]
        repo = FakeSectionRepo(sections)

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_empty_sections_returns_empty_list(self) -> None:
        item = _make_work_item()
        svc = _fake_service_found(item)
        repo = FakeSectionRepo([])

        result = await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == []


# ---------------------------------------------------------------------------
# Cross-workspace isolation
# ---------------------------------------------------------------------------


class TestListSectionsIsolation:
    @pytest.mark.asyncio
    async def test_cross_workspace_work_item_returns_not_found(self) -> None:
        svc = _fake_service_not_found()
        repo = FakeSectionRepo()

        result = await handle_list_sections(
            arguments={"work_item_id": str(uuid4())},
            service=svc,
            section_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_not_found_does_not_query_sections(self) -> None:
        svc = _fake_service_not_found()
        called: list[UUID] = []

        class TrackingRepo:
            async def get_by_work_item(self, work_item_id: UUID) -> list[Section]:
                called.append(work_item_id)
                return []

        result = await handle_list_sections(
            arguments={"work_item_id": str(uuid4())},
            service=svc,
            section_repo=TrackingRepo(),
            workspace_id=WORKSPACE_ID,
        )

        assert result == {"error": "not_found"}
        assert called == []

    @pytest.mark.asyncio
    async def test_service_called_with_correct_workspace_id(self) -> None:
        item = _make_work_item()
        ws = uuid4()
        svc = _fake_service_found(item)
        repo = FakeSectionRepo()

        await handle_list_sections(
            arguments={"work_item_id": str(item.id)},
            service=svc,
            section_repo=repo,
            workspace_id=ws,
        )

        svc.get.assert_called_once_with(item.id, ws)

    @pytest.mark.asyncio
    async def test_invalid_work_item_id_raises(self) -> None:
        svc = _fake_service_not_found()
        repo = FakeSectionRepo()

        with pytest.raises(ValueError):
            await handle_list_sections(
                arguments={"work_item_id": "not-a-uuid"},
                service=svc,
                section_repo=repo,
                workspace_id=WORKSPACE_ID,
            )

    @pytest.mark.asyncio
    async def test_missing_work_item_id_raises(self) -> None:
        svc = _fake_service_not_found()
        repo = FakeSectionRepo()

        with pytest.raises((ValueError, KeyError)):
            await handle_list_sections(
                arguments={},
                service=svc,
                section_repo=repo,
                workspace_id=WORKSPACE_ID,
            )
