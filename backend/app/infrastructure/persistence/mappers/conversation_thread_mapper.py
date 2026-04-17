"""Mapper between ConversationThread domain entity and ConversationThreadORM."""
from __future__ import annotations

from app.domain.models.conversation_thread import ConversationThread
from app.infrastructure.persistence.models.orm import ConversationThreadORM


def to_domain(row: ConversationThreadORM) -> ConversationThread:
    return ConversationThread(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        work_item_id=row.work_item_id,
        dundun_conversation_id=row.dundun_conversation_id,
        last_message_preview=row.last_message_preview,
        last_message_at=row.last_message_at,
        created_at=row.created_at,
        deleted_at=row.deleted_at,
    )


def to_orm(entity: ConversationThread) -> ConversationThreadORM:
    row = ConversationThreadORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.user_id = entity.user_id
    row.work_item_id = entity.work_item_id
    row.dundun_conversation_id = entity.dundun_conversation_id
    row.last_message_preview = entity.last_message_preview
    row.last_message_at = entity.last_message_at
    row.created_at = entity.created_at
    row.deleted_at = entity.deleted_at
    return row
