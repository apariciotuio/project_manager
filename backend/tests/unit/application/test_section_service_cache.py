"""EP-04 Phase 5 — SectionService cache invalidation tests."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.models.section import Section
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.value_objects.work_item_type import WorkItemType


def _make_section(work_item_id: UUID, *, required: bool = False) -> Section:
    now = datetime.now(UTC)
    return Section(
        id=uuid4(),
        work_item_id=work_item_id,
        section_type=SectionType.SUMMARY,
        content="initial content x" * 5,
        display_order=1,
        is_required=required,
        generation_source=GenerationSource.LLM,
        version=1,
        created_at=now,
        updated_at=now,
        created_by=uuid4(),
        updated_by=uuid4(),
    )


class _FakeWorkItem:
    def __init__(self, owner_id: UUID) -> None:
        self.id = uuid4()
        self.owner_id = owner_id
        self.type = WorkItemType.BUG
        self.owner_suspended_flag = False


class _FakeWorkItemRepo:
    def __init__(self, item: Any) -> None:
        self._item = item

    async def get(self, work_item_id: UUID, workspace_id: UUID) -> Any:
        return self._item


class _FakeSectionRepo:
    def __init__(self, section: Section) -> None:
        self._section = section

    async def get(self, section_id: UUID) -> Section | None:
        return self._section if self._section.id == section_id else None

    async def save(self, section: Section) -> Section:
        return section

    async def get_by_work_item(self, work_item_id: UUID) -> list[Section]:
        return [self._section]

    async def bulk_insert(self, sections: list[Section]) -> list[Section]:
        return sections


class _FakeSectionVersionRepo:
    async def append(self, section: Section, actor_id: UUID) -> None:
        pass


class _TrackingCache:
    """Records delete calls to verify cache invalidation."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {"completeness:sentinel": "cached_value"}
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int = 60) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self._store.pop(key, None)


class TestSectionServiceCacheInvalidation:
    @pytest.mark.asyncio
    async def test_update_section_invalidates_completeness_cache(self) -> None:
        from app.application.services.section_service import SectionService

        actor_id = uuid4()
        work_item_id = uuid4()
        section = _make_section(work_item_id)
        wi = _FakeWorkItem(owner_id=actor_id)
        wi.id = work_item_id

        cache = _TrackingCache()
        svc = SectionService(
            section_repo=_FakeSectionRepo(section),  # type: ignore[arg-type]
            section_version_repo=_FakeSectionVersionRepo(),  # type: ignore[arg-type]
            work_item_repo=_FakeWorkItemRepo(wi),  # type: ignore[arg-type]
            cache=cache,  # type: ignore[arg-type]
        )

        await svc.update_section(
            section_id=section.id,
            work_item_id=work_item_id,
            workspace_id=uuid4(),
            actor_id=actor_id,
            new_content="new content that is long enough to be valid" * 2,
        )

        assert f"completeness:{work_item_id}" in cache.deleted

    @pytest.mark.asyncio
    async def test_no_cache_injected_does_not_crash(self) -> None:
        from app.application.services.section_service import SectionService

        actor_id = uuid4()
        work_item_id = uuid4()
        section = _make_section(work_item_id)
        wi = _FakeWorkItem(owner_id=actor_id)
        wi.id = work_item_id

        svc = SectionService(
            section_repo=_FakeSectionRepo(section),  # type: ignore[arg-type]
            section_version_repo=_FakeSectionVersionRepo(),  # type: ignore[arg-type]
            work_item_repo=_FakeWorkItemRepo(wi),  # type: ignore[arg-type]
            cache=None,
        )

        # Should not raise even with no cache
        await svc.update_section(
            section_id=section.id,
            work_item_id=work_item_id,
            workspace_id=uuid4(),
            actor_id=actor_id,
            new_content="updated content that is long enough to pass" * 2,
        )
