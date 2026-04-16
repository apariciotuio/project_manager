"""EP-04 — WorkItemVersion (append-only).

EP-07's VersioningService is the sole writer to work_item_versions. Other
services call VersioningService.create_version(...) instead of inserting here
directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class WorkItemVersion:
    id: UUID
    work_item_id: UUID
    version_number: int
    snapshot: dict[str, Any]
    created_by: UUID
    created_at: datetime
