"""Session domain entity — server-stored refresh-token session."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Session:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime = field(default_factory=_now)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        if not raw_token:
            raise ValueError("token must not be empty")
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        raw_token: str,
        ttl_seconds: int,
        ip_address: str | None,
        user_agent: str | None,
    ) -> Session:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        created = _now()
        return cls(
            id=uuid4(),
            user_id=user_id,
            token_hash=cls.hash_token(raw_token),
            expires_at=created + timedelta(seconds=ttl_seconds),
            revoked_at=None,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=created,
        )

    def is_expired(self) -> bool:
        return _now() >= self.expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_active(self) -> bool:
        return not self.is_expired() and not self.is_revoked()

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = _now()

    def raw_token_not_stored(self) -> bool:
        """Invariant marker: Session never retains the raw token, only the SHA-256 hash."""
        return True
