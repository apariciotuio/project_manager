"""EP-07 phase 3.6 — SectionService auto-versioning on content change.

RED tests: verify SectionService.update_section calls VersioningService.create_version
when content changes, and skips it when content is unchanged.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.models.section import Section
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.models.work_item_version import (
    VersionActorType,
    VersionTrigger,
    WorkItemVersion,
)
from app.domain.repositories.work_item_version_repository import IWorkItemVersionRepository


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _make_section(work_item_id: UUID, *, content: str = "initial content xyz abc def") -> Section:
    now = datetime.now(UTC)
    return Section(
        id=uuid4(),
        work_item_id=work_item_id,
        section_type=SectionType.SUMMARY,
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


class _FakeWorkItem:
    def __init__(self, owner_id: UUID) -> None:
        self.id = uuid4()
        self.owner_id = owner_id


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


class FakeVersionRepo(IWorkItemVersionRepository):
    def __init__(self) -> None:
        self._store: list[WorkItemVersion] = []

    async def append(
        self,
        work_item_id: UUID,
        snapshot: dict[str, Any],
        created_by: UUID,
        *,
        trigger: str = "content_edit",
        actor_type: str = "human",
        actor_id: UUID | None = None,
        commit_message: str | None = None,
    ) -> WorkItemVersion:
        existing_max = max(
            (v.version_number for v in self._store if v.work_item_id == work_item_id), default=0
        )
        version = WorkItemVersion(
            id=uuid4(),
            work_item_id=work_item_id,
            version_number=existing_max + 1,
            snapshot=snapshot,
            created_by=created_by,
            created_at=datetime.now(UTC),
            trigger=VersionTrigger(trigger),
            actor_type=VersionActorType(actor_type),
            actor_id=actor_id,
            commit_message=commit_message,
        )
        self._store.append(version)
        return version

    async def get_latest(self, work_item_id: UUID, workspace_id: UUID) -> WorkItemVersion | None:
        items = [v for v in self._store if v.work_item_id == work_item_id]
        return items[-1] if items else None

    async def get(self, version_id: UUID, workspace_id: UUID) -> WorkItemVersion | None:
        return next((v for v in self._store if v.id == version_id), None)

    async def get_by_number(
        self, work_item_id: UUID, version_number: int, workspace_id: UUID
    ) -> WorkItemVersion | None:
        return next(
            (v for v in self._store if v.work_item_id == work_item_id and v.version_number == version_number),
            None,
        )

    async def list_by_work_item(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        limit: int = 20,
        before_version: int | None = None,
    ) -> list[WorkItemVersion]:
        return [v for v in self._store if v.work_item_id == work_item_id]


class _FakeVersioningService:
    """Minimal fake that records create_version calls."""

    def __init__(self, version_repo: FakeVersionRepo, workspace_id: UUID) -> None:
        self._repo = version_repo
        self._workspace_id = workspace_id

    async def create_version(
        self,
        *,
        work_item_id: UUID,
        workspace_id: UUID,
        actor_id: UUID,
        trigger: VersionTrigger = VersionTrigger.CONTENT_EDIT,
        actor_type: VersionActorType = VersionActorType.HUMAN,
        commit_message: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> WorkItemVersion:
        return await self._repo.append(
            work_item_id=work_item_id,
            snapshot=snapshot or {},
            created_by=actor_id,
            trigger=trigger.value,
            actor_type=actor_type.value,
            actor_id=actor_id,
            commit_message=commit_message,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _build_service(section: Section, wi: Any, version_repo: FakeVersionRepo, workspace_id: UUID):
    from app.application.services.section_service import SectionService

    versioning = _FakeVersioningService(version_repo, workspace_id)
    return SectionService(
        section_repo=_FakeSectionRepo(section),  # type: ignore[arg-type]
        section_version_repo=_FakeSectionVersionRepo(),  # type: ignore[arg-type]
        work_item_repo=_FakeWorkItemRepo(wi),  # type: ignore[arg-type]
        versioning_service=versioning,  # type: ignore[arg-type]
    )


class TestSectionServiceAutoVersioning:
    @pytest.mark.asyncio
    async def test_changed_content_creates_version(self) -> None:
        actor_id = uuid4()
        workspace_id = uuid4()
        work_item_id = uuid4()
        section = _make_section(work_item_id, content="old content abc")
        wi = _FakeWorkItem(owner_id=actor_id)
        wi.id = work_item_id

        version_repo = FakeVersionRepo()
        svc = _build_service(section, wi, version_repo, workspace_id)

        await svc.update_section(
            section_id=section.id,
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            new_content="completely new content that differs",
        )

        assert len(version_repo._store) == 1
        v = version_repo._store[0]
        assert v.work_item_id == work_item_id
        assert v.trigger == VersionTrigger.CONTENT_EDIT

    @pytest.mark.asyncio
    async def test_same_content_skips_version(self) -> None:
        actor_id = uuid4()
        workspace_id = uuid4()
        work_item_id = uuid4()
        content = "exact same content here"
        section = _make_section(work_item_id, content=content)
        wi = _FakeWorkItem(owner_id=actor_id)
        wi.id = work_item_id

        version_repo = FakeVersionRepo()
        svc = _build_service(section, wi, version_repo, workspace_id)

        await svc.update_section(
            section_id=section.id,
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            new_content=content,  # same as initial
        )

        assert len(version_repo._store) == 0

    @pytest.mark.asyncio
    async def test_version_commit_message_includes_section_type(self) -> None:
        actor_id = uuid4()
        workspace_id = uuid4()
        work_item_id = uuid4()
        section = _make_section(work_item_id, content="old")
        wi = _FakeWorkItem(owner_id=actor_id)
        wi.id = work_item_id

        version_repo = FakeVersionRepo()
        svc = _build_service(section, wi, version_repo, workspace_id)

        await svc.update_section(
            section_id=section.id,
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            new_content="new content here definitely",
        )

        assert len(version_repo._store) == 1
        assert "summary" in (version_repo._store[0].commit_message or "").lower()

    @pytest.mark.asyncio
    async def test_no_versioning_service_still_works(self) -> None:
        """Backwards compat: SectionService without versioning_service injected does not crash."""
        from app.application.services.section_service import SectionService

        actor_id = uuid4()
        workspace_id = uuid4()
        work_item_id = uuid4()
        section = _make_section(work_item_id)
        wi = _FakeWorkItem(owner_id=actor_id)
        wi.id = work_item_id

        svc = SectionService(
            section_repo=_FakeSectionRepo(section),  # type: ignore[arg-type]
            section_version_repo=_FakeSectionVersionRepo(),  # type: ignore[arg-type]
            work_item_repo=_FakeWorkItemRepo(wi),  # type: ignore[arg-type]
        )

        # Should not raise
        await svc.update_section(
            section_id=section.id,
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            new_content="updated content that is new and different",
        )
