"""EP-05 — TaskNode entity + TaskDependency VO.

Adjacency list tree with materialised path. Status FSM is enforced in the
application layer (TaskService), not at the DB level.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class TaskStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskGenerationSource(StrEnum):
    LLM = "llm"
    MANUAL = "manual"


class PredecessorNotDoneError(Exception):
    pass


@dataclass
class TaskNode:
    id: UUID
    work_item_id: UUID
    parent_id: UUID | None
    title: str
    description: str
    display_order: int
    status: TaskStatus
    generation_source: TaskGenerationSource
    materialized_path: str
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID

    @classmethod
    def create(
        cls,
        *,
        work_item_id: UUID,
        parent_id: UUID | None,
        title: str,
        display_order: int,
        created_by: UUID,
        description: str = "",
        source: TaskGenerationSource = TaskGenerationSource.LLM,
        materialized_path: str = "",
    ) -> TaskNode:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            parent_id=parent_id,
            title=title,
            description=description,
            display_order=display_order,
            status=TaskStatus.DRAFT,
            generation_source=source,
            materialized_path=materialized_path,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
        )

    def start(self, actor_id: UUID) -> None:
        self.status = TaskStatus.IN_PROGRESS
        self.updated_by = actor_id
        self.updated_at = datetime.now(UTC)

    def mark_done(self, actor_id: UUID, predecessor_statuses: list[TaskStatus]) -> None:
        if any(s is not TaskStatus.DONE for s in predecessor_statuses):
            raise PredecessorNotDoneError(
                "cannot mark task as done while predecessors are still open"
            )
        self.status = TaskStatus.DONE
        self.updated_by = actor_id
        self.updated_at = datetime.now(UTC)

    def reopen(self, actor_id: UUID) -> None:
        """Explicit re-open (resolution #20 — no reverse FSM; reopen emits an event)."""
        self.status = TaskStatus.IN_PROGRESS
        self.updated_by = actor_id
        self.updated_at = datetime.now(UTC)


@dataclass(frozen=True)
class TaskDependency:
    id: UUID
    source_id: UUID  # the dependent — waits for target
    target_id: UUID  # the predecessor
    created_at: datetime
    created_by: UUID

    @classmethod
    def create(cls, *, source_id: UUID, target_id: UUID, created_by: UUID) -> TaskDependency:
        if source_id == target_id:
            raise ValueError("self-dependency is not allowed")
        return cls(
            id=uuid4(),
            source_id=source_id,
            target_id=target_id,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
