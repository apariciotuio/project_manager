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


# ---------------------------------------------------------------------------
# EP-25 — technical_approach coverage
# ---------------------------------------------------------------------------


from app.domain.models.section_type import SectionType


@pytest.mark.parametrize("wit", list(WorkItemType))
def test_every_type_has_technical_approach_section(wit: WorkItemType) -> None:
    """technical_approach was declared in the enum but never wired into any
    catalog entry. EP-25 adds it to every type. Bug requires it; all others
    are optional (documenting HOW the work will be done)."""
    cfg = catalog_for(wit)
    types = {c.section_type for c in cfg}
    assert SectionType.TECHNICAL_APPROACH in types, (
        f"{wit.value} is missing technical_approach section"
    )


def test_bug_technical_approach_is_required() -> None:
    """Bug requires technical_approach — a bug without a known fix approach
    cannot reach ready state (EP-25 decision)."""
    cfg = catalog_for(WorkItemType.BUG)
    entry = next(c for c in cfg if c.section_type is SectionType.TECHNICAL_APPROACH)
    assert entry.required is True


@pytest.mark.parametrize(
    "wit",
    [t for t in WorkItemType if t is not WorkItemType.BUG],
)
def test_non_bug_technical_approach_is_optional(wit: WorkItemType) -> None:
    cfg = catalog_for(wit)
    entry = next(c for c in cfg if c.section_type is SectionType.TECHNICAL_APPROACH)
    assert entry.required is False, (
        f"{wit.value} should have technical_approach as optional"
    )
