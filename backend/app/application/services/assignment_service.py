"""EP-08 Group D — AssignmentService.

Handles:
  - assign_owner: validate + assign + emit WorkItemOwnerChangedEvent
  - suggest_owner: routing rule lookup by item_type, skip suspended
  - suggest_reviewer: routing rule lookup, return team or user suggestion
  - bulk_assign: all-or-nothing on suspended target; per-item results otherwise

Note: does NOT re-implement reassign logic — delegates item mutation to the
work_item_repo directly to keep this service thin. Full audit history is
handled by the event bus subscriber.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised when assignment target fails validation (suspended or not member)."""


@dataclass
class WorkItemOwnerChangedEvent:
    work_item_id: UUID
    workspace_id: UUID
    previous_owner_id: UUID
    new_owner_id: UUID
    changed_by: UUID
    reason: str | None = None


class AssignmentService:
    """Application service for owner/reviewer assignment operations."""

    def __init__(
        self,
        *,
        user_repo: Any,
        work_item_repo: Any,
        routing_rule_repo: Any,
        membership_repo: Any,
        event_bus: Any,
    ) -> None:
        self._users = user_repo
        self._items = work_item_repo
        self._rules = routing_rule_repo
        self._memberships = membership_repo
        self._bus = event_bus

    async def assign_owner(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        actor_id: UUID,
        workspace_id: UUID,
        reason: str | None = None,
    ) -> Any:
        """Assign a new owner to a work item.

        Raises:
            ValidationError: when target user is suspended or not a workspace member.
        """
        target = await self._users.get_by_id(user_id)
        if target is None or getattr(target, "status", "active") != "active":
            raise ValidationError(
                f"user {user_id} is suspended and cannot receive assignments"
            )

        is_member = await self._memberships.is_member(workspace_id, user_id)
        if not is_member:
            raise ValidationError(
                f"user {user_id} is not a member of workspace {workspace_id}"
            )

        item = await self._items.get(item_id, workspace_id)
        if item is None:
            raise LookupError(f"work item {item_id} not found in workspace {workspace_id}")

        previous_owner_id = item.owner_id
        item.owner_id = user_id
        saved = await self._items.save(item)

        await self._bus.emit(
            WorkItemOwnerChangedEvent(
                work_item_id=item_id,
                workspace_id=workspace_id,
                previous_owner_id=previous_owner_id,
                new_owner_id=user_id,
                changed_by=actor_id,
                reason=reason,
            )
        )

        logger.info(
            "assignment: owner changed item=%s previous=%s new=%s actor=%s",
            item_id,
            previous_owner_id,
            user_id,
            actor_id,
        )
        return saved

    async def suggest_owner(
        self, *, item_type: str, workspace_id: UUID
    ) -> dict[str, Any] | None:
        """Return the first valid suggested owner for the item type.

        Returns None if no matching rule or all candidates are suspended/deleted.
        """
        rules = await self._rules.list_for_workspace(workspace_id)
        for rule in rules:
            if rule.item_type != item_type:
                continue
            suggested_owner_id = getattr(rule, "suggested_owner_id", None)
            if suggested_owner_id is None:
                continue
            user = await self._users.get_by_id(suggested_owner_id)
            if user is not None and getattr(user, "status", "active") == "active":
                return {"type": "user", "id": suggested_owner_id}
        return None

    async def suggest_reviewer(
        self, *, item_type: str, workspace_id: UUID
    ) -> dict[str, Any] | None:
        """Return the first valid suggested reviewer (team or user) for the item type.

        Returns None if no matching rule or all candidates are suspended/deleted.
        """
        rules = await self._rules.list_for_workspace(workspace_id)
        for rule in rules:
            if rule.item_type != item_type:
                continue
            suggested_team_id = getattr(rule, "suggested_team_id", None)
            if suggested_team_id is not None:
                return {"type": "team", "id": suggested_team_id}
            suggested_owner_id = getattr(rule, "suggested_owner_id", None)
            if suggested_owner_id is not None:
                user = await self._users.get_by_id(suggested_owner_id)
                if user is not None and getattr(user, "status", "active") == "active":
                    return {"type": "user", "id": suggested_owner_id}
        return None

    async def bulk_assign(
        self,
        *,
        item_ids: list[UUID],
        user_id: UUID,
        actor_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, Any]]:
        """Assign owner to multiple items.

        Raises ValidationError (all-or-nothing) if target is suspended.
        Returns per-item results for other failures.
        """
        # All-or-nothing check for suspended target
        target = await self._users.get_by_id(user_id)
        if target is None or getattr(target, "status", "active") != "active":
            raise ValidationError(
                f"user {user_id} is suspended — bulk assign rejected for all items"
            )

        results: list[dict[str, Any]] = []
        for item_id in item_ids:
            try:
                await self.assign_owner(
                    item_id=item_id,
                    user_id=user_id,
                    actor_id=actor_id,
                    workspace_id=workspace_id,
                )
                results.append({"item_id": str(item_id), "success": True})
            except (ValidationError, LookupError, Exception) as exc:
                results.append(
                    {"item_id": str(item_id), "success": False, "error": str(exc)}
                )
        return results
