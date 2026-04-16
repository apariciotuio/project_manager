"""Mapper for Comment — EP-07."""
from __future__ import annotations

from app.domain.models.comment import AnchorStatus, Comment, CommentActorType
from app.infrastructure.persistence.models.orm import CommentORM


def comment_to_domain(row: CommentORM) -> Comment:
    return Comment(
        id=row.id,
        work_item_id=row.work_item_id,
        parent_comment_id=row.parent_comment_id,
        body=row.body,
        actor_type=CommentActorType(row.actor_type),
        actor_id=row.actor_id,
        anchor_section_id=row.anchor_section_id,
        anchor_start_offset=row.anchor_start_offset,
        anchor_end_offset=row.anchor_end_offset,
        anchor_snapshot_text=row.anchor_snapshot_text,
        anchor_status=AnchorStatus(row.anchor_status),
        is_edited=row.is_edited,
        edited_at=row.edited_at,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
    )


def comment_to_orm(entity: Comment) -> CommentORM:
    row = CommentORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.parent_comment_id = entity.parent_comment_id
    row.body = entity.body
    row.actor_type = entity.actor_type.value
    row.actor_id = entity.actor_id
    row.anchor_section_id = entity.anchor_section_id
    row.anchor_start_offset = entity.anchor_start_offset
    row.anchor_end_offset = entity.anchor_end_offset
    row.anchor_snapshot_text = entity.anchor_snapshot_text
    row.anchor_status = entity.anchor_status.value
    row.is_edited = entity.is_edited
    row.edited_at = entity.edited_at
    row.deleted_at = entity.deleted_at
    row.created_at = entity.created_at
    return row
