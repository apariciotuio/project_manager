"""EP-07 — CommentService: create, edit, delete."""
from __future__ import annotations

from uuid import UUID

from app.domain.models.comment import Comment, CommentActorType, NestingExceededError
from app.domain.repositories.comment_repository import ICommentRepository


class CommentNotFoundError(Exception):
    pass


class CommentForbiddenError(Exception):
    pass


class CommentService:
    def __init__(self, *, comment_repo: ICommentRepository) -> None:
        self._repo = comment_repo

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
        return await self._repo.create(comment)

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
    ) -> Comment:
        comment = await self._repo.get(comment_id)
        if comment is None:
            raise CommentNotFoundError(f"comment {comment_id} not found")
        if comment.actor_id != actor_id:
            raise CommentForbiddenError("only the author can delete a comment")
        comment.soft_delete()
        return await self._repo.save(comment)

    async def list_for_work_item(self, work_item_id: UUID) -> list[Comment]:
        return await self._repo.list_for_work_item(work_item_id)
