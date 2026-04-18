"""EP-22 v2 — Pydantic models for the MorpheoResponse discriminated-union envelope.

Dundun-Morpheo returns a JSON string inside frame.response. Consumers must
double-parse: json.loads(frame["response"]) → MorpheoResponse.

The envelope is discriminated by `kind ∈ {question, section_suggestion, po_review, error}`.

Security:
  - SEC-LOG-001: warn logs never include raw input values; only field paths + error types.
  - SEC-INVAL-001: size caps prevent runaway LLM output from reaching the FE.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caps (SEC-INVAL-001)
# ---------------------------------------------------------------------------

_MAX_MESSAGE = 2_000
_MAX_SUGGESTED_SECTIONS = 25
_MAX_PROPOSED_CONTENT = 20_480  # ~20 KB
_MAX_RATIONALE = 2_048
_MAX_SECTION_TYPE = 64
_MAX_CLARIFICATIONS = 50
_MAX_CLARIFICATION_FIELD = 128
_MAX_CLARIFICATION_QUESTION = 500
_MAX_PER_DIMENSION = 16
_MAX_FINDINGS = 25
_MAX_ACTION_ITEMS = 50
_MAX_COMMENTS = 100
_MAX_MISSING_INFO = 50
_MAX_AGENTS_CONSULTED = 16

# ---------------------------------------------------------------------------
# Catalog (EP-22 valid section types)
# ---------------------------------------------------------------------------

SECTION_TYPE_CATALOG: frozenset[str] = frozenset({
    "objectives",
    "scope",
    "non_goals",
    "acceptance_criteria",
    "risks",
    "assumptions",
    "dependencies",
    "success_metrics",
    "rollout_plan",
    "open_questions",
})

_SECTION_TYPE_RE = re.compile(r"^[a-z_]+$")

# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class _Clarification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str = Field(min_length=1, max_length=_MAX_CLARIFICATION_FIELD)
    question: str = Field(min_length=1, max_length=_MAX_CLARIFICATION_QUESTION)


# ---------------------------------------------------------------------------
# kind = "question"
# ---------------------------------------------------------------------------


class MorpheoQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["question"]
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE)
    clarifications: list[_Clarification] = Field(
        default_factory=list, max_length=_MAX_CLARIFICATIONS
    )


# ---------------------------------------------------------------------------
# kind = "section_suggestion"
# ---------------------------------------------------------------------------


class _SuggestedSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    section_type: str = Field(min_length=1, max_length=_MAX_SECTION_TYPE)
    proposed_content: str = Field(min_length=1, max_length=_MAX_PROPOSED_CONTENT)
    rationale: str = Field(default="", max_length=_MAX_RATIONALE)

    @field_validator("section_type")
    @classmethod
    def _validate_section_type_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("section_type must not be blank")
        if not _SECTION_TYPE_RE.match(v):
            raise ValueError("section_type must match ^[a-z_]+$")
        return v


class MorpheoSectionSuggestion(BaseModel):
    """Parsed section_suggestion — items are filtered separately in parse_and_filter_envelope.

    No min/max on suggested_sections here — overflow capping and catalog filtering
    happen in code after initial parse so individual bad items don't reject the envelope.
    """

    model_config = ConfigDict(extra="ignore")

    kind: Literal["section_suggestion"]
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE)
    suggested_sections: list[Any] = Field(default_factory=list)
    clarifications: list[_Clarification] = Field(
        default_factory=list, max_length=_MAX_CLARIFICATIONS
    )


# ---------------------------------------------------------------------------
# kind = "po_review"
# ---------------------------------------------------------------------------


class _Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    severity: Literal["low", "medium", "high", "critical"]
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class _MissingInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str = Field(min_length=1, max_length=_MAX_CLARIFICATION_FIELD)
    question: str = Field(min_length=1, max_length=_MAX_CLARIFICATION_QUESTION)


class _PerDimension(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dimension: str = Field(min_length=1)
    score: int = Field(ge=0, le=100)
    verdict: Literal["approved", "needs_work", "rejected"]
    findings: list[_Finding] = Field(default_factory=list, max_length=_MAX_FINDINGS)
    missing_info: list[_MissingInfo] = Field(default_factory=list, max_length=_MAX_MISSING_INFO)


class _ActionItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    priority: Literal["low", "medium", "high", "critical"]
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    owner: str = Field(min_length=1)


class _PoReviewBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: int = Field(ge=0, le=100)
    verdict: Literal["approved", "needs_work", "rejected"]
    agents_consulted: list[str] = Field(default_factory=list, max_length=_MAX_AGENTS_CONSULTED)
    per_dimension: list[_PerDimension] = Field(default_factory=list, max_length=_MAX_PER_DIMENSION)
    action_items: list[_ActionItem] = Field(default_factory=list, max_length=_MAX_ACTION_ITEMS)


class MorpheoPoReview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["po_review"]
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE)
    po_review: _PoReviewBody
    comments: list[str] = Field(default_factory=list, max_length=_MAX_COMMENTS)
    clarifications: list[_Clarification] = Field(
        default_factory=list, max_length=_MAX_CLARIFICATIONS
    )


# ---------------------------------------------------------------------------
# kind = "error"
# ---------------------------------------------------------------------------


class MorpheoError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["error"]
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE)


# ---------------------------------------------------------------------------
# Discriminated union
# ---------------------------------------------------------------------------

MorpheoResponse = Annotated[
    MorpheoQuestion | MorpheoSectionSuggestion | MorpheoPoReview | MorpheoError,
    Field(discriminator="kind"),
]

# ---------------------------------------------------------------------------
# Log sanitization (SEC-LOG-001)
# ---------------------------------------------------------------------------


def _safe_validation_summary(exc: ValidationError) -> str:
    """Compact summary safe to log — field path + error type only, no raw values."""
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}:{err.get('type', 'unknown')}")
    return ",".join(parts) if parts else "validation_error"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_ERROR_MALFORMED = json.dumps({"kind": "error", "message": "malformed_response"})
_ERROR_INVALID = json.dumps({"kind": "error", "message": "invalid_response_shape"})


def parse_and_filter_envelope(raw_json_string: str) -> tuple[str, list[str]]:
    """Parse, validate, and filter a MorpheoResponse JSON string.

    Returns (re_serialized_json_string, warnings).
    The warnings list contains log-safe summaries (no raw input values).
    Never raises — always returns a valid JSON string.

    Behaviour:
    - Malformed JSON → error envelope + 1 warning.
    - Unknown/missing kind or required field → error envelope + 1 warning.
    - section_suggestion with catalog violations → items dropped + warnings.
    - All items dropped → downgraded to question (preserving message + clarifications).
    - Overflow (>25 items) → first 25 kept + 1 warning.
    """
    warnings: list[str] = []

    # Step 1: JSON parse
    try:
        parsed = json.loads(raw_json_string)
    except (json.JSONDecodeError, ValueError) as exc:
        warnings.append(f"malformed_json:{type(exc).__name__}")
        return _ERROR_MALFORMED, warnings

    # Step 2: validate discriminated union
    from pydantic import TypeAdapter  # noqa: PLC0415 — deferred per lru_cache trap pattern

    _adapter: TypeAdapter[Any] = TypeAdapter(MorpheoResponse)
    try:
        envelope = _adapter.validate_python(parsed)
    except ValidationError as exc:
        summary = _safe_validation_summary(exc)
        warnings.append(f"invalid_envelope_shape:{summary}")
        return _ERROR_INVALID, warnings

    # Step 3: section_suggestion filtering
    if isinstance(envelope, MorpheoSectionSuggestion):
        return _filter_section_suggestion(envelope, warnings)

    return envelope.model_dump_json(), warnings


def _filter_section_suggestion(
    envelope: MorpheoSectionSuggestion, warnings: list[str]
) -> tuple[str, list[str]]:
    """Apply per-item validation, overflow cap, and catalog filtering.

    Each item is validated individually with _SuggestedSection so that bad items
    are dropped without rejecting the entire envelope (SEC-INVAL-001).
    """
    raw_items: list[Any] = list(envelope.suggested_sections)

    # Overflow cap — applied before per-item validation to bound work
    if len(raw_items) > _MAX_SUGGESTED_SECTIONS:
        overflow_dropped = len(raw_items) - _MAX_SUGGESTED_SECTIONS
        raw_items = raw_items[:_MAX_SUGGESTED_SECTIONS]
        warnings.append(
            f"suggested_sections_overflow:received={overflow_dropped + _MAX_SUGGESTED_SECTIONS}"
            f",cap={_MAX_SUGGESTED_SECTIONS},overflow_dropped={overflow_dropped}"
        )

    # Per-item Pydantic validation — collect failures, log field path + error type only
    parsed_items: list[_SuggestedSection] = []
    item_invalid_count = 0
    for idx, raw_item in enumerate(raw_items):
        try:
            parsed_items.append(_SuggestedSection.model_validate(raw_item))
        except (ValidationError, Exception) as exc:  # noqa: BLE001
            # SEC-LOG-001: field path + error type only
            if isinstance(exc, ValidationError):
                summary = _safe_validation_summary(exc)
            else:
                summary = type(exc).__name__
            warnings.append(f"item_validation_failed:item[{idx}]:{summary}")
            item_invalid_count += 1

    if item_invalid_count > 0:
        logger.warning(
            "morpheo_item_validation_failed dropped_count=%d", item_invalid_count
        )

    # Catalog filter — drop items with section_type outside EP-22 allowed set
    valid_sections: list[_SuggestedSection] = []
    catalog_dropped = 0
    for idx, item in enumerate(parsed_items):
        if item.section_type not in SECTION_TYPE_CATALOG:
            # SEC-LOG-001: do NOT log the section_type value
            warnings.append(f"catalog_drop:item[{idx}]:type_outside_allowed_set")
            catalog_dropped += 1
        else:
            valid_sections.append(item)

    if catalog_dropped > 0:
        logger.warning(
            "morpheo_catalog_drop dropped_count=%d", catalog_dropped
        )

    # If all items dropped → downgrade to question preserving message + clarifications
    if not valid_sections:
        downgraded = MorpheoQuestion(
            kind="question",
            message=envelope.message,
            clarifications=envelope.clarifications,
        )
        warnings.append("section_suggestion_downgraded_to_question:all_items_filtered")
        return downgraded.model_dump_json(), warnings

    # Re-build envelope with filtered validated sections
    filtered = MorpheoSectionSuggestion(
        kind="section_suggestion",
        message=envelope.message,
        suggested_sections=valid_sections,
        clarifications=envelope.clarifications,
    )
    return filtered.model_dump_json(), warnings
