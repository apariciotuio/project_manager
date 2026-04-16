"""EP-04 Phase 2 — Validator entity."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.validator import Validator, ValidatorStatus


def _make() -> Validator:
    return Validator.create(work_item_id=uuid4(), role="product_owner", assigned_by=uuid4())


def test_create_starts_pending() -> None:
    v = _make()
    assert v.status is ValidatorStatus.PENDING
    assert v.responded_at is None


def test_respond_sets_responded_at() -> None:
    v = _make()
    v.respond(ValidatorStatus.APPROVED)
    assert v.status is ValidatorStatus.APPROVED
    assert v.responded_at is not None


def test_cannot_respond_twice() -> None:
    v = _make()
    v.respond(ValidatorStatus.APPROVED)
    with pytest.raises(ValueError):
        v.respond(ValidatorStatus.DECLINED)


def test_cannot_transition_back_to_pending() -> None:
    v = _make()
    with pytest.raises(ValueError):
        v.respond(ValidatorStatus.PENDING)
