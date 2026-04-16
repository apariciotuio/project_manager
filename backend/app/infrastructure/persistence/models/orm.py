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
    "'idea','bug','enhancement','task','initiative','spike','business_change','requirement'"
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
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
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


_SUGGESTION_STATUSES = "'pending','accepted','rejected','expired'"


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
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
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
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
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
