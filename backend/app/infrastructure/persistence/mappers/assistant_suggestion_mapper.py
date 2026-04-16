"""Mapper between AssistantSuggestion domain entity and AssistantSuggestionORM."""
from __future__ import annotations

from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus
from app.infrastructure.persistence.models.orm import AssistantSuggestionORM


def to_domain(row: AssistantSuggestionORM) -> AssistantSuggestion:
    return AssistantSuggestion(
        id=row.id,
        work_item_id=row.work_item_id,
        thread_id=row.thread_id,
        section_id=row.section_id,
        proposed_content=row.proposed_content,
        current_content=row.current_content,
        rationale=row.rationale,
        status=SuggestionStatus(row.status),
        version_number_target=row.version_number_target,
        batch_id=row.batch_id,
        dundun_request_id=row.dundun_request_id,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        expires_at=row.expires_at,
    )


def to_orm(entity: AssistantSuggestion) -> AssistantSuggestionORM:
    row = AssistantSuggestionORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.thread_id = entity.thread_id
    row.section_id = entity.section_id
    row.proposed_content = entity.proposed_content
    row.current_content = entity.current_content
    row.rationale = entity.rationale
    row.status = entity.status.value
    row.version_number_target = entity.version_number_target
    row.batch_id = entity.batch_id
    row.dundun_request_id = entity.dundun_request_id
    row.created_by = entity.created_by
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.expires_at = entity.expires_at
    return row
