"""ConversationThreadRepositoryImpl integration tests — EP-03 Phase 4.

Covers:
- create stores and returns domain entity
- create duplicate (user_id, work_item_id) raises IntegrityError
- get_by_id returns entity or None
- get_by_user_and_work_item with work_item_id=None returns general thread
- get_by_user_and_work_item with work_item_id returns item-specific thread
- get_by_dundun_conversation_id returns entity or None
- list_for_user without filter returns all non-archived threads
- list_for_user with include_archived=True includes archived
- list_for_user with work_item_id filter
- update persists mutations (preview, archived)
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.conversation_thread import ConversationThread


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_thread(
    user_id: object,
    work_item_id: object = None,
    *,
    workspace_id: object | None = None,
    dundun_id: str | None = None,
) -> ConversationThread:
    now = datetime.now(UTC)
    return ConversationThread(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),  # type: ignore[arg-type]
        user_id=user_id,  # type: ignore[arg-type]
        work_item_id=work_item_id,  # type: ignore[arg-type]
        dundun_conversation_id=dundun_id or f"dun_{uuid4().hex}",
        last_message_preview=None,
        last_message_at=None,
        created_at=now,
        deleted_at=None,
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
    # Stash workspace_id on the item for downstream tests (domain model doesn't carry it).
    item.workspace_id = ws.id  # type: ignore[attr-defined]
    await db.flush()
    return user, item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConversationThreadRepositoryCreate:
    async def test_create_stores_and_returns_entity(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        thread = _make_thread(user.id, item.id, workspace_id=item.workspace_id)

        result = await ConversationThreadRepositoryImpl(db).create(thread)

        assert result.id == thread.id
        assert result.user_id == user.id
        assert result.work_item_id == item.id
        assert result.dundun_conversation_id == thread.dundun_conversation_id
        assert result.deleted_at is None

    async def test_create_general_thread_with_null_work_item(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        thread = _make_thread(user.id, None, workspace_id=item.workspace_id)

        result = await ConversationThreadRepositoryImpl(db).create(thread)

        assert result.work_item_id is None
        assert result.is_general_thread

    async def test_create_duplicate_user_work_item_raises_integrity_error(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)

        thread1 = _make_thread(user.id, item.id, workspace_id=item.workspace_id)
        await repo.create(thread1)
        await db.flush()

        thread2 = _make_thread(user.id, item.id, workspace_id=item.workspace_id)  # same (user, work_item)
        with pytest.raises(IntegrityError):
            await repo.create(thread2)
            await db.flush()


class TestConversationThreadRepositoryGet:
    async def test_get_by_id_returns_entity(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)
        thread = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id))

        fetched = await repo.get_by_id(thread.id)

        assert fetched is not None
        assert fetched.id == thread.id

    async def test_get_by_id_returns_none_for_missing(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        _user, _item = user_and_work_item
        result = await ConversationThreadRepositoryImpl(db).get_by_id(uuid4())

        assert result is None

    async def test_get_by_user_and_work_item_returns_item_thread(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)
        created = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id))

        fetched = await repo.get_by_user_and_work_item(user.id, item.id)

        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_by_user_and_work_item_with_none_returns_general_thread(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)
        created = await repo.create(_make_thread(user.id, None, workspace_id=item.workspace_id))

        fetched = await repo.get_by_user_and_work_item(user.id, None)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.work_item_id is None

    async def test_get_by_user_and_work_item_returns_none_when_absent(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        result = await ConversationThreadRepositoryImpl(db).get_by_user_and_work_item(
            user.id, item.id
        )

        assert result is None

    async def test_get_by_dundun_conversation_id_returns_entity(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)
        dundun_id = f"dun_{uuid4().hex}"
        created = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id, dundun_id=dundun_id))

        fetched = await repo.get_by_dundun_conversation_id(dundun_id)

        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_by_dundun_conversation_id_returns_none_for_missing(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        _user, _item = user_and_work_item
        result = await ConversationThreadRepositoryImpl(db).get_by_dundun_conversation_id(
            "nonexistent"
        )

        assert result is None


class TestConversationThreadRepositoryList:
    async def test_list_for_user_returns_non_archived_by_default(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)

        active = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id))
        archived_thread = _make_thread(user.id, None, workspace_id=item.workspace_id)
        archived_thread = ConversationThread(
            **{**archived_thread.__dict__, "deleted_at": datetime.now(UTC)}
        )
        await repo.create(archived_thread)

        results = await repo.list_for_user(user.id)

        ids = [r.id for r in results]
        assert active.id in ids
        assert archived_thread.id not in ids

    async def test_list_for_user_include_archived_returns_all(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)

        active = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id))
        archived_thread = _make_thread(user.id, None, workspace_id=item.workspace_id)
        archived_thread = ConversationThread(
            **{**archived_thread.__dict__, "deleted_at": datetime.now(UTC)}
        )
        archived = await repo.create(archived_thread)

        results = await repo.list_for_user(user.id, include_archived=True)

        ids = [r.id for r in results]
        assert active.id in ids
        assert archived.id in ids

    async def test_list_for_user_with_work_item_filter(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)

        item_thread = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id))
        general_thread = await repo.create(_make_thread(user.id, None, workspace_id=item.workspace_id))

        results = await repo.list_for_user(user.id, work_item_id=item.id)

        ids = [r.id for r in results]
        assert item_thread.id in ids
        assert general_thread.id not in ids


class TestConversationThreadRepositoryUpdate:
    async def test_update_persists_preview_and_last_message_at(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)
        thread = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id))

        now = datetime.now(UTC)
        updated_thread = ConversationThread(
            **{
                **thread.__dict__,
                "last_message_preview": "Hello world",
                "last_message_at": now,
            }
        )
        result = await repo.update(updated_thread)

        assert result.last_message_preview == "Hello world"
        assert result.last_message_at is not None

    async def test_update_archives_thread(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from app.infrastructure.persistence.conversation_thread_repository_impl import (
            ConversationThreadRepositoryImpl,
        )

        user, item = user_and_work_item
        repo = ConversationThreadRepositoryImpl(db)
        thread = await repo.create(_make_thread(user.id, item.id, workspace_id=item.workspace_id))

        archived = thread.archive(datetime.now(UTC))
        result = await repo.update(archived)

        assert result.is_archived
        assert result.deleted_at is not None
