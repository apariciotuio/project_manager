"""Unit tests for ClarificationService — EP-03 Phase 5.

Uses fake repos, fake cache, fake Dundun. No DB, no Redis, no HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tests.fakes.fake_dundun_client import FakeDundunClient
from tests.fakes.fake_repositories import FakeCache, FakeWorkItemRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_work_item(workspace_id, *, type_="task", description="Some description"):
    from app.domain.models.work_item import WorkItem
    from app.domain.value_objects.priority import Priority
    from app.domain.value_objects.work_item_state import WorkItemState
    from app.domain.value_objects.work_item_type import WorkItemType

    return WorkItem(
        id=uuid4(),
        title="Test Item",
        type=WorkItemType(type_),
        state=WorkItemState.DRAFT,
        owner_id=uuid4(),
        creator_id=uuid4(),
        project_id=uuid4(),
        description=description,
        original_input=None,
        priority=Priority.MEDIUM,
        due_date=None,
        tags=[],
        completeness_score=50,
        parent_work_item_id=None,
        materialized_path="",
        attachment_count=0,
        has_override=False,
        override_justification=None,
        owner_suspended_flag=False,
        draft_data=None,
        template_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
        exported_at=None,
        export_reference=None,
    )


def _make_service(
    work_item_repo=None, cache=None, dundun=None, callback_url="https://app/callback"
):
    from app.application.services.clarification_service import ClarificationService
    from app.domain.gap_detection.gap_detector import GapDetector

    if work_item_repo is None:
        work_item_repo = FakeWorkItemRepository()
    if cache is None:
        cache = FakeCache()
    if dundun is None:
        dundun = FakeDundunClient()
    return ClarificationService(
        gap_detector=GapDetector(),
        work_item_repo=work_item_repo,
        dundun_client=dundun,
        cache=cache,
        callback_url=callback_url,
    )


# ---------------------------------------------------------------------------
# get_gap_report
# ---------------------------------------------------------------------------


class TestGetGapReport:
    async def test_cache_miss_runs_detection_and_caches(self) -> None:
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id)
        await repo.save(item, ws_id)
        cache = FakeCache()

        service = _make_service(work_item_repo=repo, cache=cache)
        report = await service.get_gap_report(item.id, ws_id)

        assert report.work_item_id == item.id
        assert cache.set_call_count == 1

    async def test_cache_hit_skips_detection(self) -> None:
        """If cache returns a value, the service returns it without re-running rules."""
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id)
        await repo.save(item, ws_id)
        cache = FakeCache()

        service = _make_service(work_item_repo=repo, cache=cache)

        # Warm the cache
        await service.get_gap_report(item.id, ws_id)
        initial_set = cache.set_call_count

        # Second call hits cache
        report2 = await service.get_gap_report(item.id, ws_id)

        assert report2.work_item_id == item.id
        assert cache.set_call_count == initial_set  # no additional set

    async def test_not_found_raises(self) -> None:
        from app.domain.exceptions import WorkItemNotFoundError

        service = _make_service()
        with pytest.raises(WorkItemNotFoundError):
            await service.get_gap_report(uuid4(), uuid4())

    async def test_report_score_is_float_in_zero_to_one(self) -> None:
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id)
        await repo.save(item, ws_id)

        service = _make_service(work_item_repo=repo)
        report = await service.get_gap_report(item.id, ws_id)

        assert 0.0 <= report.score <= 1.0

    async def test_item_with_no_description_has_blocking_finding(self) -> None:
        from app.domain.models.gap_finding import GapSeverity

        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id, description=None)
        await repo.save(item, ws_id)

        service = _make_service(work_item_repo=repo)
        report = await service.get_gap_report(item.id, ws_id)

        blocking = [f for f in report.findings if f.severity == GapSeverity.BLOCKING]
        assert len(blocking) >= 1

    async def test_updated_at_in_cache_key_means_stale_key_is_ignored(self) -> None:
        """Two calls with different updated_at produce different cache keys."""
        import dataclasses
        from datetime import timedelta

        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id)
        await repo.save(item, ws_id)
        cache = FakeCache()

        service = _make_service(work_item_repo=repo, cache=cache)
        await service.get_gap_report(item.id, ws_id)

        # Simulate work item update: change updated_at
        updated_item = dataclasses.replace(item, updated_at=item.updated_at + timedelta(seconds=1))
        await repo.save(updated_item, ws_id)

        await service.get_gap_report(item.id, ws_id)

        # Two distinct sets — old key not reused
        assert cache.set_call_count == 2


# ---------------------------------------------------------------------------
# trigger_ai_review
# ---------------------------------------------------------------------------


class TestTriggerAiReview:
    async def test_returns_request_id_string(self) -> None:
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id)
        await repo.save(item, ws_id)
        dundun = FakeDundunClient()

        service = _make_service(work_item_repo=repo, dundun=dundun)
        request_id = await service.trigger_ai_review(item.id, ws_id, uuid4())

        assert isinstance(request_id, str)
        assert len(request_id) > 0

    async def test_invokes_wm_gap_agent(self) -> None:
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id)
        await repo.save(item, ws_id)
        dundun = FakeDundunClient()

        service = _make_service(work_item_repo=repo, dundun=dundun)
        await service.trigger_ai_review(item.id, ws_id, uuid4())

        assert len(dundun.invocations) == 1
        agent, *_ = dundun.invocations[0]
        assert agent == "wm_gap_agent"

    async def test_callback_url_passed_to_dundun(self) -> None:
        url = "https://myapp.io/callback"
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id)
        await repo.save(item, ws_id)
        dundun = FakeDundunClient()

        service = _make_service(work_item_repo=repo, dundun=dundun, callback_url=url)
        await service.trigger_ai_review(item.id, ws_id, uuid4())

        _, _, _, _, callback, _ = dundun.invocations[0]
        assert callback == url

    async def test_not_found_raises(self) -> None:
        from app.domain.exceptions import WorkItemNotFoundError

        service = _make_service()
        with pytest.raises(WorkItemNotFoundError):
            await service.trigger_ai_review(uuid4(), uuid4(), uuid4())


# ---------------------------------------------------------------------------
# get_next_questions
# ---------------------------------------------------------------------------


class TestGetNextQuestions:
    async def test_returns_at_most_three_questions(self) -> None:
        """Even with many blocking findings, only 3 questions returned."""
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        # Item with no description, no title meaningful content → multiple blocking
        item = _make_work_item(ws_id, description=None)
        await repo.save(item, ws_id)

        service = _make_service(work_item_repo=repo)
        questions = await service.get_next_questions(item.id, ws_id)

        assert len(questions) <= 3

    async def test_questions_are_strings(self) -> None:
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id, description=None)
        await repo.save(item, ws_id)

        service = _make_service(work_item_repo=repo)
        questions = await service.get_next_questions(item.id, ws_id)

        assert all(isinstance(q, str) and len(q) > 0 for q in questions)

    async def test_item_with_no_blocking_returns_empty(self) -> None:
        """A fully-populated item might have no blocking findings."""
        from app.domain.models.gap_finding import GapSeverity

        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        # Well-formed item with description
        item = _make_work_item(ws_id, description="A clear description of the work item.")
        await repo.save(item, ws_id)

        service = _make_service(work_item_repo=repo)
        report = await service.get_gap_report(item.id, ws_id)
        blocking = [f for f in report.findings if f.severity == GapSeverity.BLOCKING]

        questions = await service.get_next_questions(item.id, ws_id)

        # If no blocking findings, no questions
        if not blocking:
            assert questions == []

    async def test_uses_human_readable_mapping_not_raw_dimension(self) -> None:
        """Known dimensions must map to human-readable questions, not raw key names."""
        ws_id = uuid4()
        repo = FakeWorkItemRepository()
        item = _make_work_item(ws_id, description=None)
        await repo.save(item, ws_id)

        service = _make_service(work_item_repo=repo)
        questions = await service.get_next_questions(item.id, ws_id)

        # None of the questions should be a raw dimension key like "description_missing"
        for q in questions:
            # Questions should end with "?" and not be snake_case identifiers
            assert "?" in q or len(q) > 20, f"Question looks like a raw dimension: {q!r}"
