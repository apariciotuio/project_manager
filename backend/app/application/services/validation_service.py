"""EP-06 — ValidationService: checklist management, on_review_closed, waive.

Single source of truth for "are all required validations satisfied?".
All mutations recompute the state and persist atomically in the caller's session.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.application.events.event_bus import EventBus
from app.application.events.review_events import ValidationStatusChangedEvent
from app.domain.models.review import (
    ReviewDecision,
    ReviewRequest,
    ReviewResponse,
    ValidationRequirement,
    ValidationState,
    ValidationStatus,
    WaiveRequiredRuleError,
)
from app.domain.repositories.review_repository import (
    IReviewRequestRepository,
    IValidationRequirementRepository,
    IValidationStatusRepository,
)

logger = logging.getLogger(__name__)


class ChecklistResult:
    def __init__(
        self,
        required: list[tuple[ValidationRequirement, ValidationStatus | None]],
        recommended: list[tuple[ValidationRequirement, ValidationStatus | None]],
    ) -> None:
        self.required = required
        self.recommended = recommended


class ValidationService:
    def __init__(
        self,
        *,
        requirement_repo: IValidationRequirementRepository,
        status_repo: IValidationStatusRepository,
        review_request_repo: IReviewRequestRepository,
        events: EventBus,
    ) -> None:
        self._requirements = requirement_repo
        self._statuses = status_repo
        self._review_requests = review_request_repo
        self._events = events

    async def get_checklist(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        work_item_type: str,
    ) -> ChecklistResult:
        """Return all applicable rules split into required/recommended, with current status."""
        rules = await self._requirements.list_applicable(
            workspace_id=workspace_id, work_item_type=work_item_type
        )
        statuses = await self._statuses.list_for_work_item(work_item_id)
        status_by_rule = {s.rule_id: s for s in statuses}

        required: list[tuple[ValidationRequirement, ValidationStatus | None]] = []
        recommended: list[tuple[ValidationRequirement, ValidationStatus | None]] = []
        for rule in rules:
            vs = status_by_rule.get(rule.rule_id)
            if rule.required:
                required.append((rule, vs))
            else:
                recommended.append((rule, vs))

        return ChecklistResult(required=required, recommended=recommended)

    async def on_review_closed(
        self,
        review_request: ReviewRequest,
        response: ReviewResponse,
        workspace_id: UUID,
    ) -> None:
        """Called atomically inside the same session as the review_response INSERT.

        If the request has a linked validation_rule_id and the decision is approved,
        mark the corresponding ValidationStatus as passed. Idempotent — repeated calls
        on an already-passed rule are no-ops.

        Rejected / changes_requested decisions leave the validation_status as pending.
        """
        if review_request.validation_rule_id is None:
            return

        vs = await self._statuses.get_by_work_item_and_rule(
            work_item_id=review_request.work_item_id,
            rule_id=review_request.validation_rule_id,
        )
        if vs is None:
            # Status row may not exist if the rule was added after the review was requested
            logger.warning(
                "validation.on_review_closed: no status row found for rule %s on work item %s",
                review_request.validation_rule_id,
                review_request.work_item_id,
            )
            return

        if response.decision is ReviewDecision.APPROVED:
            if vs.status is ValidationState.PASSED:
                return  # idempotent
            try:
                vs.mark_passed(by_review_request_id=review_request.id)
            except Exception:
                logger.warning(
                    "validation.on_review_closed: could not mark passed for %s (current=%s)",
                    review_request.validation_rule_id,
                    vs.status.value,
                )
                return
            await self._statuses.save(vs)
            await self._events.emit(
                ValidationStatusChangedEvent(
                    work_item_id=review_request.work_item_id,
                    rule_id=review_request.validation_rule_id,
                    workspace_id=workspace_id,
                    new_status=ValidationState.PASSED.value,
                )
            )
        # rejected / changes_requested → status stays pending; no mutation

    async def waive_validation(
        self,
        *,
        work_item_id: UUID,
        rule_id: str,
        workspace_id: UUID,
        waived_by: UUID,
        waive_reason: str | None = None,
    ) -> ValidationStatus:
        """Waive a recommended validation rule. Raises WaiveRequiredRuleError if required."""
        rule = await self._requirements.get(rule_id)
        if rule is None:
            from app.application.services.review_request_service import ValidationRuleNotFoundError
            raise ValidationRuleNotFoundError(rule_id)

        if rule.required:
            raise WaiveRequiredRuleError(
                f"rule {rule_id!r} is required and cannot be waived"
            )

        vs = await self._statuses.get_by_work_item_and_rule(
            work_item_id=work_item_id, rule_id=rule_id
        )
        if vs is None:
            vs = ValidationStatus.create_pending(work_item_id=work_item_id, rule_id=rule_id)

        vs.mark_waived(waived_by=waived_by, waive_reason=waive_reason)
        saved = await self._statuses.save(vs)

        await self._events.emit(
            ValidationStatusChangedEvent(
                work_item_id=work_item_id,
                rule_id=rule_id,
                workspace_id=workspace_id,
                new_status=ValidationState.WAIVED.value,
            )
        )
        return saved

    async def all_required_passed(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        work_item_type: str,
    ) -> bool:
        """True iff every required rule applicable to this work item type has passed status."""
        required_rules = await self._requirements.list_applicable(
            workspace_id=workspace_id,
            work_item_type=work_item_type,
            required_only=True,
        )
        if not required_rules:
            return True
        required_rule_ids = {r.rule_id for r in required_rules}

        statuses = await self._statuses.list_for_work_item(work_item_id)
        passed_ids = {
            s.rule_id for s in statuses
            if s.status is ValidationState.PASSED and s.rule_id in required_rule_ids
        }
        return required_rule_ids <= passed_ids
