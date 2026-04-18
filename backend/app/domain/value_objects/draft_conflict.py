"""DraftConflict value object — returned by IWorkItemDraftRepository.upsert on version mismatch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DraftConflict:
    server_version: int
    server_data: dict  # type: ignore[type-arg]
