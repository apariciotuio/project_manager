"""Unit tests for SuggestionService.apply_accepted_batch — EP-03.

Covers:
  - accepted suggestions get applied (sections updated, status → applied)
  - skips already-applied suggestions (idempotency)
  - skips rejected/pending suggestions
  - raises ValueError when no accepted suggestions
  - raises LookupError when batch not found
  - returns correct applied_count, skipped_count, and latest_version
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from tests.fakes.fake_dundun_client import FakeDundunClient
from tests.fakes.fake_repositories import FakeAssistantSuggestionRepository


# ---------------------------------------------------------------------------
# Domain imports (deferred to avoid import-time side effects in RED phase)
# ---------------------------------------------------------------------------


def _make_suggestion(
    batch_id: UUID,
    work_item_id: UUID,
    *,
    status: str = "pending",
    section_id: UUID | None = None,
    expires_at: datetime | None = None,
):
    from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus

    now = datetime.now(UTC)
    if expires_at is None:
        expires_at = now + timedelta(hours=1)
    return AssistantSuggestion(
        id=uuid4(),
        workspace_id=uuid4(),
        work_item_id=work_item_id,
        thread_id=None,
        section_id=section_id,
        proposed_content="Proposed new content for the section",
        current_content="Current old content",
        rationale="Some rationale from AI",
        status=SuggestionStatus(status),
        version_number_target=1,
        batch_id=batch_id,
        dundun_request_id=None,
        created_by=uuid4(),
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# Fakes for SectionService
# ---------------------------------------------------------------------------


class _FakeSectionService:
    """Records calls to update_section."""

    def __init__(self, workspace_id: UUID) -> None:
        self.calls: list[dict] = []
        self.workspace_id = workspace_id

    async def update_section(
        self,
        *,
        section_id: UUID,
        work_item_id: UUID,
        workspace_id: UUID,
        actor_id: UUID,
        new_content: str,
    ) -> object:
        self.calls.append(
            {
                "section_id": section_id,
                "work_item_id": work_item_id,
                "new_content": new_content,
            }
        )
        return object()  # fake Section — callers don't inspect it


class _FakeVersioningService:
    """Records version creation calls."""

    def __init__(self) -> None:
        from app.domain.models.work_item_version import (
            VersionActorType,
            VersionTrigger,
            WorkItemVersion,
        )

        self.versions_created: list[WorkItemVersion] = []

    async def create_version(self, **kwargs: object) -> object:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.models.work_item_version import (
            VersionActorType,
            VersionTrigger,
            WorkItemVersion,
        )

        v = WorkItemVersion(
            id=uuid4(),
            work_item_id=kwargs["work_item_id"],  # type: ignore[arg-type]
            version_number=len(self.versions_created) + 1,
            snapshot={},
            created_by=kwargs["actor_id"],  # type: ignore[arg-type]
            created_at=datetime.now(UTC),
            trigger=VersionTrigger.AI_SUGGESTION,
            actor_type=VersionActorType.AI_SUGGESTION,
        )
        self.versions_created.append(v)
        return v

    async def get_latest(self, work_item_id: UUID, workspace_id: UUID) -> object | None:
        for v in reversed(self.versions_created):
            if v.work_item_id == work_item_id:  # type: ignore[attr-defined]
                return v
        return None


def _make_service(
    suggestion_repo=None,
    section_service=None,
    versioning_service=None,
    workspace_id: UUID | None = None,
    callback_url: str = "https://app/cb",
):
    from app.application.services.suggestion_service import SuggestionService

    if suggestion_repo is None:
        suggestion_repo = FakeAssistantSuggestionRepository()
    if workspace_id is None:
        workspace_id = uuid4()
    if section_service is None:
        section_service = _FakeSectionService(workspace_id)
    if versioning_service is None:
        versioning_service = _FakeVersioningService()

    return (
        SuggestionService(
            suggestion_repo=suggestion_repo,
            dundun_client=FakeDundunClient(),
            callback_url=callback_url,
            section_service=section_service,
            versioning_service=versioning_service,
            workspace_id=workspace_id,
        ),
        suggestion_repo,
        section_service,
        versioning_service,
    )


# ---------------------------------------------------------------------------
# apply_accepted_batch
# ---------------------------------------------------------------------------


class TestApplyAcceptedBatch:
    @pytest.mark.asyncio
    async def test_applies_accepted_suggestions(self) -> None:
        workspace_id = uuid4()
        work_item_id = uuid4()
        batch_id = uuid4()
        section_id = uuid4()

        repo = FakeAssistantSuggestionRepository()
        s = _make_suggestion(batch_id, work_item_id, status="accepted", section_id=section_id)
        await repo.create_batch([s])

        svc, _, section_svc, _ = _make_service(suggestion_repo=repo, workspace_id=workspace_id)
        result = await svc.apply_accepted_batch(batch_id=batch_id, actor_id=uuid4())

        assert result["applied_count"] == 1
        assert result["skipped_count"] == 0
        assert len(section_svc.calls) == 1
        assert section_svc.calls[0]["section_id"] == section_id
        assert section_svc.calls[0]["new_content"] == s.proposed_content

    @pytest.mark.asyncio
    async def test_skips_non_accepted_suggestions(self) -> None:
        workspace_id = uuid4()
        work_item_id = uuid4()
        batch_id = uuid4()

        repo = FakeAssistantSuggestionRepository()
        pending = _make_suggestion(batch_id, work_item_id, status="pending", section_id=uuid4())
        rejected = _make_suggestion(batch_id, work_item_id, status="rejected", section_id=uuid4())
        accepted = _make_suggestion(batch_id, work_item_id, status="accepted", section_id=uuid4())
        await repo.create_batch([pending, rejected, accepted])

        svc, _, section_svc, _ = _make_service(suggestion_repo=repo, workspace_id=workspace_id)
        result = await svc.apply_accepted_batch(batch_id=batch_id, actor_id=uuid4())

        assert result["applied_count"] == 1
        assert result["skipped_count"] == 2
        assert len(section_svc.calls) == 1

    @pytest.mark.asyncio
    async def test_idempotent_skips_already_applied(self) -> None:
        workspace_id = uuid4()
        work_item_id = uuid4()
        batch_id = uuid4()

        repo = FakeAssistantSuggestionRepository()
        already_applied = _make_suggestion(
            batch_id, work_item_id, status="applied", section_id=uuid4()
        )
        await repo.create_batch([already_applied])

        svc, _, section_svc, _ = _make_service(suggestion_repo=repo, workspace_id=workspace_id)
        result = await svc.apply_accepted_batch(batch_id=batch_id, actor_id=uuid4())

        assert result["applied_count"] == 0
        assert result["skipped_count"] == 1
        assert len(section_svc.calls) == 0

    @pytest.mark.asyncio
    async def test_raises_when_no_accepted_suggestions(self) -> None:
        work_item_id = uuid4()
        batch_id = uuid4()

        repo = FakeAssistantSuggestionRepository()
        pending = _make_suggestion(batch_id, work_item_id, status="pending", section_id=uuid4())
        await repo.create_batch([pending])

        svc, _, _, _ = _make_service(suggestion_repo=repo)
        with pytest.raises(ValueError, match="no accepted"):
            await svc.apply_accepted_batch(batch_id=batch_id, actor_id=uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_batch_not_found(self) -> None:
        svc, _, _, _ = _make_service()
        with pytest.raises(LookupError):
            await svc.apply_accepted_batch(batch_id=uuid4(), actor_id=uuid4())

    @pytest.mark.asyncio
    async def test_marks_applied_suggestions_as_applied(self) -> None:
        from app.domain.models.assistant_suggestion import SuggestionStatus

        workspace_id = uuid4()
        work_item_id = uuid4()
        batch_id = uuid4()
        section_id = uuid4()

        repo = FakeAssistantSuggestionRepository()
        s = _make_suggestion(batch_id, work_item_id, status="accepted", section_id=section_id)
        await repo.create_batch([s])

        svc, repo, _, _ = _make_service(suggestion_repo=repo, workspace_id=workspace_id)
        await svc.apply_accepted_batch(batch_id=batch_id, actor_id=uuid4())

        updated = await repo.get_by_id(s.id)
        assert updated is not None
        assert updated.status == SuggestionStatus.APPLIED

    @pytest.mark.asyncio
    async def test_suggestion_without_section_id_is_skipped(self) -> None:
        """Suggestion with no section_id cannot be applied — skip it."""
        workspace_id = uuid4()
        work_item_id = uuid4()
        batch_id = uuid4()

        repo = FakeAssistantSuggestionRepository()
        # accepted but no section_id
        no_section = _make_suggestion(batch_id, work_item_id, status="accepted", section_id=None)
        with_section = _make_suggestion(
            batch_id, work_item_id, status="accepted", section_id=uuid4()
        )
        await repo.create_batch([no_section, with_section])

        svc, _, section_svc, _ = _make_service(suggestion_repo=repo, workspace_id=workspace_id)
        result = await svc.apply_accepted_batch(batch_id=batch_id, actor_id=uuid4())

        # Only the one with section_id is applied
        assert result["applied_count"] == 1
        assert len(section_svc.calls) == 1

    @pytest.mark.asyncio
    async def test_returns_latest_version_after_apply(self) -> None:
        workspace_id = uuid4()
        work_item_id = uuid4()
        batch_id = uuid4()
        section_id = uuid4()

        repo = FakeAssistantSuggestionRepository()
        s = _make_suggestion(batch_id, work_item_id, status="accepted", section_id=section_id)
        await repo.create_batch([s])

        versioning = _FakeVersioningService()
        svc, _, _, _ = _make_service(
            suggestion_repo=repo,
            versioning_service=versioning,
            workspace_id=workspace_id,
        )
        result = await svc.apply_accepted_batch(batch_id=batch_id, actor_id=uuid4())

        assert result["latest_version"] is not None
