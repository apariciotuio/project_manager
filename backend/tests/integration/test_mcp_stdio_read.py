"""EP-18 — Integration test for read_work_item MCP tool.

Full in-process roundtrip:
  handle_read_work_item → WorkItemService.get → FakeWorkItemRepository
                        → FakeSectionRepository

Validates the complete tool handler pipeline without a real DB or MCP transport.
The section repo is constructed separately, mirroring the server.py dispatch pattern.

Scenarios:
- Known item in workspace returns all expected fields
- Sections from section_repo are included in response
- Long section content is truncated with "..." marker
- Different workspace returns {error: "not_found"}
- Missing work item id returns {error: "not_found"}
- Field types are correct (id=str UUID, state=str, sections=list, etc.)
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.events.event_bus import EventBus
from app.application.services.audit_service import AuditService
from app.application.services.work_item_service import WorkItemService
from app.domain.models.section import Section
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType
from tests.fakes.fake_repositories import (
    FakeAuditRepository,
    FakeUserRepository,
    FakeWorkItemRepository,
    FakeWorkspaceMembershipRepository,
)
from apps.mcp_server.tools.read_work_item import handle_read_work_item


# ---------------------------------------------------------------------------
# Inline fake section repository
# ---------------------------------------------------------------------------


class FakeSectionRepository:
    def __init__(self, sections: list[Section] | None = None) -> None:
        self._sections = sections or []

    def add(self, section: Section) -> None:
        self._sections.append(section)

    async def get_by_work_item(self, work_item_id: UUID) -> list[Section]:
        return [s for s in self._sections if s.work_item_id == work_item_id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(repo: FakeWorkItemRepository) -> WorkItemService:
    return WorkItemService(
        work_items=repo,
        users=FakeUserRepository(),
        memberships=FakeWorkspaceMembershipRepository(),
        audit=AuditService(FakeAuditRepository()),
        events=EventBus(),
    )


async def _seed_item(
    repo: FakeWorkItemRepository,
    *,
    workspace_id: UUID,
    title: str = "Test work item",
    description: str | None = None,
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
    await repo.save(item, workspace_id)
    return item


def _make_section(
    work_item_id: UUID,
    section_type: SectionType = SectionType.SUMMARY,
    content: str = "Section content",
) -> Section:
    uid = uuid4()
    return Section.create(
        work_item_id=work_item_id,
        section_type=section_type,
        display_order=0,
        is_required=True,
        created_by=uid,
        content=content,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadWorkItemIntegration:
    def setup_method(self) -> None:
        self.repo = FakeWorkItemRepository()
        self.section_repo = FakeSectionRepository()
        self.ws_id = uuid4()
        self.other_ws_id = uuid4()

    @pytest.mark.asyncio
    async def test_known_item_returns_all_expected_fields(self) -> None:
        item = await _seed_item(self.repo, workspace_id=self.ws_id, title="My work item")
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert result["id"] == str(item.id)
        assert result["title"] == "My work item"
        assert isinstance(result["state"], str)
        assert isinstance(result["type"], str)
        assert isinstance(result["completeness_score"], int)
        assert "sections" in result
        assert "created_at" in result
        assert "updated_at" in result

    @pytest.mark.asyncio
    async def test_sections_from_repo_included_in_response(self) -> None:
        item = await _seed_item(self.repo, workspace_id=self.ws_id)
        section = _make_section(item.id, SectionType.SUMMARY, "The summary text")
        self.section_repo.add(section)
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert len(result["sections"]) == 1
        s = result["sections"][0]
        assert s["title"] == SectionType.SUMMARY.value
        assert s["content_markdown"] == "The summary text"

    @pytest.mark.asyncio
    async def test_long_section_content_truncated(self) -> None:
        item = await _seed_item(self.repo, workspace_id=self.ws_id)
        long_content = "a" * 3000
        section = _make_section(item.id, SectionType.CONTEXT, long_content)
        self.section_repo.add(section)
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        content = result["sections"][0]["content_markdown"]
        assert len(content) <= 2003
        assert content.endswith("...")

    @pytest.mark.asyncio
    async def test_different_workspace_returns_not_found(self) -> None:
        await _seed_item(self.repo, workspace_id=self.ws_id, title="Item in ws_a")
        # Seed item in ws_id but query with other_ws_id
        item = await _seed_item(self.repo, workspace_id=self.ws_id)
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.other_ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_unknown_item_id_returns_not_found(self) -> None:
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(uuid4()), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_result_id_matches_seeded_item(self) -> None:
        item = await _seed_item(self.repo, workspace_id=self.ws_id, title="Known title")
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert result["id"] == str(item.id)

    @pytest.mark.asyncio
    async def test_multiple_sections_all_returned(self) -> None:
        item = await _seed_item(self.repo, workspace_id=self.ws_id)
        for st in [SectionType.SUMMARY, SectionType.CONTEXT, SectionType.ACCEPTANCE_CRITERIA]:
            self.section_repo.add(_make_section(item.id, st, f"Content for {st.value}"))
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert len(result["sections"]) == 3

    @pytest.mark.asyncio
    async def test_no_sections_returns_empty_sections_list(self) -> None:
        item = await _seed_item(self.repo, workspace_id=self.ws_id)
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert result["sections"] == []

    @pytest.mark.asyncio
    async def test_external_jira_key_included(self) -> None:
        uid = uuid4()
        item = WorkItem.create(
            title="Jira linked item",
            type=WorkItemType.TASK,
            owner_id=uid,
            creator_id=uid,
            project_id=uid,
        )
        item.external_jira_key = "PROJ-999"
        await self.repo.save(item, self.ws_id)
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert result["external_jira_key"] == "PROJ-999"

    @pytest.mark.asyncio
    async def test_sections_from_different_item_not_included(self) -> None:
        """Sections belonging to another work item must not leak into this item's response."""
        item_a = await _seed_item(self.repo, workspace_id=self.ws_id, title="Item A")
        item_b = await _seed_item(self.repo, workspace_id=self.ws_id, title="Item B")
        # Only add section for item_b
        self.section_repo.add(_make_section(item_b.id, SectionType.NOTES, "B notes"))
        svc = _make_service(self.repo)

        result = await handle_read_work_item(
            arguments={"work_item_id": str(item_a.id), "workspace_id": str(self.ws_id)},
            service=svc,
            section_repo=self.section_repo,
        )

        assert result["sections"] == []
