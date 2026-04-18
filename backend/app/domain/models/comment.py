"""EP-07 — Comment entity.

Single-level nesting enforced at the application layer (PostgreSQL CHECK
cannot express sub-queries). CommentService.create_reply refuses to create a
reply when the parent already has a non-NULL parent_comment_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class CommentActorType(StrEnum):
    HUMAN = "human"
    AI_SUGGESTION = "ai_suggestion"
    SYSTEM = "system"


class AnchorStatus(StrEnum):
    ACTIVE = "active"
    ORPHANED = "orphaned"


class NestingExceededError(Exception):
    pass


class AnchorInvalidError(Exception):
    pass


@dataclass
class Comment:
    id: UUID
    work_item_id: UUID
    parent_comment_id: UUID | None
    body: str
    actor_type: CommentActorType
    actor_id: UUID | None
    anchor_section_id: UUID | None
    anchor_start_offset: int | None
    anchor_end_offset: int | None
    anchor_snapshot_text: str | None
    anchor_status: AnchorStatus
    is_edited: bool
    edited_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime

    @classmethod
    def create(
        cls,
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
        if not body.strip():
            raise ValueError("comment body cannot be empty")
        if len(body) > 10000:
            raise ValueError("comment body exceeds 10000 characters")
        if anchor_start_offset is not None:
            if anchor_end_offset is None or anchor_end_offset < anchor_start_offset:
                raise AnchorInvalidError("anchor range is invalid")
            if anchor_section_id is None:
                raise AnchorInvalidError("anchor_section_id is required when offsets are provided")
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            parent_comment_id=parent_comment_id,
            body=body,
            actor_type=actor_type,
            actor_id=actor_id,
            anchor_section_id=anchor_section_id,
            anchor_start_offset=anchor_start_offset,
            anchor_end_offset=anchor_end_offset,
            anchor_snapshot_text=anchor_snapshot_text,
            anchor_status=AnchorStatus.ACTIVE,
            is_edited=False,
            edited_at=None,
            deleted_at=None,
            created_at=datetime.now(UTC),
        )

    def edit(self, new_body: str) -> None:
        if not new_body.strip() or len(new_body) > 10000:
            raise ValueError("invalid comment body")
        self.body = new_body
        self.is_edited = True
        self.edited_at = datetime.now(UTC)

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(UTC)
