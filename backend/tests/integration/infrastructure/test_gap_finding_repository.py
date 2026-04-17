"""GapFindingRepositoryImpl integration tests — EP-03 Phase 4.

Covers:
- insert_many persists all findings and returns entities with ids
- insert_many with empty list returns empty list
- get_active_for_work_item returns only non-invalidated findings
- get_active_for_work_item with source filter returns only matching source
- get_active_for_work_item returns empty list when no active findings
- invalidate_for_work_item with source=None invalidates all active findings
- invalidate_for_work_item with source="rule" only touches rule findings
- invalidate_for_work_item returns count of updated rows
- invalidate_for_work_item returns 0 when no active findings to invalidate
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.gap_finding import GapSeverity, StoredGapFinding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    work_item_id: object,
    *,
    workspace_id: object | None = None,
    source: str = "rule",
    severity: GapSeverity = GapSeverity.WARNING,
    dimension: str = "title",
    message: str = "test message",
    dundun_request_id: str | None = None,
    invalidated_at: datetime | None = None,
) -> StoredGapFinding:
    return StoredGapFinding(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),  # type: ignore[arg-type]
        work_item_id=work_item_id,  # type: ignore[arg-type]
        dimension=dimension,
        severity=severity,
        message=message,
        source=source,  # type: ignore[arg-type]
        dundun_request_id=dundun_request_id,
        created_at=datetime.now(UTC),
        invalidated_at=invalidated_at,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(db_session: AsyncSession) -> AsyncSession:
    return db_session


@pytest_asyncio.fixture
async def user_and_work_item(db: AsyncSession):
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.value_objects.work_item_state import WorkItemState
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    email = f"user_{uuid4().hex[:8]}@test.com"
    user = User.from_google_claims(
        sub=f"sub_{uuid4().hex}", email=email, name="Test User", picture=None
    )
    user = await UserRepositoryImpl(db).upsert(user)
    ws = Workspace.create_from_email(email=email, created_by=user.id)
    ws = await WorkspaceRepositoryImpl(db).create(ws)

    project_id = uuid4()
    item = WorkItem(
        id=uuid4(),
        project_id=project_id,
        title="Test work item",
        type=WorkItemType.TASK,
        state=WorkItemState.DRAFT,
        owner_id=user.id,
        creator_id=user.id,
        description=None,
        original_input=None,
        priority=None,
        due_date=None,
        tags=[],
        completeness_score=0,
        parent_work_item_id=None,
        materialized_path="",
        attachment_count=0,
        has_override=False,
        override_justification=None,
        owner_suspended_flag=False,
        draft_data=None,
        template_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
        exported_at=None,
        export_reference=None,
    )
    item = await WorkItemRepositoryImpl(db).save(item, ws.id)
    item.workspace_id = ws.id  # type: ignore[attr-defined]
    await db.flush()
    return user, item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGapFindingRepositoryInsertMany:
    async def test_insert_many_persists_and_returns_entities(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        findings = [
            _make_finding(item.id, workspace_id=item.workspace_id, source="rule"),
            _make_finding(item.id, workspace_id=item.workspace_id, source="dundun"),
        ]

        results = await GapFindingRepositoryImpl(db).insert_many(findings)

        assert len(results) == 2
        assert all(isinstance(r, StoredGapFinding) for r in results)
        assert all(r.work_item_id == item.id for r in results)

    async def test_insert_many_with_empty_list_returns_empty(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, _item = user_and_work_item
        results = await GapFindingRepositoryImpl(db).insert_many([])

        assert results == []

    async def test_insert_many_sets_created_at_and_null_invalidated_at(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        [result] = await GapFindingRepositoryImpl(db).insert_many([_make_finding(item.id, workspace_id=item.workspace_id)])

        assert result.created_at is not None
        assert result.invalidated_at is None

    async def test_insert_many_preserves_severity_and_source(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        finding = _make_finding(item.id, workspace_id=item.workspace_id, source="dundun", severity=GapSeverity.BLOCKING)

        [result] = await GapFindingRepositoryImpl(db).insert_many([finding])

        assert result.severity == GapSeverity.BLOCKING
        assert result.source == "dundun"


class TestGapFindingRepositoryGetActive:
    async def test_get_active_returns_non_invalidated(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        repo = GapFindingRepositoryImpl(db)

        active = _make_finding(item.id, workspace_id=item.workspace_id)
        invalidated = _make_finding(item.id, workspace_id=item.workspace_id, invalidated_at=datetime.now(UTC))
        [a, inv] = await repo.insert_many([active, invalidated])

        results = await repo.get_active_for_work_item(item.id)

        ids = [r.id for r in results]
        assert a.id in ids
        assert inv.id not in ids

    async def test_get_active_with_source_filter_returns_only_matching(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        repo = GapFindingRepositoryImpl(db)

        rule_finding = _make_finding(item.id, workspace_id=item.workspace_id, source="rule")
        dundun_finding = _make_finding(item.id, workspace_id=item.workspace_id, source="dundun")
        [rf, df] = await repo.insert_many([rule_finding, dundun_finding])

        rule_results = await repo.get_active_for_work_item(item.id, source="rule")

        ids = [r.id for r in rule_results]
        assert rf.id in ids
        assert df.id not in ids

    async def test_get_active_returns_empty_when_all_invalidated(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        repo = GapFindingRepositoryImpl(db)

        finding = _make_finding(item.id, workspace_id=item.workspace_id, invalidated_at=datetime.now(UTC))
        await repo.insert_many([finding])

        results = await repo.get_active_for_work_item(item.id)

        assert results == []

    async def test_get_active_returns_empty_for_unknown_work_item(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, _item = user_and_work_item
        results = await GapFindingRepositoryImpl(db).get_active_for_work_item(uuid4())

        assert results == []


class TestGapFindingRepositoryInvalidate:
    async def test_invalidate_with_no_source_invalidates_all_active(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        repo = GapFindingRepositoryImpl(db)

        await repo.insert_many([
            _make_finding(item.id, workspace_id=item.workspace_id, source="rule"),
            _make_finding(item.id, workspace_id=item.workspace_id, source="dundun"),
        ])

        count = await repo.invalidate_for_work_item(item.id, datetime.now(UTC))

        assert count == 2
        active = await repo.get_active_for_work_item(item.id)
        assert active == []

    async def test_invalidate_with_source_only_touches_that_source(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        repo = GapFindingRepositoryImpl(db)

        [rule_f, dundun_f] = await repo.insert_many([
            _make_finding(item.id, workspace_id=item.workspace_id, source="rule"),
            _make_finding(item.id, workspace_id=item.workspace_id, source="dundun"),
        ])

        count = await repo.invalidate_for_work_item(item.id, datetime.now(UTC), source="rule")

        assert count == 1
        active = await repo.get_active_for_work_item(item.id)
        ids = [r.id for r in active]
        assert dundun_f.id in ids
        assert rule_f.id not in ids

    async def test_invalidate_returns_zero_when_nothing_active(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )

        _user, item = user_and_work_item
        repo = GapFindingRepositoryImpl(db)

        # insert already-invalidated finding
        await repo.insert_many([_make_finding(item.id, workspace_id=item.workspace_id, invalidated_at=datetime.now(UTC))])

        count = await repo.invalidate_for_work_item(item.id, datetime.now(UTC))

        assert count == 0

    async def test_invalidate_does_not_affect_other_work_items(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.domain.models.work_item import WorkItem
        from app.domain.value_objects.work_item_state import WorkItemState
        from app.domain.value_objects.work_item_type import WorkItemType
        from app.infrastructure.persistence.gap_finding_repository_impl import (
            GapFindingRepositoryImpl,
        )
        from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
        from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

        user, item = user_and_work_item

        # Fetch workspace_id for the work item
        from app.infrastructure.persistence.models.orm import WorkItemORM
        from sqlalchemy import select
        row = (
            await db.execute(select(WorkItemORM).where(WorkItemORM.id == item.id))
        ).scalar_one()
        ws_id = row.workspace_id

        other_item = WorkItem(
            id=uuid4(),
            project_id=uuid4(),
            title="Other work item",
            type=WorkItemType.TASK,
            state=WorkItemState.DRAFT,
            owner_id=user.id,
            creator_id=user.id,
            description=None,
            original_input=None,
            priority=None,
            due_date=None,
            tags=[],
            completeness_score=0,
            parent_work_item_id=None,
            materialized_path="",
            attachment_count=0,
            has_override=False,
            override_justification=None,
            owner_suspended_flag=False,
            draft_data=None,
            template_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deleted_at=None,
            exported_at=None,
            export_reference=None,
        )
        other_item = await WorkItemRepositoryImpl(db).save(other_item, ws_id)
        other_item.workspace_id = ws_id  # type: ignore[attr-defined]
        await db.flush()

        repo = GapFindingRepositoryImpl(db)
        await repo.insert_many([
            _make_finding(item.id, workspace_id=item.workspace_id),
            _make_finding(other_item.id, workspace_id=other_item.workspace_id),
        ])

        await repo.invalidate_for_work_item(item.id, datetime.now(UTC))

        other_active = await repo.get_active_for_work_item(other_item.id)
        assert len(other_active) == 1
