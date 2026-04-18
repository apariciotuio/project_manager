"""EP-04 Phase 6 — NextStepService.

Orchestrates: CompletenessService → GapService → NextStepDecisionTree.
"""

from __future__ import annotations

from uuid import UUID

from app.application.services.completeness_service import CompletenessService, GapService
from app.domain.quality import next_step_rules
from app.domain.quality.next_step_rules import NextStepResult
from app.domain.repositories.work_item_repository import IWorkItemRepository


class NextStepService:
    def __init__(
        self,
        *,
        work_item_repo: IWorkItemRepository,
        completeness_service: CompletenessService,
        gap_service: GapService,
    ) -> None:
        self._work_items = work_item_repo
        self._completeness = completeness_service
        self._gaps = gap_service

    async def recommend(self, work_item_id: UUID, workspace_id: UUID) -> NextStepResult:
        work_item = await self._work_items.get(work_item_id, workspace_id)
        if work_item is None:
            raise LookupError(f"work item {work_item_id} not found")

        completeness = await self._completeness.compute(work_item_id, workspace_id)
        gaps = await self._gaps.list(work_item_id, workspace_id)

        return next_step_rules.evaluate(work_item, completeness, gaps)
