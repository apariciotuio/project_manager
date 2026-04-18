"""EP-17 — LockUnlockRequest repository interface."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.lock_unlock_request import LockUnlockRequest


class ILockUnlockRequestRepository(Protocol):
    async def save(self, request: LockUnlockRequest) -> LockUnlockRequest: ...

    async def get(self, request_id: UUID) -> LockUnlockRequest | None: ...
