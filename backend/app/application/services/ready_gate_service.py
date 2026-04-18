"""EP-06 — ReadyGateService: checks all mandatory validations before Ready transition.

Pure — no side effects. Called by WorkItemService.transition() when target_state=READY.
Injected as a callable (Callable[[UUID, UUID, str], Awaitable[GateResult]]) so EP-01's
WorkItemService doesn't need to import EP-06 types directly at module load time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.models.review import ValidationRequirement, ValidationState, ValidationStatus
from app.domain.repositories.review_repository import (
    IValidationRequirementRepository,
    IValidationStatusRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Blocker:
    rule_id: str
    label: str
    status: str
    required: bool = True


@dataclass(frozen=True)
class GateResult:
    ok: bool
    blockers: list[Blocker] = field(default_factory=list)


class ReadyGateService:
    def __init__(
        self,
        *,
        requirement_repo: IValidationRequirementRepository,
        status_repo: IValidationStatusRepository,
    ) -> None:
        self._requirements = requirement_repo
        self._statuses = status_repo

    async def check(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        work_item_type: str,
    ) -> GateResult:
        """Return GateResult(ok, blockers) — no side effects.

        ALG-3 (design.md): required+waived is treated as blocking with a warning.
        DB invariant prevents it, but the gate is the last line of defence.
        """
        required_rules = await self._requirements.list_applicable(
            workspace_id=workspace_id,
            work_item_type=work_item_type,
            required_only=True,
        )
        if not required_rules:
            return GateResult(ok=True, blockers=[])

        required_by_id: dict[str, ValidationRequirement] = {r.rule_id: r for r in required_rules}
        statuses = await self._statuses.list_for_work_item(work_item_id)
        status_by_rule: dict[str, ValidationStatus] = {s.rule_id: s for s in statuses}

        blockers: list[Blocker] = []
        for rule_id, rule in required_by_id.items():
            vs = status_by_rule.get(rule_id)
            if vs is None:
                # No status row → pending by default
                blockers.append(Blocker(rule_id=rule_id, label=rule.label, status="pending"))
                continue

            if vs.status is ValidationState.PASSED:
                continue  # good

            if vs.status is ValidationState.WAIVED:
                # Belt-and-suspenders guard (ALG-3)
                logger.warning(
                    "ready_gate: required rule %r has waived status on item %s — treating as blocking",
                    rule_id,
                    work_item_id,
                )
                blockers.append(Blocker(rule_id=rule_id, label=rule.label, status="waived"))
            elif vs.status is ValidationState.OBSOLETE:
                # Obsolete required rule — treat as blocking; shouldn't happen but guard it
                logger.warning(
                    "ready_gate: required rule %r is obsolete on item %s — treating as blocking",
                    rule_id,
                    work_item_id,
                )
                blockers.append(Blocker(rule_id=rule_id, label=rule.label, status="obsolete"))
            else:
                # pending
                blockers.append(Blocker(rule_id=rule_id, label=rule.label, status=vs.status.value))

        return GateResult(ok=len(blockers) == 0, blockers=blockers)
