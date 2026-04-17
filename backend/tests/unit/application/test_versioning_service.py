"""EP-07 Phase 3 — VersioningService unit tests (using fakes)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.application.services.versioning_service import VersionConflictError, VersioningService
from app.domain.models.work_item_version import (
    VersionActorType,
    VersionTrigger,
    WorkItemVersion,
)
from app.domain.repositories.work_item_version_repository import IWorkItemVersionRepository


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


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
        existing_max = max((v.version_number for v in self._store if v.work_item_id == work_item_id), default=0)
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
        candidates = [v for v in self._store if v.work_item_id == work_item_id]
        return max(candidates, key=lambda v: v.version_number) if candidates else None

    async def get(self, version_id: UUID, workspace_id: UUID) -> WorkItemVersion | None:
        return next((v for v in self._store if v.id == version_id), None)

    async def get_by_number(self, work_item_id: UUID, version_number: int, workspace_id: UUID) -> WorkItemVersion | None:
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
        candidates = [v for v in self._store if v.work_item_id == work_item_id]
        if not include_archived:
            candidates = [v for v in candidates if not v.archived]
        if before_version is not None:
            candidates = [v for v in candidates if v.version_number < before_version]
        candidates.sort(key=lambda v: v.version_number, reverse=True)
        return candidates[:limit]


def _make_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    return session


def _make_service(repo: FakeVersionRepo) -> VersioningService:
    session = _make_session()
    return VersioningService(session=session, repo=repo)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateVersion:
    @pytest.mark.asyncio
    async def test_first_version_is_number_1(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)
        work_item_id = uuid4()
        snapshot = {"schema_version": 1, "work_item": {"title": "Test"}, "sections": [], "task_node_ids": []}

        v = await svc.create_version(
            work_item_id=work_item_id,
            workspace_id=uuid4(),
            actor_id=uuid4(),
            snapshot=snapshot,
        )

        assert v.version_number == 1

    @pytest.mark.asyncio
    async def test_second_version_increments(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)
        work_item_id = uuid4()
        snap = {"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []}

        await svc.create_version(work_item_id=work_item_id, workspace_id=uuid4(), actor_id=uuid4(), snapshot=snap)
        v2 = await svc.create_version(work_item_id=work_item_id, workspace_id=uuid4(), actor_id=uuid4(), snapshot=snap)

        assert v2.version_number == 2

    @pytest.mark.asyncio
    async def test_trigger_stored_correctly(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)

        v = await svc.create_version(
            work_item_id=uuid4(),
            workspace_id=uuid4(),
            actor_id=uuid4(),
            trigger=VersionTrigger.STATE_TRANSITION,
            snapshot={"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []},
        )

        assert v.trigger == VersionTrigger.STATE_TRANSITION

    @pytest.mark.asyncio
    async def test_actor_type_stored(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)

        v = await svc.create_version(
            work_item_id=uuid4(),
            workspace_id=uuid4(),
            actor_id=uuid4(),
            actor_type=VersionActorType.SYSTEM,
            snapshot={"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []},
        )

        assert v.actor_type == VersionActorType.SYSTEM

    @pytest.mark.asyncio
    async def test_snapshot_schema_version_is_1(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)

        v = await svc.create_version(
            work_item_id=uuid4(),
            workspace_id=uuid4(),
            actor_id=uuid4(),
            snapshot={"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []},
        )

        assert v.snapshot_schema_version == 1

    @pytest.mark.asyncio
    async def test_all_triggers_accepted(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)
        snap = {"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []}

        for trigger in VersionTrigger:
            v = await svc.create_version(
                work_item_id=uuid4(),
                workspace_id=uuid4(),
                actor_id=uuid4(),
                trigger=trigger,
                snapshot=snap,
            )
            assert v.trigger == trigger


class TestListVersions:
    @pytest.mark.asyncio
    async def test_list_reverse_chron(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)
        wid = uuid4()
        snap = {"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []}
        ws = uuid4()

        for _ in range(3):
            await svc.create_version(work_item_id=wid, workspace_id=ws, actor_id=uuid4(), snapshot=snap)

        versions = await svc.list_for_work_item(wid, ws)
        numbers = [v.version_number for v in versions]
        assert numbers == sorted(numbers, reverse=True)

    @pytest.mark.asyncio
    async def test_get_by_number(self) -> None:
        repo = FakeVersionRepo()
        svc = _make_service(repo)
        wid = uuid4()
        ws = uuid4()
        snap = {"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []}

        await svc.create_version(work_item_id=wid, workspace_id=ws, actor_id=uuid4(), snapshot=snap)
        await svc.create_version(work_item_id=wid, workspace_id=ws, actor_id=uuid4(), snapshot=snap)

        v = await svc.get_by_number(wid, 1, ws)
        assert v is not None
        assert v.version_number == 1
