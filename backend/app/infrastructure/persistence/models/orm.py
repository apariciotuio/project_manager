"""SQLAlchemy ORM models for EP-00 and EP-01.

Kept separate from domain entities (`app.domain.models.*`) so the domain stays pure.
Mappers live in each repository impl and convert ORM rows ↔ domain dataclasses.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class UserORM(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','suspended','deleted')", name="users_status_check"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="active")
    is_superadmin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SessionORM(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_user_id", "user_id"),
        Index("idx_sessions_expires_at", "expires_at"),
        Index(
            "idx_sessions_user_active",
            "user_id",
            sa.text("expires_at DESC"),
            postgresql_where=sa.text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkspaceORM(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','suspended','deleted')", name="workspaces_status_check"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorkspaceMembershipORM(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_membership_ws_user"),
        CheckConstraint(
            "state IN ('invited','active','suspended','deleted')",
            name="workspace_memberships_state_check",
        ),
        Index("idx_workspace_memberships_user_state", "user_id", "state"),
        Index("idx_workspace_memberships_workspace_state", "workspace_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="member")
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEventORM(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "category IN ('auth','admin','domain')", name="audit_events_category_check"
        ),
        Index(
            "idx_audit_events_actor",
            "workspace_id",
            "actor_id",
            sa.text("created_at DESC"),
        ),
        Index(
            "idx_audit_events_entity",
            "workspace_id",
            "entity_type",
            "entity_id",
            sa.text("created_at DESC"),
        ),
        Index(
            "idx_audit_events_action",
            "workspace_id",
            "action",
            sa.text("created_at DESC"),
        ),
        # idx_audit_events_category dropped in 0008 — no read path until EP-10+
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_display: Mapped[str | None] = mapped_column(Text, nullable=True)
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(nullable=True)  # no FK — polymorphic reference across entities (users/workspaces/memberships/sessions)
    before_value: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    context: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OAuthStateORM(Base):
    __tablename__ = "oauth_states"
    __table_args__ = (Index("idx_oauth_states_expires_at", "expires_at"),)

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    return_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_chosen_workspace_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# EP-01 — Work Items
# ---------------------------------------------------------------------------

_WORK_ITEM_STATES = (
    "'draft','in_clarification','in_review','changes_requested',"
    "'partially_validated','ready','exported'"
)

_WORK_ITEM_TYPES = (
    "'idea','bug','enhancement','task','initiative','spike','business_change',"
    "'requirement','story','milestone'"
)


class WorkItemORM(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({_WORK_ITEM_TYPES})",
            name="work_items_type_valid",
        ),
        CheckConstraint(
            f"state IN ({_WORK_ITEM_STATES})",
            name="work_items_state_valid",
        ),
        CheckConstraint(
            "char_length(trim(title)) BETWEEN 3 AND 255",
            name="work_items_title_length",
        ),
        CheckConstraint(
            "priority IS NULL OR priority IN ('low','medium','high','critical')",
            name="work_items_priority_valid",
        ),
        CheckConstraint(
            "completeness_score BETWEEN 0 AND 100",
            name="work_items_completeness_range",
        ),
        CheckConstraint(
            "attachment_count >= 0",
            name="work_items_attachment_count_nonneg",
        ),
        Index("idx_work_items_workspace_state", "workspace_id", "state"),
        Index(
            "idx_work_items_active",
            "workspace_id",
            sa.text("updated_at DESC"),
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
        Index("idx_work_items_owner", "owner_id"),
        Index("idx_work_items_parent", "parent_work_item_id"),
        Index("idx_work_items_tags", "tags", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    # TODO(EP-10): add FK REFERENCES projects(id) once projects table exists
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    due_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=sa.text("'{}'")
    )
    completeness_score: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="0"
    )
    parent_work_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_items.id", ondelete="SET NULL"), nullable=True
    )
    materialized_path: Mapped[str] = mapped_column(Text, nullable=False, server_default="''")
    attachment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    creator_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    has_override: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    override_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_suspended_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # EP-02 additions
    draft_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    export_reference: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# EP-02 — Work Item Drafts and Templates
# ---------------------------------------------------------------------------

_TEMPLATE_TYPES = (
    "'idea','bug','enhancement','task','initiative','spike','business_change','requirement'"
)


class WorkItemDraftORM(Base):
    __tablename__ = "work_item_drafts"
    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="work_item_drafts_unique_user_workspace"),
        Index("idx_work_item_drafts_expires", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    local_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    incomplete: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TemplateORM(Base):
    __tablename__ = "templates"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({_TEMPLATE_TYPES})",
            name="templates_type_valid",
        ),
        CheckConstraint(
            "char_length(content) <= 50000",
            name="templates_content_length",
        ),
        CheckConstraint(
            "NOT (is_system = TRUE AND workspace_id IS NOT NULL)",
            name="templates_system_no_workspace",
        ),
        Index(
            "idx_templates_workspace_type",
            "workspace_id",
            "type",
            unique=True,
            postgresql_where=sa.text("workspace_id IS NOT NULL"),
        ),
        Index(
            "idx_templates_system_type",
            "type",
            unique=True,
            postgresql_where=sa.text("is_system = TRUE"),
        ),
        Index(
            "idx_templates_workspace",
            "workspace_id",
            postgresql_where=sa.text("workspace_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# EP-03 — Conversation Threads, Assistant Suggestions, Gap Findings
# ---------------------------------------------------------------------------


class ConversationThreadORM(Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "work_item_id", name="conversation_threads_unique_user_work_item"
        ),
        Index("idx_conversation_threads_user", "user_id"),
        Index(
            "idx_conversation_threads_work_item",
            "work_item_id",
            postgresql_where=sa.text("work_item_id IS NOT NULL"),
        ),
        Index("idx_conversation_threads_workspace", "workspace_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    work_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_items.id", ondelete="SET NULL"), nullable=True
    )
    dundun_conversation_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


_SUGGESTION_STATUSES = "'pending','accepted','rejected','expired','applied'"


class AssistantSuggestionORM(Base):
    __tablename__ = "assistant_suggestions"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_SUGGESTION_STATUSES})",
            name="assistant_suggestions_status_valid",
        ),
        Index("idx_as_work_item_batch", "work_item_id", "batch_id", "status"),
        Index(
            "idx_as_work_item_created",
            "work_item_id",
            sa.text("created_at DESC"),
        ),
        Index("idx_as_batch", "batch_id"),
        Index(
            "idx_as_dundun_request",
            "dundun_request_id",
            postgresql_where=sa.text("dundun_request_id IS NOT NULL"),
        ),
        Index("idx_assistant_suggestions_workspace", "workspace_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation_threads.id", ondelete="SET NULL"), nullable=True
    )
    section_id: Mapped[UUID | None] = mapped_column(nullable=True)
    proposed_content: Mapped[str] = mapped_column(Text, nullable=False)
    current_content: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    version_number_target: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_id: Mapped[UUID] = mapped_column(nullable=False)
    dundun_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GapFindingORM(Base):
    __tablename__ = "gap_findings"
    __table_args__ = (
        CheckConstraint(
            "source IN ('rule', 'dundun')",
            name="gap_findings_source_valid",
        ),
        CheckConstraint(
            "severity IN ('blocking', 'warning', 'info')",
            name="gap_findings_severity_valid",
        ),
        Index("idx_gap_findings_work_item", "work_item_id", "source", "severity"),
        Index(
            "idx_gap_findings_active",
            "work_item_id",
            postgresql_where=sa.text("invalidated_at IS NULL"),
        ),
        Index("idx_gap_findings_workspace", "workspace_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    dimension: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    dundun_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StateTransitionORM(Base):
    __tablename__ = "state_transitions"
    __table_args__ = (
        CheckConstraint(
            f"from_state IS NULL OR from_state IN ({_WORK_ITEM_STATES})",
            name="state_transitions_from_state_valid",
        ),
        CheckConstraint(
            f"to_state IN ({_WORK_ITEM_STATES})",
            name="state_transitions_to_state_valid",
        ),
        Index(
            "idx_state_transitions_item",
            "work_item_id",
            sa.text("triggered_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        nullable=True  # FK dropped by migration 0010; NULL = system actor
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_override: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    override_justification: Mapped[str | None] = mapped_column(Text, nullable=True)


class OwnershipHistoryORM(Base):
    __tablename__ = "ownership_history"
    __table_args__ = (
        Index(
            "idx_ownership_history_item",
            "work_item_id",
            sa.text("changed_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    previous_owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    new_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# EP-04 — Sections, Validators, Versions
# ---------------------------------------------------------------------------


class WorkItemSectionORM(Base):
    __tablename__ = "work_item_sections"
    __table_args__ = (
        CheckConstraint(
            "generation_source IN ('llm', 'manual', 'revert')",
            name="work_item_sections_generation_source_valid",
        ),
        UniqueConstraint(
            "work_item_id", "section_type", name="uq_work_item_section_type"
        ),
        Index("idx_work_item_sections_work_item_id", "work_item_id"),
        Index(
            "idx_wis_completeness",
            "work_item_id",
            "is_required",
            "section_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    section_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    generation_source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="llm"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class WorkItemSectionVersionORM(Base):
    __tablename__ = "work_item_section_versions"
    __table_args__ = (
        CheckConstraint(
            "generation_source IN ('llm', 'manual', 'revert')",
            name="work_item_section_versions_generation_source_valid",
        ),
        Index("idx_section_versions_section_id", "section_id"),
        Index("idx_section_versions_work_item_id", "work_item_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    section_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_item_sections.id", ondelete="CASCADE"), nullable=False
    )
    work_item_id: Mapped[UUID] = mapped_column(nullable=False)
    section_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_source: Mapped[str] = mapped_column(String(16), nullable=False)
    revert_from_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class WorkItemValidatorORM(Base):
    __tablename__ = "work_item_validators"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'changes_requested', 'declined')",
            name="work_item_validators_status_valid",
        ),
        UniqueConstraint("work_item_id", "role", name="uq_work_item_validator"),
        Index("idx_work_item_validators_work_item", "work_item_id", "status"),
        Index(
            "idx_work_item_validators_user_pending",
            "user_id",
            postgresql_where=sa.text("status = 'pending'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WorkItemVersionORM(Base):
    __tablename__ = "work_item_versions"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id", "version_number", name="uq_work_item_version"
        ),
        Index("idx_wiv_work_item_created", "work_item_id", sa.text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # EP-07 additive columns
    snapshot_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    trigger: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="content_edit"
    )
    actor_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="human"
    )
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    commit_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


# ---------------------------------------------------------------------------
# EP-05 — Task nodes, dependencies
# ---------------------------------------------------------------------------


class TaskNodeORM(Base):
    __tablename__ = "task_nodes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_progress', 'done')",
            name="task_nodes_status_valid",
        ),
        Index("idx_task_nodes_work_item_id", "work_item_id"),
        Index("idx_task_nodes_parent_id", "parent_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    generation_source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="llm"
    )
    materialized_path: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class TaskDependencyORM(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="uq_task_dependency"),
        CheckConstraint("source_id != target_id", name="no_self_dependency"),
        Index("idx_task_dep_source", "source_id"),
        Index("idx_task_dep_target", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[UUID] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class TaskNodeSectionLinkORM(Base):
    __tablename__ = "task_node_section_links"
    __table_args__ = (
        UniqueConstraint("task_id", "section_id", name="uq_task_section_link"),
        Index("idx_tnsl_task_id", "task_id"),
        Index("idx_tnsl_section_id", "section_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_item_sections.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# EP-06 — Reviews, Validation
# ---------------------------------------------------------------------------


class ValidationRequirementORM(Base):
    __tablename__ = "validation_requirements"

    rule_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Legacy text column kept for backwards compat with 0023 migration
    applies_to: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # Columns added by 0060 migration
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReviewRequestORM(Base):
    __tablename__ = "review_requests"
    __table_args__ = (
        Index("idx_review_requests_work_item", "work_item_id"),
        Index("idx_review_requests_status", "work_item_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_item_versions.id"), nullable=False
    )
    reviewer_type: Mapped[str] = mapped_column(String(10), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    team_id: Mapped[UUID | None] = mapped_column(nullable=True)
    validation_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("validation_requirements.rule_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(15), nullable=False, server_default="pending")
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewResponseORM(Base):
    __tablename__ = "review_responses"
    __table_args__ = (
        Index("idx_review_responses_request", "review_request_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    review_request_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_requests.id", ondelete="CASCADE"), nullable=False
    )
    responder_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ValidationStatusORM(Base):
    __tablename__ = "validation_status"
    __table_args__ = (
        UniqueConstraint("work_item_id", "rule_id", name="uq_validation_status"),
        Index("idx_validation_status_work_item", "work_item_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("validation_requirements.rule_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(15), nullable=False, server_default="pending")
    passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    passed_by_review_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review_requests.id"), nullable=True
    )
    waived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waived_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    waive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# EP-07 — Comments, Timeline
# ---------------------------------------------------------------------------


class CommentORM(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("idx_comments_work_item", "work_item_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    parent_comment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    anchor_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_item_sections.id", ondelete="SET NULL"), nullable=True
    )
    anchor_start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor_end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor_snapshot_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    is_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TimelineEventORM(Base):
    __tablename__ = "timeline_events"
    __table_args__ = (
        Index("idx_timeline_work_item", "work_item_id", sa.text("occurred_at DESC")),
        Index("idx_timeline_workspace_occurred", "workspace_id", sa.text("occurred_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="RESTRICT"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    actor_display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_table: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# EP-08 — Teams, Notifications
# ---------------------------------------------------------------------------


class TeamORM(Base):
    __tablename__ = "teams"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_receive_reviews: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class TeamMembershipORM(Base):
    __tablename__ = "team_memberships"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_membership_active"),
        Index(
            "idx_team_memberships_team_active",
            "team_id",
            "joined_at",
            postgresql_where=text("removed_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationORM(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unread")
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(nullable=False)
    deeplink: Mapped[str] = mapped_column(Text, nullable=False)
    quick_action: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# EP-09 — Saved Searches
# ---------------------------------------------------------------------------


class SavedSearchORM(Base):
    __tablename__ = "saved_searches"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    query_params: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# EP-10 — Projects, Routing Rules, Integration Configs
# ---------------------------------------------------------------------------


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class RoutingRuleORM(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        CheckConstraint(
            f"work_item_type IN ({_WORK_ITEM_TYPES})",
            name="routing_rules_type_check",
        ),
        Index(
            "idx_routing_rules_lookup",
            "workspace_id",
            "work_item_type",
            sa.text("priority DESC"),
            postgresql_where=sa.text("active = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    work_item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    suggested_team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    suggested_owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    suggested_validators: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class IntegrationConfigORM(Base):
    __tablename__ = "integration_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    integration_type: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    mapping: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


# ---------------------------------------------------------------------------
# EP-10 — Validation Rule Templates
# ---------------------------------------------------------------------------

_REQUIREMENT_TYPES = (
    "'section_content','reviewer_approval','validator_approval','custom'"
)


class ValidationRuleTemplateORM(Base):
    __tablename__ = "validation_rule_templates"
    __table_args__ = (
        CheckConstraint(
            f"requirement_type IN ({_REQUIREMENT_TYPES})",
            name="vrt_requirement_type_check",
        ),
        CheckConstraint(
            "workspace_id IS NULL OR true",  # placeholder — global templates allowed
            name="vrt_global_allowed",
        ),
        Index(
            "idx_vrt_workspace_type",
            "workspace_id",
            "work_item_type",
            postgresql_where=sa.text("active = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    work_item_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    requirement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    default_dimension: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# EP-11 — Integration Exports
# ---------------------------------------------------------------------------


class IntegrationExportORM(Base):
    __tablename__ = "integration_exports"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    integration_config_id: Mapped[UUID] = mapped_column(
        ForeignKey("integration_configs.id", ondelete="CASCADE"), nullable=False
    )
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    external_key: Mapped[str] = mapped_column(String(128), nullable=False)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    exported_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


# ---------------------------------------------------------------------------
# EP-13 — Puppet Sync Outbox
# ---------------------------------------------------------------------------


class PuppetSyncOutboxORM(Base):
    __tablename__ = "puppet_sync_outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# EP-13 — Puppet Ingest Requests
# ---------------------------------------------------------------------------


class PuppetIngestRequestORM(Base):
    __tablename__ = "puppet_ingest_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    work_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_items.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    puppet_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# EP-15 — Tags
# ---------------------------------------------------------------------------


class TagORM(Base):
    __tablename__ = "tags"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class WorkItemTagORM(Base):
    __tablename__ = "work_item_tags"
    __table_args__ = (
        UniqueConstraint("work_item_id", "tag_id", name="uq_work_item_tag"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


# ---------------------------------------------------------------------------
# EP-16 — Attachments
# ---------------------------------------------------------------------------


class AttachmentORM(Base):
    __tablename__ = "attachments"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    work_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=True
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


# ---------------------------------------------------------------------------
# EP-17 — Section Locks
# ---------------------------------------------------------------------------


class SectionLockORM(Base):
    __tablename__ = "section_locks"
    __table_args__ = (
        UniqueConstraint("section_id", name="uq_section_lock_active"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    section_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_item_sections.id", ondelete="CASCADE"), nullable=False
    )
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    held_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    force_released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    force_released_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
