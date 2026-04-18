"""ClarificationService — gap detection, AI review dispatch, question generation — EP-03."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from app.domain.gap_detection.gap_detector import GapDetector
from app.domain.models.gap_finding import GapReport, GapSeverity
from app.domain.ports.cache import ICache
from app.domain.ports.dundun import DundunClient
from app.domain.repositories.work_item_repository import IWorkItemRepository

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes

# Human-readable question mapping keyed by gap dimension.
# Fallback: use finding.message directly.
_DIMENSION_QUESTIONS: dict[str, str] = {
    "title_missing": "What should this work item be called?",
    "description_missing": "What is this work item about?",
    "description_too_short": "Can you provide more detail in the description?",
    "acceptance_criteria_missing": "What are the acceptance criteria for this work item?",
    "acceptance_criteria_too_vague": "Can you make the acceptance criteria more specific?",
    "parent": "Which parent work item does this belong to?",
    "no_children": "Has this initiative been broken down into concrete work items?",
    "priority_missing": "What is the priority of this work item?",
    "due_date_missing": "When does this work item need to be completed?",
    "owner_missing": "Who is responsible for this work item?",
}


def _cache_key(work_item_id: UUID, updated_at: datetime) -> str:
    return f"gap:{work_item_id}:{updated_at.isoformat()}"


def _serialize_report(report: GapReport) -> str:
    return json.dumps(
        {
            "work_item_id": str(report.work_item_id),
            "score": report.score,
            "findings": [
                {
                    "dimension": f.dimension,
                    "severity": f.severity.value,
                    "message": f.message,
                    "source": f.source,
                }
                for f in report.findings
            ],
        }
    )


def _deserialize_report(raw: str) -> GapReport:
    from app.domain.models.gap_finding import GapFinding

    data = json.loads(raw)
    findings = [
        GapFinding(
            dimension=f["dimension"],
            severity=GapSeverity(f["severity"]),
            message=f["message"],
            source=f["source"],
        )
        for f in data["findings"]
    ]
    return GapReport(
        work_item_id=UUID(data["work_item_id"]),
        findings=findings,
        score=data["score"],
    )


class ClarificationService:
    def __init__(
        self,
        *,
        gap_detector: GapDetector,
        work_item_repo: IWorkItemRepository,
        dundun_client: DundunClient,
        cache: ICache,
        callback_url: str,
    ) -> None:
        self._gap_detector = gap_detector
        self._work_item_repo = work_item_repo
        self._dundun_client = dundun_client
        self._cache = cache
        self._callback_url = callback_url

    async def get_gap_report(self, work_item_id: UUID, workspace_id: UUID) -> GapReport:
        """Return gap report for a work item.

        Cache key embeds updated_at — invalidation is automatic on item update.
        Cache miss: runs rule-based detection synchronously, stores result, returns.
        """
        from app.domain.exceptions import WorkItemNotFoundError

        work_item = await self._work_item_repo.get(work_item_id, workspace_id)
        if work_item is None:
            raise WorkItemNotFoundError(work_item_id)

        key = _cache_key(work_item_id, work_item.updated_at)
        cached = await self._cache.get(key)
        if cached is not None:
            return _deserialize_report(cached)

        report = self._gap_detector.detect(work_item, [])
        await self._cache.set(key, _serialize_report(report), _CACHE_TTL)
        logger.info("gap_report_generated work_item=%s score=%.2f", work_item_id, report.score)
        return report

    async def trigger_ai_review(self, work_item_id: UUID, workspace_id: UUID, user_id: UUID) -> str:
        """Invoke Dundun wm_gap_agent asynchronously. Returns request_id immediately."""
        from app.domain.exceptions import WorkItemNotFoundError

        work_item = await self._work_item_repo.get(work_item_id, workspace_id)
        if work_item is None:
            raise WorkItemNotFoundError(work_item_id)

        work_item_dict = {
            "id": str(work_item.id),
            "title": work_item.title,
            "type": work_item.type.value,
            "description": work_item.description,
        }

        result = await self._dundun_client.invoke_agent(
            agent="wm_gap_agent",
            user_id=user_id,
            conversation_id=None,
            work_item_id=work_item_id,
            callback_url=self._callback_url,
            payload={"work_item": work_item_dict},
        )
        request_id: str = result["request_id"]
        logger.info("ai_review_triggered work_item=%s request_id=%s", work_item_id, request_id)
        return request_id

    async def get_next_questions(self, work_item_id: UUID, workspace_id: UUID) -> list[str]:
        """Return up to 3 human-readable questions from BLOCKING findings."""
        report = await self.get_gap_report(work_item_id, workspace_id)
        blocking = [f for f in report.findings if f.severity == GapSeverity.BLOCKING]
        questions: list[str] = []
        for finding in blocking[:3]:
            q = _DIMENSION_QUESTIONS.get(finding.dimension, finding.message)
            questions.append(q)
        return questions
