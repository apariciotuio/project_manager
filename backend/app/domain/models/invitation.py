"""Invitation domain entity — EP-10 admin members."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

InvitationState = Literal["invited", "accepted", "expired", "revoked"]

_INVITE_TTL_DAYS = 7


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Invitation:
    id: UUID
    workspace_id: UUID
    email: str
    token_hash: str
    state: InvitationState
    context_labels: list[str]
    team_ids: list[UUID]
    initial_capabilities: list[str]
    created_by: UUID
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime = field(default_factory=_now)

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        email: str,
        token_hash: str,
        context_labels: list[str],
        team_ids: list[UUID],
        initial_capabilities: list[str],
        created_by: UUID,
        ttl_days: int = _INVITE_TTL_DAYS,
    ) -> Invitation:
        now = _now()
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            email=email.lower().strip(),
            token_hash=token_hash,
            state="invited",
            context_labels=list(context_labels),
            team_ids=list(team_ids),
            initial_capabilities=list(initial_capabilities),
            created_by=created_by,
            expires_at=now + timedelta(days=ttl_days),
            accepted_at=None,
            created_at=now,
        )

    def is_expired(self) -> bool:
        return self.expires_at < _now()

    def is_resendable(self) -> bool:
        return self.state == "invited"

    def accept(self) -> None:
        if self.state != "invited":
            raise ValueError(f"cannot accept invitation in state {self.state!r}")
        if self.is_expired():
            raise ValueError("invitation has expired")
        self.state = "accepted"
        self.accepted_at = _now()

    def revoke(self) -> None:
        if self.state in ("accepted", "revoked"):
            raise ValueError(f"cannot revoke invitation in state {self.state!r}")
        self.state = "revoked"

    def refresh_token(self, new_token_hash: str, ttl_days: int = _INVITE_TTL_DAYS) -> None:
        """Replace token and extend expiry — used for resend."""
        if not self.is_resendable():
            raise ValueError(f"cannot refresh token for invitation in state {self.state!r}")
        self.token_hash = new_token_hash
        self.expires_at = _now() + timedelta(days=ttl_days)
