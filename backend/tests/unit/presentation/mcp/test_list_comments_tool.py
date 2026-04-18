"""EP-18 — Unit tests for list_comments MCP tool handler.

Tests exercise the handler in isolation using fakes.
No DB, no MCP SDK required.

Scenarios:
- Happy path: returns list with expected keys per comment
- Cross-workspace isolation: unknown work_item_id returns not_found error
- Empty list returned when no comments exist
- section_id filter: only comments with matching anchor_section_id returned
- Unknown work_item (not_found) does not query repo
- Invalid work_item_id UUID raises ValueError
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.exceptions import WorkItemNotFoundError
from app.domain.models.comment import Comment, CommentActorType
from apps.mcp_server.tools.list_comments import handle_list_comments

WORKSPACE_ID = uuid4()

_EXPECTED_COMMENT_KEYS = {"id", "author", "body", "created_at", "resolved"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_comment(
    work_item_id: UUID,
    body: str = "Some comment",
    actor_id: UUID | None = None,
    anchor_section_id: UUID | None = None,
    deleted_at: datetime | None = None,
) -> Comment:
    uid = actor_id or uuid4()
    return Comment(
        id=uuid4(),
        work_item_id=work_item_id,
        parent_comment_id=None,
        body=body,
        actor_type=CommentActorType.HUMAN,
        actor_id=uid,
        anchor_section_id=anchor_section_id,
        anchor_start_offset=None,
        anchor_end_offset=None,
        anchor_snapshot_text=None,
        anchor_status="active",
        is_edited=False,
        edited_at=None,
        deleted_at=deleted_at,
        created_at=datetime.now(UTC),
    )


def _fake_service_found() -> MagicMock:
    svc = MagicMock()
    svc.get = AsyncMock(return_value=MagicMock())
    return svc


def _fake_service_not_found() -> MagicMock:
    svc = MagicMock()
    svc.get = AsyncMock(side_effect=WorkItemNotFoundError(uuid4()))
    return svc


class FakeCommentRepo:
    def __init__(self, comments: list[Comment] | None = None) -> None:
        self._comments = comments or []
        self.called_with: list[UUID] = []

    async def list_for_work_item(self, work_item_id: UUID) -> list[Comment]:
        self.called_with.append(work_item_id)
        return [c for c in self._comments if c.work_item_id == work_item_id]


# ---------------------------------------------------------------------------
# Shape tests
# ---------------------------------------------------------------------------


class TestListCommentsShape:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        comment = _make_comment(work_item_id)
        repo = FakeCommentRepo([comment])

        result = await handle_list_comments(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_comment_has_required_keys(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        comment = _make_comment(work_item_id)
        repo = FakeCommentRepo([comment])

        result = await handle_list_comments(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result
        assert _EXPECTED_COMMENT_KEYS.issubset(set(result[0].keys()))

    @pytest.mark.asyncio
    async def test_resolved_false_for_active_comment(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        comment = _make_comment(work_item_id, deleted_at=None)
        repo = FakeCommentRepo([comment])

        result = await handle_list_comments(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["resolved"] is False

    @pytest.mark.asyncio
    async def test_resolved_true_for_deleted_comment(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        comment = _make_comment(work_item_id, deleted_at=datetime.now(UTC))
        repo = FakeCommentRepo([comment])

        result = await handle_list_comments(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result[0]["resolved"] is True


# ---------------------------------------------------------------------------
# Empty + isolation
# ---------------------------------------------------------------------------


class TestListCommentsEmptyAndIsolation:
    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self) -> None:
        work_item_id = uuid4()
        svc = _fake_service_found()
        repo = FakeCommentRepo([])

        result = await handle_list_comments(
            arguments={"work_item_id": str(work_item_id)},
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_cross_workspace_returns_not_found(self) -> None:
        svc = _fake_service_not_found()
        repo = FakeCommentRepo()

        result = await handle_list_comments(
            arguments={"work_item_id": str(uuid4())},
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_not_found_does_not_query_repo(self) -> None:
        svc = _fake_service_not_found()
        repo = FakeCommentRepo()

        await handle_list_comments(
            arguments={"work_item_id": str(uuid4())},
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert repo.called_with == []

    @pytest.mark.asyncio
    async def test_section_id_filter_returns_only_matching(self) -> None:
        work_item_id = uuid4()
        section_a = uuid4()
        section_b = uuid4()
        svc = _fake_service_found()
        c1 = _make_comment(work_item_id, anchor_section_id=section_a)
        c2 = _make_comment(work_item_id, anchor_section_id=section_b)
        repo = FakeCommentRepo([c1, c2])

        result = await handle_list_comments(
            arguments={
                "work_item_id": str(work_item_id),
                "section_id": str(section_a),
            },
            service=svc,
            comment_repo=repo,
            workspace_id=WORKSPACE_ID,
        )

        assert len(result) == 1
        assert result[0]["section_id"] == str(section_a)

    @pytest.mark.asyncio
    async def test_invalid_work_item_id_raises(self) -> None:
        svc = _fake_service_found()
        repo = FakeCommentRepo()

        with pytest.raises(ValueError):
            await handle_list_comments(
                arguments={"work_item_id": "not-a-uuid"},
                service=svc,
                comment_repo=repo,
                workspace_id=WORKSPACE_ID,
            )
