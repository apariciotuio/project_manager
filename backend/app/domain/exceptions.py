"""Domain exceptions for WorkItem and related entities."""
from __future__ import annotations

from uuid import UUID


class InvalidTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str) -> None:
        super().__init__(f"Invalid transition: {from_state} -> {to_state}")
        self.from_state = from_state
        self.to_state = to_state


class NotOwnerError(Exception):
    def __init__(self, actor_id: UUID, item_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} is not the owner of item {item_id}")
        self.actor_id = actor_id
        self.item_id = item_id


class InvalidOverrideError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid override: {reason}")
        self.reason = reason


class MandatoryValidationsPendingError(Exception):
    def __init__(self, item_id: UUID, pending_ids: tuple[object, ...]) -> None:
        super().__init__(f"Mandatory validations pending for item {item_id}: {pending_ids}")
        self.item_id = item_id
        self.pending_ids = pending_ids


class OwnerSuspendedError(Exception):
    def __init__(self, owner_id: UUID) -> None:
        super().__init__(f"Owner {owner_id} is suspended")
        self.owner_id = owner_id


class TargetUserSuspendedError(Exception):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"Target user {user_id} is suspended")
        self.user_id = user_id


class CreatorNotMemberError(Exception):
    def __init__(self, creator_id: UUID, workspace_id: UUID) -> None:
        super().__init__(
            f"Creator {creator_id} is not an active member of workspace {workspace_id}"
        )
        self.creator_id = creator_id
        self.workspace_id = workspace_id


class ConfirmationRequiredError(Exception):
    def __init__(self, pending_ids: tuple[object, ...]) -> None:
        super().__init__(f"Confirmation required; pending: {pending_ids}")
        self.pending_ids = pending_ids


class TargetUserNotInWorkspaceError(Exception):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"User {user_id} is not a member of the workspace")
        self.user_id = user_id


class WorkItemNotFoundError(Exception):
    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"Work item {item_id} not found")
        self.item_id = item_id


class CannotDeleteNonDraftError(Exception):
    def __init__(self, item_id: UUID, state: str) -> None:
        super().__init__(f"Cannot delete work item {item_id} in state {state!r}")
        self.item_id = item_id
        self.state = state


class UserNotFoundError(Exception):
    """Raised when an FK violation occurs referencing a non-existent user (owner/creator)."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


class InvalidWorkItemError(Exception):
    """Raised when a DB CHECK constraint violation occurs on work_items."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"Invalid work item field '{field}': {reason}")
        self.field = field
        self.reason = reason


# ---------------------------------------------------------------------------
# EP-02 domain exceptions
# ---------------------------------------------------------------------------


class WorkItemDraftNotFoundError(Exception):
    def __init__(self, draft_id: UUID) -> None:
        super().__init__(f"Work item draft {draft_id} not found")
        self.draft_id = draft_id


class DraftForbiddenError(Exception):
    """Raised when a user tries to access a draft they don't own."""

    def __init__(self, actor_id: UUID, draft_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} does not own draft {draft_id}")
        self.actor_id = actor_id
        self.draft_id = draft_id


class WorkItemInvalidStateError(Exception):
    """Raised when an operation is attempted on a work item in the wrong state (EP-02)."""

    def __init__(self, item_id: UUID, expected_state: str, actual_state: str) -> None:
        super().__init__(
            f"Work item {item_id} must be in {expected_state!r} state, "
            f"but is in {actual_state!r}"
        )
        self.item_id = item_id
        self.expected_state = expected_state
        self.actual_state = actual_state


class TemplateNotFoundError(Exception):
    def __init__(self, template_id: UUID) -> None:
        super().__init__(f"Template {template_id} not found")
        self.template_id = template_id


class TemplateForbiddenError(Exception):
    """Raised when non-admin tries to create/update/delete a template, or system template is mutated."""  # noqa: E501

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DuplicateTemplateError(Exception):
    """Raised when a workspace already has a template for the given type."""

    def __init__(self, workspace_id: UUID, type_: str) -> None:
        super().__init__(f"Workspace {workspace_id} already has a template for type {type_!r}")
        self.workspace_id = workspace_id
        self.type_ = type_


# ---------------------------------------------------------------------------
# EP-03 domain exceptions
# ---------------------------------------------------------------------------


class SuggestionExpiredError(Exception):
    """Raised when accept() is called on an expired suggestion."""

    def __init__(self, suggestion_id: UUID) -> None:
        super().__init__(f"Suggestion {suggestion_id} has expired")
        self.suggestion_id = suggestion_id


class InvalidSuggestionStateError(Exception):
    """Raised when accept()/reject() is called on a non-pending suggestion."""

    def __init__(
        self, suggestion_id: UUID, current_status: object, attempted_transition: str
    ) -> None:
        super().__init__(
            f"Cannot {attempted_transition} suggestion {suggestion_id} "
            f"in state {current_status!r}"
        )
        self.suggestion_id = suggestion_id
        self.current_status = current_status
        self.attempted_transition = attempted_transition
