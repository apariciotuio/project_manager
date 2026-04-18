"""EP-04 Phase 5 — CompletenessService + GapService.

Thin orchestration on top of the dimension checkers + ScoreCalculator. Cache
plumbing is intentionally left as a direct pass-through to ICache so tests can
swap in a FakeCache.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from uuid import UUID

from app.domain.models.section import Section
from app.domain.models.validator import Validator
from app.domain.ports.cache import ICache
from app.domain.quality import dimension_checkers
from app.domain.quality import score_calculator as score_calc
from app.domain.quality.dimension_result import CompletenessResult, DimensionResult
from app.domain.repositories.section_repository import ISectionRepository
from app.domain.repositories.task_node_repository import ITaskNodeRepository
from app.domain.repositories.validator_repository import IValidatorRepository
from app.domain.repositories.work_item_repository import IWorkItemRepository

_CACHE_TTL = 60


def _cache_key(work_item_id: UUID) -> str:
    return f"completeness:{work_item_id}"


def _serialise(result: CompletenessResult) -> str:
    return json.dumps(
        {
            "score": result.score,
            "level": result.level,
            "dimensions": [asdict(d) for d in result.dimensions],
        }
    )


def _deserialise(payload: str) -> CompletenessResult:
    data: dict[str, Any] = json.loads(payload)
    dims = [DimensionResult(**d) for d in data["dimensions"]]
    return CompletenessResult(
        score=int(data["score"]),
        level=str(data["level"]),
        dimensions=dims,
        cached=True,
    )


class CompletenessService:
    def __init__(
        self,
        *,
        work_item_repo: IWorkItemRepository,
        section_repo: ISectionRepository,
        validator_repo: IValidatorRepository,
        cache: ICache,
        task_node_repo: ITaskNodeRepository | None = None,
    ) -> None:
        self._work_items = work_item_repo
        self._sections = section_repo
        self._validators = validator_repo
        self._cache = cache
        self._task_nodes = task_node_repo

    async def compute(self, work_item_id: UUID, workspace_id: UUID) -> CompletenessResult:
        cached = await self._cache.get(_cache_key(work_item_id))
        if cached:
            return _deserialise(cached)

        work_item = await self._work_items.get(work_item_id, workspace_id)
        if work_item is None:
            raise LookupError(f"work item {work_item_id} not found")
        sections = await self._sections.get_by_work_item(work_item_id)
        validators = await self._validators.get_by_work_item(work_item_id)
        task_count = (
            await self._task_nodes.count_by_work_item(work_item_id)
            if self._task_nodes is not None
            else 0
        )
        dims = dimension_checkers.check_all(work_item, sections, validators, task_count=task_count)
        result = score_calc.compute(dims)

        await self._cache.set(_cache_key(work_item_id), _serialise(result), ttl_seconds=_CACHE_TTL)
        return result

    async def invalidate(self, work_item_id: UUID) -> None:
        await self._cache.delete(_cache_key(work_item_id))


class GapService:
    def __init__(self, completeness: CompletenessService) -> None:
        self._completeness = completeness

    async def list(self, work_item_id: UUID, workspace_id: UUID) -> list[dict[str, Any]]:
        result = await self._completeness.compute(work_item_id, workspace_id)
        return [
            {
                "dimension": d.dimension,
                "message": d.message,
                "severity": "blocking" if d.weight >= 0.12 else "warning",
            }
            for d in result.dimensions
            if d.applicable and not d.filled and d.message
        ]


def _section_sort_key(section: Section) -> tuple[int, str]:
    return (section.display_order, section.section_type.value)


def sort_sections(sections: list[Section]) -> list[Section]:
    return sorted(sections, key=_section_sort_key)


def filter_validators(validators: list[Validator]) -> list[Validator]:
    return validators
