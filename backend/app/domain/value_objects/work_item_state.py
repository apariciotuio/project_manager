"""WorkItemState — primary FSM states for WorkItem."""

from __future__ import annotations

from enum import StrEnum


class WorkItemState(StrEnum):
    DRAFT = "draft"
    IN_CLARIFICATION = "in_clarification"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    PARTIALLY_VALIDATED = "partially_validated"
    READY = "ready"
    EXPORTED = "exported"
