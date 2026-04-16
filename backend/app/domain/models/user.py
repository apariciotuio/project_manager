"""User domain entity — pure, no infrastructure or ORM dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

UserStatus = Literal["active", "suspended", "deleted"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(UTC)


def _require_non_blank(value: str | None, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{field_name} must not be empty")
    return str(value).strip()


def _validate_email(value: str | None) -> str:
    stripped = _require_non_blank(value, "email")
    normalized = stripped.lower()
    if not _EMAIL_RE.match(normalized):
        raise ValueError(f"email is not a valid address: {value!r}")
    return normalized


@dataclass
class User:
    id: UUID
    google_sub: str
    email: str
    full_name: str
    avatar_url: str | None
    status: UserStatus = "active"
    is_superadmin: bool = False
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @classmethod
    def from_google_claims(
        cls,
        *,
        sub: str | None,
        email: str | None,
        name: str | None,
        picture: str | None,
    ) -> User:
        sub_clean = _require_non_blank(sub, "sub")
        name_clean = _require_non_blank(name, "name")
        email_clean = _validate_email(email)
        now = _now()
        return cls(
            id=uuid4(),
            google_sub=sub_clean,
            email=email_clean,
            full_name=name_clean,
            avatar_url=picture,
            status="active",
            is_superadmin=False,
            created_at=now,
            updated_at=now,
        )

    def update_from_google(self, *, name: str | None, picture: str | None) -> None:
        self.full_name = _require_non_blank(name, "name")
        self.avatar_url = picture
        self.updated_at = _now()

    def update_email(self, new_email: str | None) -> None:
        """Re-validates and normalizes before assignment — never bypass _validate_email."""
        self.email = _validate_email(new_email)
        self.updated_at = _now()
