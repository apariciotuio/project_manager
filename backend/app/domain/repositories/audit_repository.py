"""Abstract interface for audit event persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models.audit_event import AuditEvent


class IAuditRepository(ABC):
    @abstractmethod
    async def record(self, event: AuditEvent) -> None:
        """Persist the event. May raise on DB failure — callers wrap with fire-and-forget."""
        ...
