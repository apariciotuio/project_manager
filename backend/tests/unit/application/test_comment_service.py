"""EP-07 Phase 3 — CommentService unit tests."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.application.services.comment_service import (
    CommentForbiddenError,
    CommentNotFoundError,
    CommentService,
)
from app.domain.models.comment import (
    AnchorInvalidError,
    AnchorStatus,
    Comment,
    CommentActorType,
    NestingExceededError,
)
from app.domain.models.timeline_event import TimelineEvent
from app.domain.repositories.comment_repository import ICommentRepository
from app.domain.repositories.timeline_repository import ITimelineEventRepository


class FakeCommentRepo(ICommentRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, Comment] = {}

    async def create(self, comment: Comment) -> Comment:
        self._store[comment.id] = comment
        return comment

    async def get(self, comment_id: UUID) -> Comment | None:
        return self._store.get(comment_id)

    async def list_for_work_item(self, work_item_id: UUID) -> list[Comment]:
        return [c for c in self._store.values() if c.work_item_id == work_item_id and c.deleted_at is None]

    async def save(self, comment: Comment) -> Comment:
        self._store[comment.id] = comment
        return comment


class FakeTimelineRepo(ITimelineEventRepository):
    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    async def insert(self, event: TimelineEvent) -> TimelineEvent:
        self._events.append(event)
        return event

    async def list_for_work_item(
        self,
        work_item_id: UUID,
        *,
        before_occurred_at: datetime | None = None,
        before_id: UUID | None = None,
        limit: int = 50,
    ) -> list[TimelineEvent]:
        return [e for e in self._events if e.work_item_id == work_item_id]


def _make_service(comment_repo: FakeCommentRepo, timeline_repo: FakeTimelineRepo | None = None) -> CommentService:
    return CommentService(
        comment_repo=comment_repo,
        timeline_repo=timeline_repo,
    )


class TestCreateComment:
    @pytest.mark.asyncio
    async def test_general_comment_created(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)
        work_item_id = uuid4()

        c = await svc.create(work_item_id=work_item_id, body="Hello", actor_id=uuid4())
        assert c.work_item_id == work_item_id
        assert c.anchor_status == AnchorStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_anchor_invalid_range_raises(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)

        with pytest.raises(AnchorInvalidError):
            await svc.create(
                work_item_id=uuid4(),
                body="anchored",
                actor_id=uuid4(),
                anchor_section_id=uuid4(),
                anchor_start_offset=10,
                anchor_end_offset=5,
            )

    @pytest.mark.asyncio
    async def test_anchor_without_section_raises(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)

        with pytest.raises(AnchorInvalidError):
            await svc.create(
                work_item_id=uuid4(),
                body="anchored",
                actor_id=uuid4(),
                anchor_start_offset=0,
                anchor_end_offset=5,
            )

    @pytest.mark.asyncio
    async def test_reply_to_reply_raises_nesting_error(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)
        work_item_id = uuid4()

        # Create root comment
        root = await svc.create(work_item_id=work_item_id, body="root", actor_id=uuid4())
        # Create reply to root
        reply = await svc.create(work_item_id=work_item_id, body="reply", actor_id=uuid4(), parent_comment_id=root.id)
        # Attempt reply to reply
        with pytest.raises(NestingExceededError):
            await svc.create(work_item_id=work_item_id, body="deep", actor_id=uuid4(), parent_comment_id=reply.id)

    @pytest.mark.asyncio
    async def test_comment_added_timeline_event_emitted(self) -> None:
        comment_repo = FakeCommentRepo()
        timeline_repo = FakeTimelineRepo()
        svc = _make_service(comment_repo, timeline_repo)

        await svc.create(
            work_item_id=uuid4(),
            body="Hello",
            actor_id=uuid4(),
            workspace_id=uuid4(),
        )
        assert len(timeline_repo._events) == 1
        assert timeline_repo._events[0].event_type == "comment_added"

    @pytest.mark.asyncio
    async def test_no_timeline_repo_doesnt_crash(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo, timeline_repo=None)

        c = await svc.create(work_item_id=uuid4(), body="Hello", actor_id=uuid4())
        assert c is not None


class TestEditComment:
    @pytest.mark.asyncio
    async def test_author_can_edit(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)
        actor_id = uuid4()

        c = await svc.create(work_item_id=uuid4(), body="original", actor_id=actor_id)
        updated = await svc.edit(comment_id=c.id, new_body="updated", actor_id=actor_id)
        assert updated.body == "updated"
        assert updated.is_edited is True

    @pytest.mark.asyncio
    async def test_non_author_cannot_edit(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)

        c = await svc.create(work_item_id=uuid4(), body="original", actor_id=uuid4())
        with pytest.raises(CommentForbiddenError):
            await svc.edit(comment_id=c.id, new_body="hacked", actor_id=uuid4())

    @pytest.mark.asyncio
    async def test_ai_comment_cannot_be_edited(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)
        actor_id = uuid4()

        ai_comment = Comment.create(
            work_item_id=uuid4(),
            body="AI suggestion",
            actor_id=actor_id,
            actor_type=CommentActorType.AI_SUGGESTION,
        )
        repo._store[ai_comment.id] = ai_comment

        with pytest.raises(CommentForbiddenError, match="ai"):
            await svc.edit(comment_id=ai_comment.id, new_body="changed", actor_id=actor_id)

    @pytest.mark.asyncio
    async def test_edit_not_found(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)
        with pytest.raises(CommentNotFoundError):
            await svc.edit(comment_id=uuid4(), new_body="x", actor_id=uuid4())


class TestDeleteComment:
    @pytest.mark.asyncio
    async def test_author_can_soft_delete(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)
        actor_id = uuid4()

        c = await svc.create(work_item_id=uuid4(), body="bye", actor_id=actor_id)
        deleted = await svc.delete(comment_id=c.id, actor_id=actor_id)
        assert deleted.deleted_at is not None

    @pytest.mark.asyncio
    async def test_non_author_cannot_delete(self) -> None:
        repo = FakeCommentRepo()
        svc = _make_service(repo)

        c = await svc.create(work_item_id=uuid4(), body="bye", actor_id=uuid4())
        with pytest.raises(CommentForbiddenError):
            await svc.delete(comment_id=c.id, actor_id=uuid4())

    @pytest.mark.asyncio
    async def test_delete_emits_timeline_event(self) -> None:
        comment_repo = FakeCommentRepo()
        timeline_repo = FakeTimelineRepo()
        svc = _make_service(comment_repo, timeline_repo)
        actor_id = uuid4()

        c = await svc.create(
            work_item_id=uuid4(),
            body="bye",
            actor_id=actor_id,
            workspace_id=uuid4(),
        )
        timeline_repo._events.clear()  # reset after create event

        await svc.delete(comment_id=c.id, actor_id=actor_id, workspace_id=uuid4())
        assert len(timeline_repo._events) == 1
        assert timeline_repo._events[0].event_type == "comment_deleted"
