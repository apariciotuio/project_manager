"""EP-17 — SectionLock repository interface."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.section_lock import SectionLock


class ISectionLockRepository(Protocol):
    async def acquire(self, lock: SectionLock) -> SectionLock: ...

    async def get(self, section_id: UUID) -> SectionLock | None: ...

    async def save(self, lock: SectionLock) -> SectionLock: ...

    async def delete(self, section_id: UUID) -> None: ...

    async def get_locks_for_work_item(self, work_item_id: UUID) -> list[SectionLock]: ...

    async def cleanup_expired(self) -> int: ...
