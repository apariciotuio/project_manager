"""Unit tests for ConversationService.build_sections_snapshot — EP-22.

Tests:
  - Work item with 3 sections → snapshot maps section_type to content
  - Work item with 0 sections → empty dict
  - General thread (work_item_id=None) → None (skip)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tests.fakes.fake_dundun_client import FakeDundunClient
from tests.fakes.fake_repositories import FakeConversationThreadRepository, FakeSectionRepository


def _make_section(work_item_id, section_type_value: str, content: str):
    from app.domain.models.section import Section
    from app.domain.models.section_type import GenerationSource, SectionType

    now = datetime.now(UTC)
    return Section(
        id=uuid4(),
        work_item_id=work_item_id,
        section_type=SectionType(section_type_value),
        content=content,
        display_order=1,
        is_required=False,
        generation_source=GenerationSource.MANUAL,
        version=1,
        created_at=now,
        updated_at=now,
        created_by=uuid4(),
        updated_by=uuid4(),
    )


def _make_svc(section_repo=None):
    from app.application.services.conversation_service import ConversationService

    thread_repo = FakeConversationThreadRepository()
    dundun = FakeDundunClient()
    svc = ConversationService(thread_repo=thread_repo, dundun_client=dundun)
    svc._section_repo = section_repo  # injected for snapshot building
    return svc


class TestBuildSectionsSnapshot:
    async def test_work_item_with_sections_returns_snapshot(self) -> None:
        from app.application.services.conversation_service import ConversationService

        work_item_id = uuid4()
        section_repo = FakeSectionRepository()
        section_repo.seed(_make_section(work_item_id, "summary", "Summary content"))
        section_repo.seed(_make_section(work_item_id, "context", "Context here"))
        section_repo.seed(_make_section(work_item_id, "acceptance_criteria", "AC here"))

        thread_repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        svc = ConversationService(
            thread_repo=thread_repo,
            dundun_client=dundun,
            section_repo=section_repo,
        )

        snapshot = await svc.build_sections_snapshot(work_item_id)

        assert snapshot is not None
        assert snapshot["summary"] == "Summary content"
        assert snapshot["context"] == "Context here"
        assert snapshot["acceptance_criteria"] == "AC here"

    async def test_work_item_with_no_sections_returns_empty_dict(self) -> None:
        from app.application.services.conversation_service import ConversationService

        work_item_id = uuid4()
        section_repo = FakeSectionRepository()  # empty

        thread_repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        svc = ConversationService(
            thread_repo=thread_repo,
            dundun_client=dundun,
            section_repo=section_repo,
        )

        snapshot = await svc.build_sections_snapshot(work_item_id)

        assert snapshot == {}

    async def test_none_work_item_id_returns_none(self) -> None:
        from app.application.services.conversation_service import ConversationService

        thread_repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        svc = ConversationService(
            thread_repo=thread_repo,
            dundun_client=dundun,
            section_repo=FakeSectionRepository(),
        )

        snapshot = await svc.build_sections_snapshot(None)

        assert snapshot is None
