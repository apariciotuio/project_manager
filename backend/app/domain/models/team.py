"""EP-08 — Team + TeamMembership + Notification entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class TeamRole(StrEnum):
    MEMBER = "member"
    LEAD = "lead"


class NotificationState(StrEnum):
    UNREAD = "unread"
    READ = "read"
    ACTIONED = "actioned"


@dataclass
class Team:
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    can_receive_reviews: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        name: str,
        created_by: UUID,
        description: str | None = None,
        can_receive_reviews: bool = False,
    ) -> Team:
        if not name.strip():
            raise ValueError("team name cannot be empty")
        if len(name) > 255:
            raise ValueError("team name exceeds 255 characters")
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name.strip(),
            description=description,
            can_receive_reviews=can_receive_reviews,
            deleted_at=None,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


@dataclass
class TeamMembership:
    id: UUID
    team_id: UUID
    user_id: UUID
    role: TeamRole
    joined_at: datetime
    removed_at: datetime | None

    @classmethod
    def create(
        cls,
        *,
        team_id: UUID,
        user_id: UUID,
        role: TeamRole = TeamRole.MEMBER,
    ) -> TeamMembership:
        return cls(
            id=uuid4(),
            team_id=team_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
            removed_at=None,
        )

    def remove(self) -> None:
        self.removed_at = datetime.now(UTC)


@dataclass
class Notification:
    id: UUID
    workspace_id: UUID
    recipient_id: UUID
    type: str
    state: NotificationState
    actor_id: UUID | None
    subject_type: str
    subject_id: UUID
    deeplink: str
    quick_action: dict[str, Any] | None
    extra: dict[str, Any]
    idempotency_key: str
    created_at: datetime
    read_at: datetime | None
    actioned_at: datetime | None
    archived_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        recipient_id: UUID,
        type: str,
        subject_type: str,
        subject_id: UUID,
        deeplink: str,
        idempotency_key: str,
        actor_id: UUID | None = None,
        quick_action: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Notification:
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            recipient_id=recipient_id,
            type=type,
            state=NotificationState.UNREAD,
            actor_id=actor_id,
            subject_type=subject_type,
            subject_id=subject_id,
            deeplink=deeplink,
            quick_action=quick_action,
            extra=extra or {},
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
            read_at=None,
            actioned_at=None,
        )

    def mark_read(self) -> None:
        if self.state is NotificationState.UNREAD:
            self.state = NotificationState.READ
            self.read_at = datetime.now(UTC)

    def mark_actioned(self) -> None:
        self.state = NotificationState.ACTIONED
        self.actioned_at = datetime.now(UTC)
