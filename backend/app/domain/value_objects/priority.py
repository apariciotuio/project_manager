"""Priority — ordered work item priority levels."""
from __future__ import annotations

from enum import StrEnum


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
