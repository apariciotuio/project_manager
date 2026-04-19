"""EP-18 — Unit tests for list_reviews MCP tool handler.

Tests exercise the handler in isolation using fakes.
No DB, no MCP SDK required.

Scenarios:
- Happy path: returns list with expected keys per review
- Cross-workspace isolation: unknown work_item_id returns not_found error
- Empty list returned when no reviews exist
- include_resolved=false (default) excludes CLOSED/CANCELLED requests
- include_resolved=true includes all statuses
- Invalid work_item_id UUID raises ValueError
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.exceptions import WorkItemNotFoundError
from app.domain.models.review import ReviewerType, ReviewRequest, ReviewStatus
from apps.mcp_server.tools.list_reviews import handle_list_reviews

WORKSPACE_ID = uuid4()

_EXPECTED_REVIEW_KEYS = {"id", "status", "kind", "created_at"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_review_request(
    work_item_id: UUID,
    status: ReviewStatus = ReviewStatus.PENDING,
    reviewer_type: ReviewerType = ReviewerType.USER,
) -> ReviewRequest:
    reviewer_id = uuid4() if reviewer_type is ReviewerType.USER else None
    team_id = uuid4() if reviewer_type is ReviewerType.TEAM else None
    return ReviewRequest(
        id=uuid4(),
        work_item_id=work_item_id,
        version_id=uuid4(),
        reviewer_type=reviewer_type,
        reviewer_id=reviewer_id,
        team_id=team_id,
        validation_rule_id=None,
        status=status,
        requested_by=uuid4(),
        requested_at=datetime.now(UTC),
        cancelled_at=None,
    )


def _fake_service_found() -> MagicMock:
    svc = MagicMock()
    svc.get = AsyncMock(return_value=MagicMock())
    return svc


def _fake_service_not_found() -> MagicMock:
    svc = MagicMock()
    svc.get = AsyncMock(side_effect=WorkItemNotFoundError(uuid4()))
    return svc


class FakeReviewRepo:
    def __init__(self, requests: list[ReviewRequest] | None = None) -> None:
        self._requests = requests or []
        self.called_with: list[UUID] = []

    async def list_for_work_item(self, work_item_id: UUID) -> list[ReviewRequest]:
        self.called_with.append(work_item_id)
        return [r for r in self._requests if r.work_item_id == work_item_id]


# ---------------------------------------------------------------------------
# Shape tests
# ---------------------------------------------------------------------------


class TestListReviewsShape:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        req = _make_review_request(work_item_id)
        repo = FakeReviewRepo([req])

        result = await handle_list_reviews(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_review_has_required_keys(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        req = _make_review_request(work_item_id)
        repo = FakeReviewRepo([req])

        result = await handle_list_reviews(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result
        assert _EXPECTED_REVIEW_KEYS.issubset(set(result[0].keys()))

    @pytest.mark.asyncio
    async def test_status_is_string(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        req = _make_review_request(work_item_id, status=ReviewStatus.PENDING)
        repo = FakeReviewRepo([req])

        result = await handle_list_reviews(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result[0]["status"], str)
        assert result[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# Empty + isolation
# ---------------------------------------------------------------------------


class TestListReviewsEmptyAndIsolation:
    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        repo = FakeReviewRepo([])

        result = await handle_list_reviews(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_cross_workspace_returns_not_found(self) -> None:
        svc = _fake_service_not_found()
        repo = FakeReviewRepo()

        result = await handle_list_reviews(
            arguments={"work_item_id": str(uuid4())},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_not_found_does_not_query_repo(self) -> None:
        svc = _fake_service_not_found()
        repo = FakeReviewRepo()

        await handle_list_reviews(
            arguments={"work_item_id": str(uuid4())},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert repo.called_with == []

    @pytest.mark.asyncio
    async def test_include_resolved_false_excludes_closed(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        pending = _make_review_request(work_item_id, status=ReviewStatus.PENDING)
        closed = _make_review_request(work_item_id, status=ReviewStatus.CLOSED)
        cancelled = _make_review_request(work_item_id, status=ReviewStatus.CANCELLED)
        repo = FakeReviewRepo([pending, closed, cancelled])

        result = await handle_list_reviews(
            arguments={"work_item_id": str(work_item_id), "include_resolved": False},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert len(result) == 1
        assert result[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_include_resolved_true_returns_all(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        pending = _make_review_request(work_item_id, status=ReviewStatus.PENDING)
        closed = _make_review_request(work_item_id, status=ReviewStatus.CLOSED)
        repo = FakeReviewRepo([pending, closed])

        result = await handle_list_reviews(
            arguments={"work_item_id": str(work_item_id), "include_resolved": True},
            service=svc,
            review_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_invalid_work_item_id_raises(self) -> None:
        svc = _fake_service_found()
        repo = FakeReviewRepo()

        with pytest.raises(ValueError):
            await handle_list_reviews(
                arguments={"work_item_id": "not-a-uuid"},
                service=svc,
                review_repo=repo,
                workspace_id=WORKSPACE_ID,
            )
