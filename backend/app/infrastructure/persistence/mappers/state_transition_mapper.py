"""Mapper between StateTransition domain value object and StateTransitionORM.

from_state is nullable in the DB (NULL = creation event) but WorkItemState-typed in
the domain VO. The mapper returns the raw ORM row dict for creation events where
from_state is NULL — callers that insert a creation event pass from_state=None and
the DB trigger enforces append-only.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.value_objects.state_transition import StateTransition
from app.domain.value_objects.work_item_state import WorkItemState
from app.infrastructure.persistence.models.orm import StateTransitionORM


def to_domain(row: StateTransitionORM) -> StateTransition:
    return StateTransition(
        work_item_id=row.work_item_id,
        from_state=WorkItemState(row.from_state)
        if row.from_state is not None
        else WorkItemState.DRAFT,
        to_state=WorkItemState(row.to_state),
        actor_id=row.actor_id,  # nullable after migration 0010
        triggered_at=row.triggered_at,
        reason=row.reason,
        is_override=row.is_override,
        override_justification=row.override_justification,
    )


_UNSET = object()


def to_orm(
    transition: StateTransition,
    *,
    workspace_id: UUID,
    from_state_override: str | None | object = _UNSET,
) -> StateTransitionORM:
    """Build a new StateTransitionORM insert row.

    from_state_override: pass None explicitly to store a NULL from_state (creation event).
    When omitted (sentinel), uses transition.from_state.value.
    """
    row = StateTransitionORM()
    row.work_item_id = transition.work_item_id
    row.workspace_id = workspace_id
    row.from_state = (
        transition.from_state.value if from_state_override is _UNSET else from_state_override  # type: ignore[assignment]
    )
    row.to_state = transition.to_state.value
    row.actor_id = transition.actor_id
    row.triggered_at = transition.triggered_at
    row.reason = transition.reason
    row.is_override = transition.is_override
    row.override_justification = transition.override_justification
    return row
