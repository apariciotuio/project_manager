"""EP-04 — SectionType enum.

Every work_item_sections row's section_type must match one of these values.
Enforced at the application layer; the DB column is VARCHAR(64) with no CHECK
constraint (app-layer catalog is the source of truth — see section_catalog.py).
"""
from __future__ import annotations

from enum import StrEnum


class SectionType(StrEnum):
    SUMMARY = "summary"
    CONTEXT = "context"
    OBJECTIVE = "objective"
    SCOPE = "scope"
    STEPS_TO_REPRODUCE = "steps_to_reproduce"
    EXPECTED_BEHAVIOR = "expected_behavior"
    ACTUAL_BEHAVIOR = "actual_behavior"
    ENVIRONMENT = "environment"
    IMPACT = "impact"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    DEPENDENCIES = "dependencies"
    RISKS = "risks"
    BREAKDOWN = "breakdown"
    NOTES = "notes"
    DEFINITION_OF_DONE = "definition_of_done"
    HYPOTHESIS = "hypothesis"
    SUCCESS_METRICS = "success_metrics"
    TECHNICAL_APPROACH = "technical_approach"


class GenerationSource(StrEnum):
    LLM = "llm"
    MANUAL = "manual"
    REVERT = "revert"
