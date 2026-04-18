"""EP-09 — SavedSearch."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.saved_search import SavedSearch


def test_create_default_empty_params() -> None:
    s = SavedSearch.create(user_id=uuid4(), workspace_id=uuid4(), name="mine")
    assert s.query_params == {}


def test_create_strips_name() -> None:
    s = SavedSearch.create(user_id=uuid4(), workspace_id=uuid4(), name="  x ")
    assert s.name == "x"


def test_empty_name_rejected() -> None:
    with pytest.raises(ValueError):
        SavedSearch.create(user_id=uuid4(), workspace_id=uuid4(), name="  ")


def test_long_name_rejected() -> None:
    with pytest.raises(ValueError):
        SavedSearch.create(user_id=uuid4(), workspace_id=uuid4(), name="x" * 256)
