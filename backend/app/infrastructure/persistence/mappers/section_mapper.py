"""Mappers for Section, SectionVersion, Validator, WorkItemVersion — EP-04."""
from __future__ import annotations

from app.domain.models.section import Section
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.models.section_version import SectionVersion
from app.domain.models.validator import Validator, ValidatorStatus
from app.domain.models.work_item_version import WorkItemVersion
from app.infrastructure.persistence.models.orm import (
    WorkItemSectionORM,
    WorkItemSectionVersionORM,
    WorkItemValidatorORM,
    WorkItemVersionORM,
)

# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------


def section_to_domain(row: WorkItemSectionORM) -> Section:
    return Section(
        id=row.id,
        work_item_id=row.work_item_id,
        section_type=SectionType(row.section_type),
        content=row.content,
        display_order=row.display_order,
        is_required=row.is_required,
        generation_source=GenerationSource(row.generation_source),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by=row.created_by,
        updated_by=row.updated_by,
        workspace_id=row.workspace_id,
    )


def section_to_orm(entity: Section) -> WorkItemSectionORM:
    row = WorkItemSectionORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.section_type = entity.section_type.value
    row.content = entity.content
    row.display_order = entity.display_order
    row.is_required = entity.is_required
    row.generation_source = entity.generation_source.value
    row.version = entity.version
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.created_by = entity.created_by
    row.updated_by = entity.updated_by
    if entity.workspace_id is not None:
        row.workspace_id = entity.workspace_id
    return row


# ---------------------------------------------------------------------------
# SectionVersion
# ---------------------------------------------------------------------------


def section_version_to_domain(row: WorkItemSectionVersionORM) -> SectionVersion:
    return SectionVersion(
        id=row.id,
        section_id=row.section_id,
        work_item_id=row.work_item_id,
        section_type=SectionType(row.section_type),
        content=row.content,
        version=row.version,
        generation_source=GenerationSource(row.generation_source),
        revert_from_version=row.revert_from_version,
        created_at=row.created_at,
        created_by=row.created_by,
        workspace_id=row.workspace_id,
    )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validator_to_domain(row: WorkItemValidatorORM) -> Validator:
    return Validator(
        id=row.id,
        work_item_id=row.work_item_id,
        user_id=row.user_id,
        role=row.role,
        status=ValidatorStatus(row.status),
        assigned_at=row.assigned_at,
        assigned_by=row.assigned_by,
        responded_at=row.responded_at,
        workspace_id=row.workspace_id,
    )


def validator_to_orm(entity: Validator) -> WorkItemValidatorORM:
    row = WorkItemValidatorORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.user_id = entity.user_id
    row.role = entity.role
    row.status = entity.status.value
    row.assigned_at = entity.assigned_at
    row.assigned_by = entity.assigned_by
    row.responded_at = entity.responded_at
    if entity.workspace_id is not None:
        row.workspace_id = entity.workspace_id
    return row


# ---------------------------------------------------------------------------
# WorkItemVersion
# ---------------------------------------------------------------------------


def work_item_version_to_domain(row: WorkItemVersionORM) -> WorkItemVersion:
    from app.domain.models.work_item_version import VersionActorType, VersionTrigger

    return WorkItemVersion(
        id=row.id,
        work_item_id=row.work_item_id,
        version_number=row.version_number,
        snapshot=dict(row.snapshot),
        created_by=row.created_by,
        created_at=row.created_at,
        snapshot_schema_version=getattr(row, "snapshot_schema_version", 1),
        trigger=VersionTrigger(getattr(row, "trigger", "content_edit")),
        actor_type=VersionActorType(getattr(row, "actor_type", "human")),
        actor_id=getattr(row, "actor_id", None),
        commit_message=getattr(row, "commit_message", None),
        archived=getattr(row, "archived", False),
        workspace_id=getattr(row, "workspace_id", None),
    )
