"""EP-04 Phase 2 — catalog invariants."""
from __future__ import annotations

import pytest

from app.domain.models.section_catalog import SECTION_CATALOG, catalog_for
from app.domain.value_objects.work_item_type import WorkItemType


@pytest.mark.parametrize("wit", list(WorkItemType))
def test_every_type_has_a_catalog(wit: WorkItemType) -> None:
    cfg = catalog_for(wit)
    assert cfg, f"{wit.value} has no section catalog"


@pytest.mark.parametrize("wit", list(WorkItemType))
def test_every_type_has_at_least_one_required_section(wit: WorkItemType) -> None:
    cfg = catalog_for(wit)
    assert any(c.required for c in cfg), f"{wit.value} has no required sections"


@pytest.mark.parametrize("wit", list(WorkItemType))
def test_no_duplicate_section_types_per_type(wit: WorkItemType) -> None:
    cfg = catalog_for(wit)
    types = [c.section_type for c in cfg]
    assert len(types) == len(set(types)), f"{wit.value} has duplicate section_types"


@pytest.mark.parametrize("wit", list(WorkItemType))
def test_display_orders_are_unique_within_type(wit: WorkItemType) -> None:
    cfg = catalog_for(wit)
    orders = [c.display_order for c in cfg]
    assert len(orders) == len(set(orders)), f"{wit.value} has duplicate display_order values"


def test_catalog_covers_all_eight_types() -> None:
    assert set(SECTION_CATALOG.keys()) == set(WorkItemType)
