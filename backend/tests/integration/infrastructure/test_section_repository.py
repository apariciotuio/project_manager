"""EP-04 Phase 3 — SectionRepositoryImpl + SectionVersionRepositoryImpl +
ValidatorRepositoryImpl + WorkItemVersionRepositoryImpl integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.section import Section
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.models.validator import Validator, ValidatorStatus
from app.infrastructure.persistence.section_repository_impl import (
    SectionRepositoryImpl,
    SectionVersionRepositoryImpl,
    ValidatorRepositoryImpl,
    WorkItemVersionRepositoryImpl,
)


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
    user = User.from_google_claims(sub=f"sub_{uuid4().hex}", email=email, name="T", picture=None)
    user = await UserRepositoryImpl(db).upsert(user)
    ws = Workspace.create_from_email(email=email, created_by=user.id)
    ws = await WorkspaceRepositoryImpl(db).create(ws)
    item = WorkItem(
        id=uuid4(),
        project_id=uuid4(),
        title="Test work item title",
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
    await db.flush()
    return user, item


# ---------------------------------------------------------------------------
# SectionRepositoryImpl
# ---------------------------------------------------------------------------


class TestSectionRepository:
    async def test_bulk_insert_and_get_by_work_item_ordered_by_display_order(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        user, item = user_and_work_item
        repo = SectionRepositoryImpl(db)
        sections = [
            Section.create(
                work_item_id=item.id,
                section_type=SectionType.SUMMARY,
                display_order=1,
                is_required=True,
                created_by=user.id,
            ),
            Section.create(
                work_item_id=item.id,
                section_type=SectionType.NOTES,
                display_order=3,
                is_required=False,
                created_by=user.id,
            ),
            Section.create(
                work_item_id=item.id,
                section_type=SectionType.OBJECTIVE,
                display_order=2,
                is_required=False,
                created_by=user.id,
            ),
        ]
        await repo.bulk_insert(sections)
        await db.commit()

        found = await repo.get_by_work_item(item.id)
        assert [s.section_type for s in found] == [
            SectionType.SUMMARY,
            SectionType.OBJECTIVE,
            SectionType.NOTES,
        ]

    async def test_save_updates_existing_row(self, db: AsyncSession, user_and_work_item) -> None:
        user, item = user_and_work_item
        repo = SectionRepositoryImpl(db)
        section = Section.create(
            work_item_id=item.id,
            section_type=SectionType.SUMMARY,
            display_order=1,
            is_required=True,
            created_by=user.id,
        )
        await repo.save(section)
        await db.commit()
        section.update_content("fresh content of sufficient length", user.id)
        await repo.save(section)
        await db.commit()
        reloaded = await repo.get(section.id)
        assert reloaded is not None
        assert reloaded.version == 2
        assert reloaded.content.startswith("fresh")
        assert reloaded.generation_source is GenerationSource.MANUAL


# ---------------------------------------------------------------------------
# SectionVersionRepositoryImpl
# ---------------------------------------------------------------------------


class TestSectionVersionRepository:
    async def test_append_and_get_history_descending(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        user, item = user_and_work_item
        section_repo = SectionRepositoryImpl(db)
        version_repo = SectionVersionRepositoryImpl(db)
        section = Section.create(
            work_item_id=item.id,
            section_type=SectionType.SUMMARY,
            display_order=1,
            is_required=True,
            created_by=user.id,
        )
        await section_repo.save(section)
        await version_repo.append(section, user.id)
        section.update_content("v2 content is getting longer now", user.id)
        await section_repo.save(section)
        await version_repo.append(section, user.id)
        await db.commit()

        history = await version_repo.get_history(section.id)
        assert [v.version for v in history] == [2, 1]


# ---------------------------------------------------------------------------
# ValidatorRepositoryImpl
# ---------------------------------------------------------------------------


class TestValidatorRepository:
    async def test_assign_and_respond_persists_status(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        user, item = user_and_work_item
        repo = ValidatorRepositoryImpl(db)
        v = Validator.create(work_item_id=item.id, role="product_owner", assigned_by=user.id)
        await repo.assign(v)
        await db.commit()
        v.respond(ValidatorStatus.APPROVED)
        await repo.save(v)
        await db.commit()
        reloaded = await repo.get(v.id)
        assert reloaded is not None
        assert reloaded.status is ValidatorStatus.APPROVED
        assert reloaded.responded_at is not None

    async def test_unique_work_item_role_enforced(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        user, item = user_and_work_item
        repo = ValidatorRepositoryImpl(db)
        v1 = Validator.create(work_item_id=item.id, role="product_owner", assigned_by=user.id)
        await repo.assign(v1)
        await db.commit()
        v2 = Validator.create(work_item_id=item.id, role="product_owner", assigned_by=user.id)
        with pytest.raises(IntegrityError):
            await repo.assign(v2)
            await db.commit()
        await db.rollback()


# ---------------------------------------------------------------------------
# WorkItemVersionRepositoryImpl
# ---------------------------------------------------------------------------


class TestWorkItemVersionRepository:
    async def test_append_increments_version_number(
        self, db: AsyncSession, user_and_work_item
    ) -> None:
        user, item = user_and_work_item
        repo = WorkItemVersionRepositoryImpl(db)
        v1 = await repo.append(item.id, {"k": 1}, user.id)
        v2 = await repo.append(item.id, {"k": 2}, user.id)
        await db.commit()
        assert v1.version_number == 1
        assert v2.version_number == 2

        latest = await repo.get_latest(item.id)
        assert latest is not None
        assert latest.version_number == 2
        assert latest.snapshot == {"k": 2}
