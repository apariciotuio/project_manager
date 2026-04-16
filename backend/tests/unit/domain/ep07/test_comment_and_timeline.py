"""EP-07 — Comment entity + TimelineEvent value object."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.comment import (
    AnchorInvalidError,
    AnchorStatus,
    Comment,
    CommentActorType,
)
from app.domain.models.timeline_event import TimelineActorType, TimelineEvent


class TestComment:
    def test_create_valid(self) -> None:
        c = Comment.create(
            work_item_id=uuid4(), body="hello", actor_id=uuid4()
        )
        assert c.anchor_status is AnchorStatus.ACTIVE
        assert c.is_edited is False
        assert c.actor_type is CommentActorType.HUMAN

    def test_empty_body_rejected(self) -> None:
        with pytest.raises(ValueError):
            Comment.create(work_item_id=uuid4(), body="   ", actor_id=uuid4())

    def test_too_long_body_rejected(self) -> None:
        with pytest.raises(ValueError):
            Comment.create(work_item_id=uuid4(), body="x" * 10001, actor_id=uuid4())

    def test_anchor_range_without_section_rejected(self) -> None:
        with pytest.raises(AnchorInvalidError):
            Comment.create(
                work_item_id=uuid4(),
                body="pinned",
                actor_id=uuid4(),
                anchor_start_offset=0,
                anchor_end_offset=5,
            )

    def test_anchor_end_before_start_rejected(self) -> None:
        with pytest.raises(AnchorInvalidError):
            Comment.create(
                work_item_id=uuid4(),
                body="pinned",
                actor_id=uuid4(),
                anchor_section_id=uuid4(),
                anchor_start_offset=10,
                anchor_end_offset=5,
            )

    def test_edit_flips_flags(self) -> None:
        c = Comment.create(
            work_item_id=uuid4(), body="hello", actor_id=uuid4()
        )
        c.edit("updated body")
        assert c.is_edited is True
        assert c.edited_at is not None
        assert c.body == "updated body"

    def test_soft_delete_sets_timestamp(self) -> None:
        c = Comment.create(
            work_item_id=uuid4(), body="hello", actor_id=uuid4()
        )
        c.soft_delete()
        assert c.deleted_at is not None


class TestTimelineEvent:
    def test_create_defaults(self) -> None:
        ev = TimelineEvent.create(
            work_item_id=uuid4(),
            workspace_id=uuid4(),
            event_type="content_edit",
            actor_type=TimelineActorType.HUMAN,
            summary="edited description",
        )
        assert ev.payload == {}
        assert ev.actor_type is TimelineActorType.HUMAN

    def test_summary_too_long_rejected(self) -> None:
        with pytest.raises(ValueError):
            TimelineEvent.create(
                work_item_id=uuid4(),
                workspace_id=uuid4(),
                event_type="x",
                actor_type=TimelineActorType.HUMAN,
                summary="y" * 256,
            )
