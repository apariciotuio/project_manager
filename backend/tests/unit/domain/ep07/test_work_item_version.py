"""EP-07 Phase 1 — WorkItemVersion domain entity tests."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.models.work_item_version import (
    VersionActorType,
    VersionTrigger,
    WorkItemVersion,
)


def _make(version_number: int = 1, trigger: str = "content_edit") -> WorkItemVersion:
    return WorkItemVersion(
        id=uuid4(),
        work_item_id=uuid4(),
        version_number=version_number,
        snapshot={"schema_version": 1, "work_item": {}, "sections": [], "task_node_ids": []},
        created_by=uuid4(),
        created_at=datetime.now(UTC),
        trigger=VersionTrigger(trigger),
    )


class TestWorkItemVersionInvariants:
    def test_valid_version_number_positive(self) -> None:
        v = _make(version_number=1)
        assert v.version_number == 1

    def test_version_number_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _make(version_number=0)

    def test_version_number_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _make(version_number=-1)

    def test_valid_triggers(self) -> None:
        for t in ("content_edit", "state_transition", "review_outcome", "breakdown_change", "manual"):
            v = _make(trigger=t)
            assert v.trigger == VersionTrigger(t)

    def test_invalid_trigger_raises(self) -> None:
        with pytest.raises(ValueError):
            WorkItemVersion(
                id=uuid4(),
                work_item_id=uuid4(),
                version_number=1,
                snapshot={},
                created_by=uuid4(),
                created_at=datetime.now(UTC),
                trigger="invalid_trigger",  # type: ignore[arg-type]
            )

    def test_immutable_after_construction(self) -> None:
        v = _make()
        with pytest.raises(Exception):  # FrozenInstanceError
            v.version_number = 99  # type: ignore[misc]

    def test_snapshot_schema_version_defaults_to_1(self) -> None:
        v = _make()
        assert v.snapshot_schema_version == 1

    def test_archived_defaults_to_false(self) -> None:
        v = _make()
        assert v.archived is False

    def test_actor_type_defaults_to_human(self) -> None:
        v = _make()
        assert v.actor_type == VersionActorType.HUMAN

    def test_actor_type_enum_validation(self) -> None:
        with pytest.raises(ValueError):
            WorkItemVersion(
                id=uuid4(),
                work_item_id=uuid4(),
                version_number=1,
                snapshot={},
                created_by=uuid4(),
                created_at=datetime.now(UTC),
                trigger=VersionTrigger.CONTENT_EDIT,
                actor_type="invalid_actor",  # type: ignore[arg-type]
            )
