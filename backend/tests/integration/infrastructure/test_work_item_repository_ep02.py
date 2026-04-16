"""WorkItemRepositoryImpl integration tests for EP-02 extensions (draft_data, template_id)."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.persistence.session_context import with_workspace


def _make_email() -> str:
    return f"user_{uuid4().hex[:8]}@test.com"


@pytest_asyncio.fixture
async def ctx(db_session: AsyncSession):
    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    email = _make_email()
    user = User.from_google_claims(sub=f"sub_{uuid4().hex}", email=email, name="T", picture=None)
    user = await UserRepositoryImpl(db_session).upsert(user)
    ws = Workspace.create_from_email(email=email, created_by=user.id)
    ws = await WorkspaceRepositoryImpl(db_session).create(ws)
    await with_workspace(db_session, ws.id)
    return {
        "user": user,
        "ws": ws,
        "repo": WorkItemRepositoryImpl(db_session),
    }


class TestWorkItemRepositoryEP02:
    async def test_save_and_load_draft_data_preserves_nested_structure(
        self, ctx
    ) -> None:
        user, ws, repo = ctx["user"], ctx["ws"], ctx["repo"]
        item = WorkItem.create(
            title="Draft item",
            type=WorkItemType.BUG,
            owner_id=user.id,
            creator_id=user.id,
            project_id=uuid4(),
        )
        item.draft_data = {"description": "partial", "nested": {"key": 42, "list": [1, 2, 3]}}

        saved = await repo.save(item, ws.id)
        fetched = await repo.get(saved.id, ws.id)

        assert fetched is not None
        assert fetched.draft_data == {
            "description": "partial",
            "nested": {"key": 42, "list": [1, 2, 3]},
        }

    async def test_save_and_load_null_draft_data(self, ctx) -> None:
        user, ws, repo = ctx["user"], ctx["ws"], ctx["repo"]
        item = WorkItem.create(
            title="No draft",
            type=WorkItemType.TASK,
            owner_id=user.id,
            creator_id=user.id,
            project_id=uuid4(),
        )
        # draft_data defaults to None
        saved = await repo.save(item, ws.id)
        fetched = await repo.get(saved.id, ws.id)

        assert fetched is not None
        assert fetched.draft_data is None

    async def test_save_and_load_template_id_round_trip(self, ctx) -> None:
        from app.domain.models.template import Template
        from app.infrastructure.persistence.template_repository_impl import (
            TemplateRepositoryImpl,
        )

        user, ws, repo = ctx["user"], ctx["ws"], ctx["repo"]

        # Create a template first
        tmpl = Template(
            id=uuid4(),
            workspace_id=ws.id,
            type=WorkItemType.BUG,
            name="Bug Template",
            content="## Summary",
            is_system=False,
            created_by=user.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        tmpl_repo = TemplateRepositoryImpl(ctx["repo"]._session)
        created_tmpl = await tmpl_repo.create(tmpl)

        item = WorkItem.create(
            title="Templated item",
            type=WorkItemType.BUG,
            owner_id=user.id,
            creator_id=user.id,
            project_id=uuid4(),
        )
        item.template_id = created_tmpl.id

        saved = await repo.save(item, ws.id)
        fetched = await repo.get(saved.id, ws.id)

        assert fetched is not None
        assert fetched.template_id == created_tmpl.id
