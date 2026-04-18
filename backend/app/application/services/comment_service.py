"""EP-07 — CommentService: create, edit, delete.

Timeline events are emitted in-band (same call, not transactionally isolated).
If a timeline_repo is injected, comment_added / comment_deleted events are
appended. Callers that need transactional atomicity (test 3.23a) must ensure
both operations are executed inside the same DB session.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.models.comment import Comment, CommentActorType, NestingExceededError
from app.domain.models.timeline_event import TimelineActorType, TimelineEvent
from app.domain.repositories.comment_repository import ICommentRepository
from app.domain.repositories.timeline_repository import ITimelineEventRepository


class CommentNotFoundError(Exception):
    pass


class CommentForbiddenError(Exception):
    pass


class CommentService:
    def __init__(
        self,
        *,
        comment_repo: ICommentRepository,
        timeline_repo: ITimelineEventRepository | None = None,
    ) -> None:
        self._repo = comment_repo
        self._timeline = timeline_repo

    async def create(
        self,
        *,
        work_item_id: UUID,
        body: str,
        actor_id: UUID | None,
        parent_comment_id: UUID | None = None,
        actor_type: CommentActorType = CommentActorType.HUMAN,
        anchor_section_id: UUID | None = None,
        anchor_start_offset: int | None = None,
        anchor_end_offset: int | None = None,
        anchor_snapshot_text: str | None = None,
        workspace_id: UUID | None = None,
    ) -> Comment:
        if parent_comment_id is not None:
            parent = await self._repo.get(parent_comment_id)
            if parent is None:
                raise CommentNotFoundError(f"parent comment {parent_comment_id} not found")
            if parent.parent_comment_id is not None:
                raise NestingExceededError(
                    "replies to replies are not allowed (single-level nesting only)"
                )

        comment = Comment.create(
            work_item_id=work_item_id,
            body=body,
            actor_id=actor_id,
            parent_comment_id=parent_comment_id,
            actor_type=actor_type,
            anchor_section_id=anchor_section_id,
            anchor_start_offset=anchor_start_offset,
            anchor_end_offset=anchor_end_offset,
            anchor_snapshot_text=anchor_snapshot_text,
        )
        result = await self._repo.create(comment)

        if self._timeline is not None and workspace_id is not None:
            event = TimelineEvent.create(
                work_item_id=work_item_id,
                workspace_id=workspace_id,
                event_type="comment_added",
                actor_type=TimelineActorType(actor_type.value),
                actor_id=actor_id,
                summary="Comment added",
                source_id=result.id,
                source_table="comments",
            )
            await self._timeline.insert(event)

        return result

    async def edit(
        self,
        *,
        comment_id: UUID,
        new_body: str,
        actor_id: UUID,
    ) -> Comment:
        comment = await self._repo.get(comment_id)
        if comment is None:
            raise CommentNotFoundError(f"comment {comment_id} not found")
        if comment.actor_type == CommentActorType.AI_SUGGESTION:
            raise CommentForbiddenError("ai suggestion comments cannot be edited")
        if comment.actor_id != actor_id:
            raise CommentForbiddenError("only the author can edit a comment")
        if comment.deleted_at is not None:
            raise CommentForbiddenError("cannot edit a deleted comment")
        comment.edit(new_body)
        return await self._repo.save(comment)

    async def delete(
        self,
        *,
        comment_id: UUID,
        actor_id: UUID,
        workspace_id: UUID | None = None,
    ) -> Comment:
        comment = await self._repo.get(comment_id)
        if comment is None:
            raise CommentNotFoundError(f"comment {comment_id} not found")
        if comment.actor_id != actor_id:
            raise CommentForbiddenError("only the author can delete a comment")
        comment.soft_delete()
        result = await self._repo.save(comment)

        if self._timeline is not None and workspace_id is not None:
            event = TimelineEvent.create(
                work_item_id=comment.work_item_id,
                workspace_id=workspace_id,
                event_type="comment_deleted",
                actor_type=TimelineActorType(comment.actor_type.value),
                actor_id=actor_id,
                summary="Comment deleted",
                source_id=comment_id,
                source_table="comments",
            )
            await self._timeline.insert(event)

        return result

    async def list_for_work_item(self, work_item_id: UUID) -> list[Comment]:
        return await self._repo.list_for_work_item(work_item_id)
