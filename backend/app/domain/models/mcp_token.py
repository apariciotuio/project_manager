"""MCP Token domain entity — EP-18 Capability 1."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class MCPToken:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    name: str
    token_hash_argon2: str
    lookup_key_hmac: bytes
    scopes: list[str]
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    rotated_from: UUID | None = None

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        user_id: UUID,
        name: str,
        token_hash_argon2: str,
        lookup_key_hmac: bytes,
        scopes: list[str],
        expires_at: datetime,
        rotated_from: UUID | None = None,
    ) -> "MCPToken":
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if len(name) > 200:
            raise ValueError("name must be <= 200 characters")
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            name=name.strip(),
            token_hash_argon2=token_hash_argon2,
            lookup_key_hmac=lookup_key_hmac,
            scopes=list(scopes),
            created_at=_now(),
            expires_at=expires_at,
            rotated_from=rotated_from,
        )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_revoked and not self.is_expired

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = _now()
