"""EP-04 — Section catalog per WorkItemType.

Single source of truth for which sections every work item type must have.

Bootstrap pattern:
  create_sections_from_catalog(work_item_id, work_item_type, user_id) returns
  the default set of Section rows for a given type. SectionRepository persists
  them on work item creation.

Only section types actually needed per WorkItemType are declared. A section_type
absent from a type's list is not applicable — CompletenessService skips it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.section_type import SectionType
from app.domain.value_objects.work_item_type import WorkItemType


@dataclass(frozen=True)
class SectionConfig:
    section_type: SectionType
    display_order: int
    required: bool


SECTION_CATALOG: dict[WorkItemType, list[SectionConfig]] = {
    WorkItemType.BUG: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.STEPS_TO_REPRODUCE, 2, True),
        SectionConfig(SectionType.EXPECTED_BEHAVIOR, 3, True),
        SectionConfig(SectionType.ACTUAL_BEHAVIOR, 4, True),
        SectionConfig(SectionType.ENVIRONMENT, 5, False),
        SectionConfig(SectionType.IMPACT, 6, False),
        SectionConfig(SectionType.ACCEPTANCE_CRITERIA, 7, True),
        SectionConfig(SectionType.NOTES, 8, False),
    ],
    WorkItemType.REQUIREMENT: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.CONTEXT, 2, True),
        SectionConfig(SectionType.OBJECTIVE, 3, True),
        SectionConfig(SectionType.ACCEPTANCE_CRITERIA, 4, True),
        SectionConfig(SectionType.DEFINITION_OF_DONE, 5, False),
        SectionConfig(SectionType.DEPENDENCIES, 6, False),
        SectionConfig(SectionType.RISKS, 7, False),
        SectionConfig(SectionType.NOTES, 8, False),
    ],
    WorkItemType.ENHANCEMENT: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.CONTEXT, 2, True),
        SectionConfig(SectionType.OBJECTIVE, 3, True),
        SectionConfig(SectionType.ACCEPTANCE_CRITERIA, 4, True),
        SectionConfig(SectionType.IMPACT, 5, False),
        SectionConfig(SectionType.NOTES, 6, False),
    ],
    WorkItemType.IDEA: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.CONTEXT, 2, True),
        SectionConfig(SectionType.HYPOTHESIS, 3, False),
        SectionConfig(SectionType.SUCCESS_METRICS, 4, False),
        SectionConfig(SectionType.NOTES, 5, False),
    ],
    WorkItemType.TASK: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.OBJECTIVE, 2, False),
        SectionConfig(SectionType.DEFINITION_OF_DONE, 3, True),
        SectionConfig(SectionType.DEPENDENCIES, 4, False),
        SectionConfig(SectionType.NOTES, 5, False),
    ],
    WorkItemType.SPIKE: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.HYPOTHESIS, 2, True),
        SectionConfig(SectionType.SCOPE, 3, True),
        SectionConfig(SectionType.SUCCESS_METRICS, 4, False),
        SectionConfig(SectionType.NOTES, 5, False),
    ],
    WorkItemType.INITIATIVE: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.OBJECTIVE, 2, True),
        SectionConfig(SectionType.SCOPE, 3, True),
        SectionConfig(SectionType.BREAKDOWN, 4, True),
        SectionConfig(SectionType.DEPENDENCIES, 5, False),
        SectionConfig(SectionType.RISKS, 6, False),
        SectionConfig(SectionType.SUCCESS_METRICS, 7, False),
    ],
    WorkItemType.BUSINESS_CHANGE: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.CONTEXT, 2, True),
        SectionConfig(SectionType.OBJECTIVE, 3, True),
        SectionConfig(SectionType.SCOPE, 4, True),
        SectionConfig(SectionType.IMPACT, 5, True),
        SectionConfig(SectionType.DEPENDENCIES, 6, False),
        SectionConfig(SectionType.RISKS, 7, False),
    ],
    # EP-14 hierarchy types
    WorkItemType.MILESTONE: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.OBJECTIVE, 2, True),
        SectionConfig(SectionType.SCOPE, 3, True),
        SectionConfig(SectionType.BREAKDOWN, 4, True),
        SectionConfig(SectionType.SUCCESS_METRICS, 5, False),
        SectionConfig(SectionType.RISKS, 6, False),
    ],
    WorkItemType.STORY: [
        SectionConfig(SectionType.SUMMARY, 1, True),
        SectionConfig(SectionType.CONTEXT, 2, True),
        SectionConfig(SectionType.ACCEPTANCE_CRITERIA, 3, True),
        SectionConfig(SectionType.DEFINITION_OF_DONE, 4, False),
        SectionConfig(SectionType.DEPENDENCIES, 5, False),
        SectionConfig(SectionType.NOTES, 6, False),
    ],
}


def catalog_for(work_item_type: WorkItemType) -> list[SectionConfig]:
    """Return catalog list for a type. Raises KeyError if misconfigured."""
    return SECTION_CATALOG[work_item_type]
