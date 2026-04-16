"""Gap detection domain models — pure, no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID


class GapSeverity(StrEnum):
    BLOCKING = "blocking"
    INFO = "info"
    WARNING = "warning"


@dataclass(frozen=True)
class GapFinding:
    dimension: str
    severity: GapSeverity
    message: str
    source: Literal["rule", "dundun"]

    def __post_init__(self) -> None:
        if self.source not in ("rule", "dundun"):
            raise ValueError(f"source must be 'rule' or 'dundun', got {self.source!r}")


@dataclass
class GapReport:
    work_item_id: UUID
    findings: list[GapFinding]
    score: float
