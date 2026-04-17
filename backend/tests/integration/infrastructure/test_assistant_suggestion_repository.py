"""AssistantSuggestionRepositoryImpl integration tests — EP-03 Phase 4.

Covers:
- create_batch inserts all suggestions and returns persisted entities
- create_batch with empty list returns empty list
- get_by_id returns entity or None
- get_by_batch_id returns all suggestions in batch
- get_by_dundun_request_id returns matched suggestions
- list_pending_for_work_item excludes accepted/rejected/expired
- update_status bulk-updates matching rows and returns count
- update_status with empty list returns 0
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_suggestion(
    work_item_id: object,
    created_by: object,
    *,
    workspace_id: object | None = None,
    batch_id: object = None,
    dundun_request_id: str | None = None,
    status: SuggestionStatus = SuggestionStatus.PENDING,
    expires_in: timedelta = timedelta(hours=1),
) -> AssistantSuggestion:
    now = datetime.now(UTC)
    return AssistantSuggestion(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),  # type: ignore[arg-type]
        work_item_id=work_item_id,  # type: ignore[arg-type]
        thread_id=None,
        section_id=None,
        proposed_content="proposed text",
        current_content="current text",
        rationale="rationale",
        status=status,
        version_number_target=1,
        batch_id=batch_id or uuid4(),  # type: ignore[arg-type]
        dundun_request_id=dundun_request_id,
        created_by=created_by,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
        expires_at=now + expires_in,
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


class TestAssistantSuggestionRepositoryCreateBatch:
    async def test_create_batch_inserts_and_returns_entities(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        batch_id = uuid4()
        suggestions = [
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, batch_id=batch_id),
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, batch_id=batch_id),
        ]

        results = await AssistantSuggestionRepositoryImpl(db).create_batch(suggestions)

        assert len(results) == 2
        assert all(isinstance(r, AssistantSuggestion) for r in results)
        assert all(r.batch_id == batch_id for r in results)

    async def test_create_batch_with_empty_list_returns_empty(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        _user, _item = user_and_work_item
        results = await AssistantSuggestionRepositoryImpl(db).create_batch([])

        assert results == []


class TestAssistantSuggestionRepositoryGet:
    async def test_get_by_id_returns_entity(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = AssistantSuggestionRepositoryImpl(db)
        [created] = await repo.create_batch([_make_suggestion(item.id, user.id, workspace_id=item.workspace_id)])

        fetched = await repo.get_by_id(created.id)

        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_by_id_returns_none_for_missing(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        _user, _item = user_and_work_item
        result = await AssistantSuggestionRepositoryImpl(db).get_by_id(uuid4())

        assert result is None

    async def test_get_by_batch_id_returns_all_in_batch(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = AssistantSuggestionRepositoryImpl(db)
        batch_id = uuid4()
        other_batch_id = uuid4()

        await repo.create_batch([
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, batch_id=batch_id),
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, batch_id=batch_id),
        ])
        await repo.create_batch([_make_suggestion(item.id, user.id, workspace_id=item.workspace_id, batch_id=other_batch_id)])

        results = await repo.get_by_batch_id(batch_id)

        assert len(results) == 2
        assert all(r.batch_id == batch_id for r in results)

    async def test_get_by_dundun_request_id_returns_matched(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = AssistantSuggestionRepositoryImpl(db)
        request_id = f"req_{uuid4().hex}"

        await repo.create_batch([
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, dundun_request_id=request_id),
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, dundun_request_id=request_id),
        ])
        await repo.create_batch([_make_suggestion(item.id, user.id, workspace_id=item.workspace_id)])  # no request_id

        results = await repo.get_by_dundun_request_id(request_id)

        assert len(results) == 2
        assert all(r.dundun_request_id == request_id for r in results)

    async def test_get_by_dundun_request_id_returns_empty_for_missing(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        _user, _item = user_and_work_item
        results = await AssistantSuggestionRepositoryImpl(db).get_by_dundun_request_id(
            "nonexistent"
        )

        assert results == []


class TestAssistantSuggestionRepositoryListPending:
    async def test_list_pending_returns_only_pending_not_expired(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = AssistantSuggestionRepositoryImpl(db)

        pending = _make_suggestion(item.id, user.id, workspace_id=item.workspace_id)
        accepted = _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, status=SuggestionStatus.ACCEPTED)
        rejected = _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, status=SuggestionStatus.REJECTED)
        expired = _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, status=SuggestionStatus.EXPIRED)

        [p, a, r, e] = await repo.create_batch([pending, accepted, rejected, expired])

        results = await repo.list_pending_for_work_item(item.id)

        ids = [res.id for res in results]
        assert p.id in ids
        assert a.id not in ids
        assert r.id not in ids
        assert e.id not in ids

    async def test_list_pending_excludes_time_expired_suggestions(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = AssistantSuggestionRepositoryImpl(db)

        still_valid = _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, expires_in=timedelta(hours=1))
        time_expired = _make_suggestion(item.id, user.id, workspace_id=item.workspace_id, expires_in=timedelta(seconds=-1))

        [v, te] = await repo.create_batch([still_valid, time_expired])

        results = await repo.list_pending_for_work_item(item.id)

        ids = [res.id for res in results]
        assert v.id in ids
        assert te.id not in ids

    async def test_list_pending_returns_empty_for_no_suggestions(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        _user, item = user_and_work_item
        results = await AssistantSuggestionRepositoryImpl(db).list_pending_for_work_item(item.id)

        assert results == []


class TestAssistantSuggestionRepositoryUpdateStatus:
    async def test_update_status_returns_count_of_updated_rows(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = AssistantSuggestionRepositoryImpl(db)

        [s1, s2, s3] = await repo.create_batch([
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id),
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id),
            _make_suggestion(item.id, user.id, workspace_id=item.workspace_id),
        ])

        count = await repo.update_status(
            [s1.id, s2.id], SuggestionStatus.ACCEPTED, datetime.now(UTC)
        )

        assert count == 2

    async def test_update_status_mutates_persisted_rows(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = AssistantSuggestionRepositoryImpl(db)
        [s] = await repo.create_batch([_make_suggestion(item.id, user.id, workspace_id=item.workspace_id)])

        await repo.update_status([s.id], SuggestionStatus.REJECTED, datetime.now(UTC))

        fetched = await repo.get_by_id(s.id)
        assert fetched is not None
        assert fetched.status == SuggestionStatus.REJECTED

    async def test_update_status_with_empty_list_returns_zero(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
            AssistantSuggestionRepositoryImpl,
        )

        _user, _item = user_and_work_item
        count = await AssistantSuggestionRepositoryImpl(db).update_status(
            [], SuggestionStatus.EXPIRED, datetime.now(UTC)
        )

        assert count == 0
