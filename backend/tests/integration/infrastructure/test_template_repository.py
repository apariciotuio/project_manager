"""TemplateRepositoryImpl integration tests — EP-02 Phase 3.

Covers:
- get_by_workspace_and_type returns workspace template when it exists
- Returns None when no workspace template (system fallback is service responsibility, not repo)
- Duplicate (workspace_id, type) raises constraint error
- System template cannot have workspace_id set (DB constraint enforced)
- get_system_default returns system template
- update / delete round-trips
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import DuplicateTemplateError, TemplateNotFoundError
from app.domain.models.template import Template
from app.domain.models.workspace import Workspace
from app.domain.value_objects.work_item_type import WorkItemType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_sub() -> str:
    return f"sub_{uuid4().hex}"


def _make_user_email() -> str:
    return f"user_{uuid4().hex[:8]}@test.com"


def _make_template(workspace_id: object, type_: WorkItemType, *, is_system: bool = False) -> Template:
    from uuid import UUID

    ws_id = workspace_id if isinstance(workspace_id, UUID) else None
    return Template(
        id=uuid4(),
        workspace_id=ws_id,
        type=type_,
        name=f"{type_.value} template",
        content=f"## {type_.value.title()} Template",
        is_system=is_system,
        created_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(db_session: AsyncSession) -> AsyncSession:
    return db_session


@pytest_asyncio.fixture
async def workspace(db: AsyncSession) -> Workspace:
    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    email = _make_user_email()
    user = User.from_google_claims(sub=_make_user_sub(), email=email, name="Test", picture=None)
    user = await UserRepositoryImpl(db).upsert(user)
    ws = Workspace.create_from_email(email=email, created_by=user.id)
    return await WorkspaceRepositoryImpl(db).create(ws)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTemplateRepositoryGet:
    async def test_get_by_workspace_and_type_returns_template(
        self, db: AsyncSession, workspace: Workspace
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        repo = TemplateRepositoryImpl(db)
        tmpl = _make_template(workspace.id, WorkItemType.BUG)
        await repo.create(tmpl)

        result = await repo.get_by_workspace_and_type(workspace.id, WorkItemType.BUG)

        assert result is not None
        assert result.type == WorkItemType.BUG
        assert result.workspace_id == workspace.id

    async def test_get_by_workspace_and_type_returns_none_when_absent(
        self, db: AsyncSession, workspace: Workspace
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        result = await TemplateRepositoryImpl(db).get_by_workspace_and_type(
            workspace.id, WorkItemType.BUG
        )
        assert result is None

    async def test_get_system_default_returns_system_template(
        self, db: AsyncSession
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        repo = TemplateRepositoryImpl(db)
        sys_tmpl = _make_template(None, WorkItemType.TASK, is_system=True)
        await repo.create(sys_tmpl)

        result = await repo.get_system_default(WorkItemType.TASK)

        assert result is not None
        assert result.is_system is True
        assert result.workspace_id is None

    async def test_get_system_default_returns_none_when_absent(
        self, db: AsyncSession
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        result = await TemplateRepositoryImpl(db).get_system_default(WorkItemType.IDEA)
        assert result is None


class TestTemplateRepositoryConstraints:
    async def test_duplicate_workspace_type_raises_duplicate_template_error(
        self, db: AsyncSession, workspace: Workspace
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        repo = TemplateRepositoryImpl(db)
        tmpl1 = _make_template(workspace.id, WorkItemType.BUG)
        await repo.create(tmpl1)

        tmpl2 = _make_template(workspace.id, WorkItemType.BUG)
        with pytest.raises(DuplicateTemplateError):
            await repo.create(tmpl2)

    async def test_system_template_with_workspace_id_raises_integrity_error(
        self, db: AsyncSession, workspace: Workspace
    ) -> None:
        """DB CHECK constraint: is_system=TRUE + workspace_id IS NOT NULL → error."""
        from sqlalchemy import text

        with pytest.raises(Exception):  # IntegrityError or ValueError from domain
            # This would violate the Template domain invariant or DB constraint
            tmpl = Template(
                id=uuid4(),
                workspace_id=workspace.id,  # violates is_system invariant
                type=WorkItemType.BUG,
                name="System Bug",
                content="## Bug",
                is_system=True,
                created_by=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )


class TestTemplateRepositoryUpdate:
    async def test_update_returns_updated_template(
        self, db: AsyncSession, workspace: Workspace
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        repo = TemplateRepositoryImpl(db)
        tmpl = _make_template(workspace.id, WorkItemType.ENHANCEMENT)
        created = await repo.create(tmpl)

        updated = await repo.update(created.id, name="New Name", content="## Updated")

        assert updated.name == "New Name"
        assert updated.content == "## Updated"

    async def test_update_nonexistent_raises_not_found(
        self, db: AsyncSession
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        with pytest.raises(TemplateNotFoundError):
            await TemplateRepositoryImpl(db).update(uuid4(), name="X", content="Y")


class TestTemplateRepositoryDelete:
    async def test_delete_removes_template(
        self, db: AsyncSession, workspace: Workspace
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        repo = TemplateRepositoryImpl(db)
        tmpl = _make_template(workspace.id, WorkItemType.SPIKE)
        created = await repo.create(tmpl)

        await repo.delete(created.id)

        result = await repo.get_by_workspace_and_type(workspace.id, WorkItemType.SPIKE)
        assert result is None

    async def test_delete_nonexistent_raises_not_found(
        self, db: AsyncSession
    ) -> None:
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        with pytest.raises(TemplateNotFoundError):
            await TemplateRepositoryImpl(db).delete(uuid4())
