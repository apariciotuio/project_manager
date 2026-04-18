"""IWorkItemRepository — domain-layer interface for work item persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.domain.models.work_item import WorkItem
from app.domain.queries.page import Page
from app.domain.queries.work_item_filters import WorkItemFilters
from app.domain.queries.work_item_list_filters import WorkItemListFilters
from app.domain.value_objects.ownership_record import OwnershipRecord
from app.domain.value_objects.state_transition import StateTransition
from app.infrastructure.pagination import PaginationCursor, PaginationResult


class IWorkItemRepository(ABC):
    @abstractmethod
    async def get(self, item_id: UUID, workspace_id: UUID) -> WorkItem | None:
        """Return work item or None.

        workspace_id mismatch returns None (not raises) — existence disclosure prevention
        (CRIT-2). Both app-layer filter and RLS kill the row; explicit param is defense in depth.
        """

    @abstractmethod
    async def exists_in_workspace(self, item_id: UUID, workspace_id: UUID) -> bool:
        """Fast existence check without fetching full row."""

    @abstractmethod
    async def list(
        self,
        workspace_id: UUID,
        project_id: UUID,
        filters: WorkItemFilters,
    ) -> Page[WorkItem]:
        """Paginated list. Respects filters. Excludes soft-deleted unless include_deleted=True."""

    @abstractmethod
    async def save(self, item: WorkItem, workspace_id: UUID) -> WorkItem:
        """UPSERT. Returns persisted entity."""

    @abstractmethod
    async def delete(self, item_id: UUID, workspace_id: UUID) -> None:
        """Soft delete — sets deleted_at. Hard delete not supported."""

    @abstractmethod
    async def record_transition(
        self, transition: StateTransition, workspace_id: UUID
    ) -> None:
        """Insert into append-only state_transitions table."""

    @abstractmethod
    async def record_ownership_change(
        self,
        record: OwnershipRecord,
        workspace_id: UUID,
        previous_owner_id: UUID | None = None,
    ) -> None:
        """Insert into append-only ownership_history table."""

    @abstractmethod
    async def get_transitions(
        self, item_id: UUID, workspace_id: UUID
    ) -> Sequence[StateTransition]:
        """Return state transitions for item, ordered triggered_at DESC."""

    @abstractmethod
    async def get_ownership_history(
        self, item_id: UUID, workspace_id: UUID
    ) -> Sequence[OwnershipRecord]:
        """Return ownership records for item, ordered changed_at DESC."""

    @abstractmethod
    async def list_cursor(
        self,
        workspace_id: UUID,
        *,
        cursor: PaginationCursor | None,
        page_size: int,
        filters: WorkItemListFilters | None = None,
        current_user_id: UUID | None = None,
    ) -> PaginationResult:
        """Keyset-paginated list of work items for a workspace.

        Supports full filter/sort surface via WorkItemListFilters.
        Returns domain WorkItem objects in PaginationResult.rows.
        current_user_id is forwarded to the query builder for visibility rules.
        """
