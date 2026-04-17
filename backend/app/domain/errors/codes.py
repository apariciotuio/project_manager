"""Central error code registry (EP-21 F-4-be).

Maps stable SNAKE_CASE error codes to their canonical HTTP status.
All domain errors inherit from DomainError and reference a code from this registry.

The TS mirror lives at frontend/lib/errors/codes.ts — keep in sync manually.
When the registry exceeds ~50 codes, consider codegen.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Registry — code → http_status
# ---------------------------------------------------------------------------

ERROR_CODES: dict[str, int] = {
    "VALIDATION_ERROR": 400,
    "UNAUTHORIZED": 401,
    "INVALID_CREDENTIALS": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "TEAM_MEMBER_ALREADY_EXISTS": 409,
    "TAG_NAME_TAKEN": 409,
    "WORK_ITEM_INVALID_TRANSITION": 422,
    "INTERNAL_ERROR": 500,
}


# ---------------------------------------------------------------------------
# Base domain error
# ---------------------------------------------------------------------------


class DomainError(Exception):
    """Base class for all structured domain errors.

    Carry a stable ``code`` (key in ERROR_CODES), a human-readable ``message``,
    and optional ``field`` / ``details`` for field-level UI mapping.
    """

    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = details or {}

    @property
    def http_status(self) -> int:
        return ERROR_CODES.get(self.code, 500)


# ---------------------------------------------------------------------------
# Concrete domain errors
# ---------------------------------------------------------------------------


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"


class InvalidCredentialsError(DomainError):
    code = "INVALID_CREDENTIALS"


class ForbiddenError(DomainError):
    code = "FORBIDDEN"


class NotFoundError(DomainError):
    code = "NOT_FOUND"


class TeamMemberAlreadyExistsError(DomainError):
    code = "TEAM_MEMBER_ALREADY_EXISTS"

    def __init__(self, user_id: object, team_id: object) -> None:
        super().__init__(
            f"user {user_id} is already a member of team {team_id}",
            field="user_id",
        )


class TagNameTakenError(DomainError):
    code = "TAG_NAME_TAKEN"

    def __init__(self, name: str) -> None:
        super().__init__(
            f"tag '{name}' already exists in this workspace",
            field="name",
        )


class WorkItemInvalidTransitionError(DomainError):
    code = "WORK_ITEM_INVALID_TRANSITION"

    def __init__(self, from_state: str, to_state: str) -> None:
        super().__init__(
            f"invalid transition: {from_state} -> {to_state}",
            details={"from": from_state, "to": to_state},
        )
