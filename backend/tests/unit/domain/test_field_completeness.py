"""Unit tests for domain/services/completeness_service.compute_completeness — RED phase.

Scoring algorithm (additive, weights sum to 100):
  - title >= 10 chars           : 25 pts
  - description >= 50 chars     : 35 pts
  - priority set                : 15 pts
  - due_date set                : 10 pts
  - owner assigned, not suspended: 15 pts
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4


def _make_work_item(**kwargs):  # type: ignore[no-untyped-def]
    from app.domain.models.work_item import WorkItem
    from app.domain.value_objects.work_item_type import WorkItemType

    defaults: dict = {
        "title": "A valid title",
        "type": WorkItemType.BUG,
        "owner_id": uuid4(),
        "creator_id": uuid4(),
        "project_id": uuid4(),
    }
    defaults.update(kwargs)
    wi = WorkItem.create(**defaults)
    # Allow caller to override post-construction fields
    for k, v in kwargs.items():
        if k not in defaults or k in ("owner_suspended_flag",):
            pass
    return wi


class TestComputeCompleteness:
    """Tests for compute_completeness(WorkItem) -> int."""

    def test_empty_work_item_scores_zero(self) -> None:
        """Minimal item: short title, no description, no priority, no due_date, no owner."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        wi = WorkItem.create(
            title="Bug",  # < 10 chars, does not earn title points
            type=WorkItemType.BUG,
            owner_id=owner,
            creator_id=owner,
            project_id=uuid4(),
        )
        wi.owner_id = None  # type: ignore[assignment]  # no owner
        wi.description = None
        wi.owner_suspended_flag = False

        score = compute_completeness(wi)

        assert score == 0

    def test_fully_filled_item_scores_100(self) -> None:
        """All fields present and above thresholds."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.priority import Priority
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        wi = WorkItem.create(
            title="A title with ten+ chars",  # >= 10 chars → 25 pts
            type=WorkItemType.BUG,
            owner_id=owner,
            creator_id=owner,
            project_id=uuid4(),
            description="A" * 50,  # >= 50 chars → 35 pts
            priority=Priority.HIGH,  # set → 15 pts
            due_date=date(2026, 12, 31),  # set → 10 pts
        )
        # owner assigned, not suspended → 15 pts

        score = compute_completeness(wi)

        assert score == 100

    def test_partial_item_scores_between_0_and_100(self) -> None:
        """title + description only → 60 pts."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        wi = WorkItem.create(
            title="A title that is long enough",  # >= 10 chars → 25 pts
            type=WorkItemType.BUG,
            owner_id=owner,
            creator_id=owner,
            project_id=uuid4(),
            description="B" * 50,  # >= 50 chars → 35 pts
        )
        wi.owner_id = None  # type: ignore[assignment]  # no owner → 0 pts
        # no priority → 0 pts; no due_date → 0 pts

        score = compute_completeness(wi)

        assert score == 60  # 25 + 35

    def test_missing_title_threshold_never_100(self) -> None:
        """Short title (< 10 chars) means at most 75 pts even with all other fields filled."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.priority import Priority
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        wi = WorkItem.create(
            title="Short",  # 5 chars, < 10 → 0 pts for title
            type=WorkItemType.BUG,
            owner_id=owner,
            creator_id=owner,
            project_id=uuid4(),
            description="C" * 50,
            priority=Priority.HIGH,
            due_date=date(2026, 12, 31),
        )

        score = compute_completeness(wi)

        assert score < 100
        assert score == 75  # 35 + 15 + 10 + 15

    def test_suspended_owner_does_not_earn_owner_points(self) -> None:
        """owner_suspended_flag=True → owner dimension is 0 pts."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.priority import Priority
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        wi = WorkItem.create(
            title="A title with ten+ chars",
            type=WorkItemType.BUG,
            owner_id=owner,
            creator_id=owner,
            project_id=uuid4(),
            description="D" * 50,
            priority=Priority.HIGH,
            due_date=date(2026, 12, 31),
        )
        wi.owner_suspended_flag = True  # suspended → 0 pts

        score = compute_completeness(wi)

        assert score == 85  # 100 - 15

    def test_score_is_int_in_range(self) -> None:
        """Score is always an int in [0, 100]."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.priority import Priority
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        for _ in range(5):
            wi = WorkItem.create(
                title="Some title for testing",
                type=WorkItemType.BUG,
                owner_id=uuid4(),
                creator_id=owner,
                project_id=uuid4(),
                priority=Priority.LOW,
            )
            score = compute_completeness(wi)
            assert isinstance(score, int)
            assert 0 <= score <= 100

    def test_description_below_threshold_earns_no_points(self) -> None:
        """description < 50 chars → 0 pts for description."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        wi = WorkItem.create(
            title="A title with ten+ chars",
            type=WorkItemType.BUG,
            owner_id=owner,
            creator_id=owner,
            project_id=uuid4(),
            description="Short",  # < 50 chars → 0 pts
        )
        wi.owner_id = None  # type: ignore[assignment]

        score = compute_completeness(wi)

        assert score == 25  # title only

    def test_work_item_method_delegates_to_function(self) -> None:
        """WorkItem.compute_completeness() must return same result as the module function."""
        from app.domain.models.work_item import WorkItem
        from app.domain.services.completeness_service import compute_completeness
        from app.domain.value_objects.priority import Priority
        from app.domain.value_objects.work_item_type import WorkItemType

        owner = uuid4()
        wi = WorkItem.create(
            title="A title with ten+ chars",
            type=WorkItemType.BUG,
            owner_id=owner,
            creator_id=owner,
            project_id=uuid4(),
            priority=Priority.HIGH,
        )

        assert wi.compute_completeness() == compute_completeness(wi)
