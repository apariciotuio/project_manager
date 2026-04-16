"""WorkspaceMembership — join entity between User and Workspace.

`role` is a display label. Authorization is capability-driven (EP-10). `state` is the
source of truth for lifecycle: only `active` members can act.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

MembershipState = Literal["invited", "active", "suspended", "deleted"]
_VALID_STATES: frozenset[str] = frozenset({"invited", "active", "suspended", "deleted"})


def _now() -> datetime:
    return datetime.now(UTC)


def _require_role(value: str | None) -> str:
    if value is None or not str(value).strip():
        raise ValueError("role must not be empty")
    return str(value).strip()


def _require_state(value: str | None) -> MembershipState:
    if value not in _VALID_STATES:
        raise ValueError(f"state must be one of {sorted(_VALID_STATES)}; got {value!r}")
    return value  # type: ignore[return-value]


@dataclass
class WorkspaceMembership:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: str
    state: MembershipState
    is_default: bool
    joined_at: datetime = field(default_factory=_now)

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: str | None,
        is_default: bool,
        state: str | None = "active",
    ) -> WorkspaceMembership:
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            role=_require_role(role),
            state=_require_state(state),
            is_default=is_default,
            joined_at=_now(),
        )

    def is_active(self) -> bool:
        return self.state == "active"

    def suspend(self) -> None:
        if self.state == "deleted":
            raise ValueError("cannot suspend a deleted membership")
        self.state = "suspended"

    def activate(self) -> None:
        if self.state == "deleted":
            raise ValueError("cannot activate a deleted membership")
        self.state = "active"

    def mark_deleted(self) -> None:
        self.state = "deleted"
