"""Unit tests for ValidationRuleService — EP-10 admin rules."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.services.validation_rule_service import (
    DuplicateRuleError,
    GlobalBlockerInEffectError,
    RuleHasHistoryError,
    ValidationRuleNotFoundError,
    ValidationRuleService,
    _annotate_precedence,
)
from app.domain.models.validation_rule import ValidationRule
from app.domain.repositories.validation_rule_repository import IValidationRuleRepository

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeValidationRuleRepo(IValidationRuleRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, ValidationRule] = {}
        self._history: set[UUID] = set()

    async def create(self, rule: ValidationRule) -> ValidationRule:
        self._by_id[rule.id] = rule
        return rule

    async def get_by_id(self, rule_id: UUID, workspace_id: UUID) -> ValidationRule | None:
        r = self._by_id.get(rule_id)
        if r and r.workspace_id == workspace_id:
            return r
        return None

    async def list_for_workspace(
        self,
        workspace_id: UUID,
        *,
        project_id: UUID | None = None,
        work_item_type: str | None = None,
        active_only: bool = True,
    ) -> list[ValidationRule]:
        result = [r for r in self._by_id.values() if r.workspace_id == workspace_id]
        if project_id is not None:
            result = [r for r in result if r.project_id is None or r.project_id == project_id]
        else:
            result = [r for r in result if r.project_id is None]
        if work_item_type:
            result = [r for r in result if r.work_item_type == work_item_type]
        if active_only:
            result = [r for r in result if r.active]
        return result

    async def save(self, rule: ValidationRule) -> ValidationRule:
        self._by_id[rule.id] = rule
        return rule

    async def delete(self, rule_id: UUID, workspace_id: UUID) -> None:
        self._by_id.pop(rule_id, None)

    async def has_history(self, rule_id: UUID) -> bool:
        return rule_id in self._history


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log_event(self, **kwargs: object) -> None:
        self.events.append(kwargs)


_WS_ID = uuid4()
_ACTOR_ID = uuid4()
_PROJ_ID = uuid4()


def _make_service(repo: FakeValidationRuleRepo | None = None) -> tuple[ValidationRuleService, FakeValidationRuleRepo, FakeAudit]:
    r = repo or FakeValidationRuleRepo()
    audit = FakeAudit()
    svc = ValidationRuleService(repo=r, audit=audit)  # type: ignore[arg-type]
    return svc, r, audit


# ---------------------------------------------------------------------------
# Tests: create
# ---------------------------------------------------------------------------


class TestCreateValidationRule:
    @pytest.mark.asyncio
    async def test_create_workspace_scope_success(self) -> None:
        svc, repo, audit = _make_service()

        rule = await svc.create_rule(
            _WS_ID,
            project_id=None,
            work_item_type="feature",
            validation_type="acceptance_criteria",
            enforcement="required",
            actor_id=_ACTOR_ID,
        )

        assert rule.workspace_id == _WS_ID
        assert rule.project_id is None
        assert rule.enforcement == "required"
        assert any(e["action"] == "validation_rule_created" for e in audit.events)

    @pytest.mark.asyncio
    async def test_create_project_scope_success(self) -> None:
        svc, repo, _ = _make_service()

        rule = await svc.create_rule(
            _WS_ID,
            project_id=_PROJ_ID,
            work_item_type="bug",
            validation_type="reviewer_approval",
            enforcement="recommended",
            actor_id=_ACTOR_ID,
        )

        assert rule.project_id == _PROJ_ID

    @pytest.mark.asyncio
    async def test_create_duplicate_workspace_scope_raises_409(self) -> None:
        svc, repo, _ = _make_service()
        await svc.create_rule(_WS_ID, project_id=None, work_item_type="feature",
                               validation_type="ac", enforcement="required", actor_id=_ACTOR_ID)

        with pytest.raises(DuplicateRuleError):
            await svc.create_rule(_WS_ID, project_id=None, work_item_type="feature",
                                   validation_type="ac", enforcement="recommended", actor_id=_ACTOR_ID)

    @pytest.mark.asyncio
    async def test_create_project_rule_when_global_blocker_raises_409(self) -> None:
        svc, repo, _ = _make_service()
        # Create workspace-level blocked_override first
        await svc.create_rule(
            _WS_ID, project_id=None, work_item_type="feature",
            validation_type="ac", enforcement="blocked_override", actor_id=_ACTOR_ID
        )

        with pytest.raises(GlobalBlockerInEffectError):
            await svc.create_rule(
                _WS_ID, project_id=_PROJ_ID, work_item_type="feature",
                validation_type="ac", enforcement="required", actor_id=_ACTOR_ID
            )

    @pytest.mark.asyncio
    async def test_create_invalid_enforcement_raises_422(self) -> None:
        svc, _, _ = _make_service()
        with pytest.raises(ValueError):
            await svc.create_rule(
                _WS_ID, project_id=None, work_item_type="feature",
                validation_type="ac", enforcement="super_strict", actor_id=_ACTOR_ID
            )


# ---------------------------------------------------------------------------
# Tests: update
# ---------------------------------------------------------------------------


class TestUpdateValidationRule:
    @pytest.mark.asyncio
    async def test_update_enforcement(self) -> None:
        svc, repo, _ = _make_service()
        rule = await svc.create_rule(_WS_ID, project_id=None, work_item_type="f",
                                      validation_type="ac", enforcement="recommended", actor_id=_ACTOR_ID)

        updated, superseded = await svc.update_rule(_WS_ID, rule.id,
                                                    enforcement="required", actor_id=_ACTOR_ID)
        assert updated.enforcement == "required"
        assert superseded == []

    @pytest.mark.asyncio
    async def test_update_to_blocked_override_flags_project_rules(self) -> None:
        svc, repo, _ = _make_service()
        # Create workspace rule
        ws_rule = await svc.create_rule(_WS_ID, project_id=None, work_item_type="f",
                                         validation_type="ac", enforcement="recommended", actor_id=_ACTOR_ID)
        # Create project rule
        proj_rule = await svc.create_rule(_WS_ID, project_id=_PROJ_ID, work_item_type="f",
                                           validation_type="ac", enforcement="required", actor_id=_ACTOR_ID)

        _, superseded = await svc.update_rule(_WS_ID, ws_rule.id,
                                              enforcement="blocked_override", actor_id=_ACTOR_ID)
        assert proj_rule.id in superseded

    @pytest.mark.asyncio
    async def test_update_not_found_raises_404(self) -> None:
        svc, _, _ = _make_service()
        with pytest.raises(ValidationRuleNotFoundError):
            await svc.update_rule(_WS_ID, uuid4(), enforcement="required", actor_id=_ACTOR_ID)


# ---------------------------------------------------------------------------
# Tests: delete
# ---------------------------------------------------------------------------


class TestDeleteValidationRule:
    @pytest.mark.asyncio
    async def test_delete_no_history_succeeds(self) -> None:
        svc, repo, audit = _make_service()
        rule = await svc.create_rule(_WS_ID, project_id=None, work_item_type="f",
                                      validation_type="ac", enforcement="required", actor_id=_ACTOR_ID)

        await svc.delete_rule(_WS_ID, rule.id, _ACTOR_ID)
        assert rule.id not in repo._by_id
        assert any(e["action"] == "validation_rule_deleted" for e in audit.events)

    @pytest.mark.asyncio
    async def test_delete_with_history_raises_409(self) -> None:
        svc, repo, _ = _make_service()
        rule = await svc.create_rule(_WS_ID, project_id=None, work_item_type="f",
                                      validation_type="ac", enforcement="required", actor_id=_ACTOR_ID)
        repo._history.add(rule.id)

        with pytest.raises(RuleHasHistoryError):
            await svc.delete_rule(_WS_ID, rule.id, _ACTOR_ID)

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_404(self) -> None:
        svc, _, _ = _make_service()
        with pytest.raises(ValidationRuleNotFoundError):
            await svc.delete_rule(_WS_ID, uuid4(), _ACTOR_ID)


# ---------------------------------------------------------------------------
# Tests: precedence annotation
# ---------------------------------------------------------------------------


class TestPrecedenceAnnotation:
    def test_project_rule_supersedes_workspace_rule(self) -> None:
        ws_rule = ValidationRule.create(
            workspace_id=_WS_ID, project_id=None, work_item_type="f",
            validation_type="ac", enforcement="recommended", created_by=_ACTOR_ID,
        )
        proj_rule = ValidationRule.create(
            workspace_id=_WS_ID, project_id=_PROJ_ID, work_item_type="f",
            validation_type="ac", enforcement="required", created_by=_ACTOR_ID,
        )

        annotated = _annotate_precedence([ws_rule, proj_rule])
        ws = next(r for r in annotated if r.project_id is None)
        proj = next(r for r in annotated if r.project_id is not None)

        assert proj.effective is True
        assert ws.effective is False
        assert ws.superseded_by == proj.id

    def test_blocked_override_always_effective(self) -> None:
        ws_rule = ValidationRule.create(
            workspace_id=_WS_ID, project_id=None, work_item_type="f",
            validation_type="ac", enforcement="blocked_override", created_by=_ACTOR_ID,
        )
        proj_rule = ValidationRule.create(
            workspace_id=_WS_ID, project_id=_PROJ_ID, work_item_type="f",
            validation_type="ac", enforcement="required", created_by=_ACTOR_ID,
        )

        annotated = _annotate_precedence([ws_rule, proj_rule])
        ws = next(r for r in annotated if r.project_id is None)
        assert ws.effective is True

    def test_empty_returns_empty(self) -> None:
        assert _annotate_precedence([]) == []

    def test_no_project_rules_workspace_rule_effective(self) -> None:
        ws_rule = ValidationRule.create(
            workspace_id=_WS_ID, project_id=None, work_item_type="f",
            validation_type="ac", enforcement="required", created_by=_ACTOR_ID,
        )
        annotated = _annotate_precedence([ws_rule])
        assert annotated[0].effective is True
        assert annotated[0].superseded_by is None
