"""DerivedState — computed operational state, never persisted directly."""
from __future__ import annotations

from enum import StrEnum


class DerivedState(StrEnum):
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    READY = "ready"
