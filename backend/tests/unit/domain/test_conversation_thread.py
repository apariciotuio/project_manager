"""Unit tests for ConversationThread entity — RED phase."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.models.conversation_thread import ConversationThread

_NOW = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_LATER = _NOW + timedelta(hours=1)


def _make(
    work_item_id: object = None,
    deleted_at: datetime | None = None,
) -> ConversationThread:
    from uuid import UUID
    wid: UUID | None = work_item_id  # type: ignore[assignment]
    return ConversationThread(
        id=uuid4(),
        user_id=uuid4(),
        work_item_id=wid,
        dundun_conversation_id="dun-abc123",
        last_message_preview=None,
        last_message_at=None,
        created_at=_NOW,
        deleted_at=deleted_at,
    )


# ---------------------------------------------------------------------------
# archive()
# ---------------------------------------------------------------------------


class TestArchive:
    def test_active_thread_can_be_archived(self) -> None:
        thread = _make()
        result = thread.archive(_NOW)
        assert result.deleted_at == _NOW

    def test_archive_returns_new_instance(self) -> None:
        thread = _make()
        result = thread.archive(_NOW)
        assert result is not thread

    def test_archive_is_idempotent(self) -> None:
        thread = _make(deleted_at=_NOW)
        result = thread.archive(_LATER)
        assert result is thread
        assert result.deleted_at == _NOW  # unchanged

    def test_archive_preserves_other_fields(self) -> None:
        thread = _make()
        result = thread.archive(_NOW)
        assert result.id == thread.id
        assert result.user_id == thread.user_id
        assert result.dundun_conversation_id == thread.dundun_conversation_id


# ---------------------------------------------------------------------------
# is_archived property
# ---------------------------------------------------------------------------


class TestIsArchived:
    def test_not_archived_when_deleted_at_is_none(self) -> None:
        thread = _make()
        assert thread.is_archived is False

    def test_archived_when_deleted_at_set(self) -> None:
        thread = _make(deleted_at=_NOW)
        assert thread.is_archived is True


# ---------------------------------------------------------------------------
# is_general_thread property
# ---------------------------------------------------------------------------


class TestIsGeneralThread:
    def test_general_thread_when_work_item_id_none(self) -> None:
        thread = _make(work_item_id=None)
        assert thread.is_general_thread is True

    def test_not_general_thread_when_work_item_id_set(self) -> None:
        thread = _make(work_item_id=uuid4())
        assert thread.is_general_thread is False

    def test_general_thread_can_be_archived(self) -> None:
        thread = _make(work_item_id=None)
        result = thread.archive(_NOW)
        assert result.is_archived is True
