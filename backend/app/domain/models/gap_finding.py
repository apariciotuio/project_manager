"""Gap detection domain models — pure, no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID


class GapSeverity(StrEnum):
    BLOCKING = "blocking"
    INFO = "info"
    WARNING = "warning"


@dataclass(frozen=True)
class GapFinding:
    """Transient value object produced by rule engines and LLM analysis.

    Not persisted directly — the repository accepts and returns ``StoredGapFinding``
    which carries the DB identity fields.
    """

    dimension: str
    severity: GapSeverity
    message: str
    source: Literal["rule", "dundun"]

    def __post_init__(self) -> None:
        if self.source not in ("rule", "dundun"):
            raise ValueError(f"source must be 'rule' or 'dundun', got {self.source!r}")


@dataclass(frozen=True)
class StoredGapFinding:
    """Persisted version of GapFinding — carries DB identity and timestamps."""

    id: UUID
    workspace_id: UUID
    work_item_id: UUID
    dimension: str
    severity: GapSeverity
    message: str
    source: Literal["rule", "dundun"]
    dundun_request_id: str | None
    created_at: datetime
    invalidated_at: datetime | None

    @property
    def is_active(self) -> bool:
        return self.invalidated_at is None

    def to_finding(self) -> GapFinding:
        return GapFinding(
            dimension=self.dimension,
            severity=self.severity,
            message=self.message,
            source=self.source,
        )


@dataclass
class GapReport:
    work_item_id: UUID
    findings: list[GapFinding]
    score: float
