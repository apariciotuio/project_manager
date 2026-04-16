"""WorkItemDraftRepositoryImpl integration tests — EP-02 Phase 3.

Covers:
- Upsert with matching version creates/updates record and increments local_version
- Upsert with lower client version (stale) returns DraftConflict with server data
- UNIQUE constraint: second upsert for same user+workspace updates existing row
- get_by_user_workspace returns None when no draft exists
- delete by owner succeeds
- delete by non-owner raises DraftForbiddenError
- delete_expired removes only expired rows
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import DraftForbiddenError, WorkItemDraftNotFoundError
from app.domain.models.user import User
from app.domain.models.work_item_draft import WorkItemDraft
from app.domain.models.workspace import Workspace
from app.domain.value_objects.draft_conflict import DraftConflict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_sub() -> str:
    return f"sub_{uuid4().hex}"


def _make_user_email() -> str:
    return f"user_{uuid4().hex[:8]}@test.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(db_session: AsyncSession) -> AsyncSession:
    return db_session


@pytest_asyncio.fixture
async def user_and_workspace(db: AsyncSession):
    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    email = _make_user_email()
    user = User.from_google_claims(sub=_make_user_sub(), email=email, name="Test User", picture=None)
    user = await UserRepositoryImpl(db).upsert(user)
    ws = Workspace.create_from_email(email=email, created_by=user.id)
    ws = await WorkspaceRepositoryImpl(db).create(ws)
    await db.flush()
    return user, ws


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkItemDraftRepositoryUpsert:
    async def test_upsert_new_draft_creates_with_version_1(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        draft = WorkItemDraft.create(
            user_id=user.id,
            workspace_id=ws.id,
            data={"title": "initial"},
        )

        result = await WorkItemDraftRepositoryImpl(db).upsert(draft, expected_version=0)

        assert isinstance(result, WorkItemDraft)
        assert result.local_version == 1
        assert result.data == {"title": "initial"}

    async def test_upsert_existing_draft_matching_version_increments(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        repo = WorkItemDraftRepositoryImpl(db)

        draft = WorkItemDraft.create(user_id=user.id, workspace_id=ws.id, data={"title": "v1"})
        result1 = await repo.upsert(draft, expected_version=0)
        assert isinstance(result1, WorkItemDraft)
        assert result1.local_version == 1

        # Second upsert with correct expected_version
        draft2 = WorkItemDraft(
            id=result1.id,
            user_id=user.id,
            workspace_id=ws.id,
            data={"title": "v2"},
            local_version=result1.local_version,
            incomplete=True,
            created_at=result1.created_at,
            updated_at=result1.updated_at,
            expires_at=result1.expires_at,
        )
        result2 = await repo.upsert(draft2, expected_version=1)

        assert isinstance(result2, WorkItemDraft)
        assert result2.local_version == 2
        assert result2.data == {"title": "v2"}

    async def test_upsert_stale_version_returns_draft_conflict(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        repo = WorkItemDraftRepositoryImpl(db)

        # Create a draft at version 1, then advance to version 2
        draft = WorkItemDraft.create(user_id=user.id, workspace_id=ws.id, data={"title": "v1"})
        result1 = await repo.upsert(draft, expected_version=0)
        assert isinstance(result1, WorkItemDraft)

        # Simulate another tab advancing version to 2
        draft_v2 = WorkItemDraft(
            id=result1.id,
            user_id=user.id,
            workspace_id=ws.id,
            data={"title": "v2"},
            local_version=result1.local_version,
            incomplete=True,
            created_at=result1.created_at,
            updated_at=result1.updated_at,
            expires_at=result1.expires_at,
        )
        result2 = await repo.upsert(draft_v2, expected_version=1)
        assert isinstance(result2, WorkItemDraft)
        assert result2.local_version == 2

        # Now stale client (still thinks version is 1) tries to upsert
        stale_draft = WorkItemDraft(
            id=result1.id,
            user_id=user.id,
            workspace_id=ws.id,
            data={"title": "stale"},
            local_version=result1.local_version,
            incomplete=True,
            created_at=result1.created_at,
            updated_at=result1.updated_at,
            expires_at=result1.expires_at,
        )
        conflict = await repo.upsert(stale_draft, expected_version=1)

        assert isinstance(conflict, DraftConflict)
        assert conflict.server_version == 2
        assert conflict.server_data == {"title": "v2"}

    async def test_upsert_unique_constraint_updates_existing_row(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        """Only one draft per user+workspace — second upsert with correct version updates it."""
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        repo = WorkItemDraftRepositoryImpl(db)

        draft1 = WorkItemDraft.create(user_id=user.id, workspace_id=ws.id, data={"title": "a"})
        result1 = await repo.upsert(draft1, expected_version=0)
        assert isinstance(result1, WorkItemDraft)
        assert result1.local_version == 1

        # Second upsert with matching version (1) → updates same row
        draft2 = WorkItemDraft(
            id=result1.id,
            user_id=user.id,
            workspace_id=ws.id,
            data={"title": "b"},
            local_version=result1.local_version,
            incomplete=True,
            created_at=result1.created_at,
            updated_at=result1.updated_at,
            expires_at=result1.expires_at,
        )
        result2 = await repo.upsert(draft2, expected_version=1)
        assert isinstance(result2, WorkItemDraft)

        # Should be the same logical row (same user+workspace), updated data
        fetched = await repo.get_by_user_workspace(user.id, ws.id)
        assert fetched is not None
        assert fetched.data == {"title": "b"}
        assert fetched.local_version == 2


class TestWorkItemDraftRepositoryGet:
    async def test_get_by_user_workspace_returns_none_when_absent(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        result = await WorkItemDraftRepositoryImpl(db).get_by_user_workspace(user.id, ws.id)
        assert result is None

    async def test_get_by_user_workspace_returns_existing_draft(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        repo = WorkItemDraftRepositoryImpl(db)

        draft = WorkItemDraft.create(user_id=user.id, workspace_id=ws.id, data={"title": "hi"})
        await repo.upsert(draft, expected_version=0)

        fetched = await repo.get_by_user_workspace(user.id, ws.id)
        assert fetched is not None
        assert fetched.data == {"title": "hi"}
        assert fetched.user_id == user.id
        assert fetched.workspace_id == ws.id


class TestWorkItemDraftRepositoryDelete:
    async def test_delete_by_owner_succeeds(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        repo = WorkItemDraftRepositoryImpl(db)

        draft = WorkItemDraft.create(user_id=user.id, workspace_id=ws.id, data={})
        result = await repo.upsert(draft, expected_version=0)
        assert isinstance(result, WorkItemDraft)

        await repo.delete(result.id, user.id)

        fetched = await repo.get_by_user_workspace(user.id, ws.id)
        assert fetched is None

    async def test_delete_by_non_owner_raises_forbidden(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )

        user, ws = user_and_workspace
        repo = WorkItemDraftRepositoryImpl(db)

        draft = WorkItemDraft.create(user_id=user.id, workspace_id=ws.id, data={})
        result = await repo.upsert(draft, expected_version=0)
        assert isinstance(result, WorkItemDraft)

        other_user_id = uuid4()
        with pytest.raises(DraftForbiddenError):
            await repo.delete(result.id, other_user_id)

    async def test_delete_expired_removes_expired_rows(
        self, db: AsyncSession, user_and_workspace
    ) -> None:
        from app.infrastructure.persistence.work_item_draft_repository_impl import (
            WorkItemDraftRepositoryImpl,
        )
        from app.infrastructure.persistence.models.orm import WorkItemDraftORM

        user, ws = user_and_workspace
        repo = WorkItemDraftRepositoryImpl(db)

        # Insert an already-expired draft directly
        now = datetime.now(UTC)
        expired_row = WorkItemDraftORM()
        expired_row.id = uuid4()
        expired_row.user_id = user.id
        expired_row.workspace_id = ws.id
        expired_row.data = {}  # type: ignore[assignment]
        expired_row.local_version = 1
        expired_row.incomplete = True
        expired_row.created_at = now - timedelta(days=31)
        expired_row.updated_at = now - timedelta(days=31)
        expired_row.expires_at = now - timedelta(days=1)
        db.add(expired_row)
        await db.flush()

        deleted = await repo.delete_expired()
        assert deleted >= 1

        fetched = await repo.get_by_user_workspace(user.id, ws.id)
        assert fetched is None
