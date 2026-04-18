"""EP-04 Phase 4 — Dimension checkers (pure functions).

Each function takes a WorkItem plus its sections and validators and returns a
DimensionResult. No I/O. No framework imports.

Weights come from DIMENSION_WEIGHTS — they are renormalised per WorkItemType
in ScoreCalculator.compute().

Breakdown scoring bands (EP-04 + EP-05 cross-EP wiring):
  0 tasks   → score 0.0  (not filled)
  1-2 tasks → score 0.4  (partial — shows intent but no real decomposition)
  3-5 tasks → score 0.8  (good decomposition)
  6+ tasks  → score 1.0  (fully filled)
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

from app.domain.models.section import Section
from app.domain.models.section_type import SectionType
from app.domain.models.validator import Validator, ValidatorStatus
from app.domain.quality.dimension_result import DimensionResult
from app.domain.value_objects.work_item_type import WorkItemType


class _WorkItemLike(Protocol):
    @property
    def owner_id(self) -> object: ...
    @property
    def owner_suspended_flag(self) -> bool: ...
    @property
    def type(self) -> WorkItemType: ...


DIMENSION_WEIGHTS: dict[str, float] = {
    "problem_clarity": 0.10,
    "objective": 0.12,
    "scope": 0.10,
    "acceptance_criteria": 0.22,
    "dependencies": 0.08,
    "risks": 0.08,
    "breakdown": 0.08,
    "ownership": 0.10,
    "validations": 0.12,
    "next_step_clarity": 0.00,
}


_TYPES_NEEDING_AC = {
    WorkItemType.REQUIREMENT,
    WorkItemType.BUSINESS_CHANGE,
    WorkItemType.ENHANCEMENT,
    WorkItemType.BUG,
    WorkItemType.INITIATIVE,
    WorkItemType.IDEA,
}
_TYPES_NEEDING_BREAKDOWN = {
    WorkItemType.INITIATIVE,
    WorkItemType.BUSINESS_CHANGE,
}
_TYPES_NEEDING_SCOPE = {
    WorkItemType.REQUIREMENT,
    WorkItemType.INITIATIVE,
    WorkItemType.BUSINESS_CHANGE,
    WorkItemType.SPIKE,
}
_TYPES_NEEDING_OBJECTIVE = {
    WorkItemType.REQUIREMENT,
    WorkItemType.ENHANCEMENT,
    WorkItemType.INITIATIVE,
    WorkItemType.BUSINESS_CHANGE,
}


def _section(sections: Iterable[Section], kind: SectionType) -> Section | None:
    for s in sections:
        if s.section_type is kind:
            return s
    return None


def _content(sections: Iterable[Section], kind: SectionType) -> str:
    s = _section(sections, kind)
    return s.content if s else ""


def _result(
    name: str,
    *,
    applicable: bool,
    filled: bool,
    message: str | None = None,
) -> DimensionResult:
    weight = DIMENSION_WEIGHTS.get(name, 0.0)
    return DimensionResult(
        dimension=name,
        weight=weight,
        applicable=applicable,
        filled=filled,
        score=1.0 if filled else 0.0,
        message=None if filled or not applicable else (message or f"{name} is missing"),
    )


def check_problem_clarity(
    work_item: _WorkItemLike,
    sections: list[Section],
    _validators: list[Validator],
) -> DimensionResult:
    applicable = work_item.type not in {WorkItemType.TASK, WorkItemType.SPIKE}
    if not applicable:
        return _result("problem_clarity", applicable=False, filled=False)
    summary = _content(sections, SectionType.SUMMARY).strip()
    context = (
        _content(sections, SectionType.CONTEXT) or _content(sections, SectionType.ACTUAL_BEHAVIOR)
    ).strip()
    filled = len(summary) + len(context) >= 100
    return _result(
        "problem_clarity",
        applicable=True,
        filled=filled,
        message="Describe the problem in at least 100 characters across summary + context",
    )


def check_objective(
    work_item: _WorkItemLike,
    sections: list[Section],
    _validators: list[Validator],
) -> DimensionResult:
    applicable = work_item.type in _TYPES_NEEDING_OBJECTIVE
    if not applicable:
        return _result("objective", applicable=False, filled=False)
    content = _content(sections, SectionType.OBJECTIVE).strip()
    filled = len(content) >= 50
    return _result(
        "objective",
        applicable=True,
        filled=filled,
        message="Define the objective in at least 50 characters",
    )


def check_scope(
    work_item: _WorkItemLike,
    sections: list[Section],
    _validators: list[Validator],
) -> DimensionResult:
    applicable = work_item.type in _TYPES_NEEDING_SCOPE
    if not applicable:
        return _result("scope", applicable=False, filled=False)
    filled = bool(_content(sections, SectionType.SCOPE).strip())
    return _result(
        "scope",
        applicable=True,
        filled=filled,
        message="Define what is in and out of scope",
    )


_AC_BULLET = re.compile(r"^\s*[-*]\s+\S", re.MULTILINE)


def check_acceptance_criteria(
    work_item: _WorkItemLike,
    sections: list[Section],
    _validators: list[Validator],
) -> DimensionResult:
    applicable = work_item.type in _TYPES_NEEDING_AC
    if not applicable:
        return _result("acceptance_criteria", applicable=False, filled=False)
    content = _content(sections, SectionType.ACCEPTANCE_CRITERIA)
    filled = len(_AC_BULLET.findall(content)) >= 2
    return _result(
        "acceptance_criteria",
        applicable=True,
        filled=filled,
        message="List at least 2 acceptance criteria as bullet points",
    )


def _section_filled_with_content_or_none(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return stripped.lower() == "none" or len(stripped) > 3


def check_dependencies(
    _work_item: _WorkItemLike,
    sections: list[Section],
    _validators: list[Validator],
) -> DimensionResult:
    content = _content(sections, SectionType.DEPENDENCIES)
    filled = _section_filled_with_content_or_none(content)
    return _result(
        "dependencies",
        applicable=True,
        filled=filled,
        message="List dependencies, or write 'none' if there are none",
    )


def check_risks(
    _work_item: _WorkItemLike,
    sections: list[Section],
    _validators: list[Validator],
) -> DimensionResult:
    content = _content(sections, SectionType.RISKS)
    filled = _section_filled_with_content_or_none(content)
    return _result(
        "risks",
        applicable=True,
        filled=filled,
        message="List risks, or write 'none' if there are none",
    )


def _breakdown_score(task_count: int) -> float:
    """Map task_count to a continuous score using the breakdown bands."""
    if task_count == 0:
        return 0.0
    if task_count <= 2:
        return 0.4
    if task_count <= 5:
        return 0.8
    return 1.0


def check_breakdown(
    work_item: _WorkItemLike,
    sections: list[Section],
    _validators: list[Validator],
    *,
    task_count: int = 0,
) -> DimensionResult:
    applicable = work_item.type in _TYPES_NEEDING_BREAKDOWN
    if not applicable:
        return _result("breakdown", applicable=False, filled=False)
    score = _breakdown_score(task_count)
    filled = score >= 0.8
    weight = DIMENSION_WEIGHTS.get("breakdown", 0.0)
    return DimensionResult(
        dimension="breakdown",
        weight=weight,
        applicable=True,
        filled=filled,
        score=score,
        message=None if filled else "Provide a breakdown of child items (at least 3 tasks)",
    )


def check_ownership(
    work_item: _WorkItemLike,
    _sections: list[Section],
    _validators: list[Validator],
) -> DimensionResult:
    filled = work_item.owner_id is not None and not work_item.owner_suspended_flag
    return _result(
        "ownership",
        applicable=True,
        filled=filled,
        message="Assign an active owner",
    )


def check_validations(
    _work_item: _WorkItemLike,
    _sections: list[Section],
    validators: list[Validator],
) -> DimensionResult:
    filled = any(
        v.status in {ValidatorStatus.APPROVED, ValidatorStatus.PENDING} for v in validators
    )
    return _result(
        "validations",
        applicable=True,
        filled=filled,
        message="Assign at least one validator",
    )


ALL_CHECKERS = (
    check_problem_clarity,
    check_objective,
    check_scope,
    check_acceptance_criteria,
    check_dependencies,
    check_risks,
    check_ownership,
    check_validations,
)


def check_all(
    work_item: _WorkItemLike,
    sections: list[Section],
    validators: list[Validator],
    *,
    task_count: int = 0,
) -> list[DimensionResult]:
    results = [chk(work_item, sections, validators) for chk in ALL_CHECKERS]
    results.insert(6, check_breakdown(work_item, sections, validators, task_count=task_count))
    return results
