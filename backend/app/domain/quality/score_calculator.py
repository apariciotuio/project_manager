"""EP-04 Phase 5 — ScoreCalculator.

Takes the 9 DimensionResults and turns them into a 0..100 completeness score
plus a level band. Per backend_review.md ALG-4 guards against zero-division
when all dimensions are marked inapplicable.
"""

from __future__ import annotations

from app.domain.quality.dimension_result import CompletenessResult, DimensionResult


def _band(score: int) -> str:
    if score >= 90:
        return "ready"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def compute(dimensions: list[DimensionResult]) -> CompletenessResult:
    applicable = [d for d in dimensions if d.applicable]
    if not applicable:
        return CompletenessResult(score=0, level="low", dimensions=dimensions)

    total_weight = sum(d.weight for d in applicable)
    if total_weight == 0:
        return CompletenessResult(score=0, level="low", dimensions=dimensions)

    renormalised = [
        DimensionResult(
            dimension=d.dimension,
            weight=d.weight / total_weight,
            applicable=d.applicable,
            filled=d.filled,
            score=d.score,
            message=d.message,
        )
        for d in applicable
    ]
    raw_score = sum(d.score * d.weight for d in renormalised)
    score = int(round(raw_score * 100))
    return CompletenessResult(
        score=score,
        level=_band(score),
        dimensions=[
            *renormalised,
            *[d for d in dimensions if not d.applicable],
        ],
    )
