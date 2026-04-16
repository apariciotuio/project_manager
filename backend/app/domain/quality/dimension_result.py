"""EP-04 — DimensionResult value object."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    weight: float
    applicable: bool
    filled: bool
    score: float
    message: str | None = None


@dataclass(frozen=True)
class CompletenessResult:
    score: int
    level: str
    dimensions: list[DimensionResult]
    cached: bool = False
