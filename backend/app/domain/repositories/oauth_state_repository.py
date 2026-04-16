"""Abstract interface for short-lived OAuth state storage.

Postgres-backed per EP-00 design (M0 Redis descope). Single-use consumption:
`consume()` atomically DELETEs the row and returns a `ConsumedOAuthState`, or None
when missing/expired. `cleanup_expired()` is a Celery-driven periodic sweep.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


class OAuthStateCollisionError(Exception):
    """PK collision on `oauth_states.state` — 128-bit state should never collide."""


@dataclass(frozen=True)
class ConsumedOAuthState:
    verifier: str
    return_to: str | None
    last_chosen_workspace_id: UUID | None


class IOAuthStateRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        state: str,
        verifier: str,
        ttl_seconds: int,
        return_to: str | None = None,
        last_chosen_workspace_id: UUID | None = None,
    ) -> None: ...

    @abstractmethod
    async def consume(self, state: str) -> ConsumedOAuthState | None:
        """DELETE ... RETURNING verifier, return_to, last_chosen_workspace_id
        WHERE state=:state AND expires_at > now()."""
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int: ...
