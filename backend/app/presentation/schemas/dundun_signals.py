"""EP-22 — Pydantic wire schemas for Dundun conversation signals.

These mirror Dundun's ConversationSignals shape and serve as the validation
gate between the Dundun WS proxy and the FE. Invalid items are dropped;
valid survivors are forwarded. Size caps protect the FE against runaway LLM
output.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

_MAX_PROPOSED_CONTENT = 20_000  # chars (~20 KB)
_MAX_RATIONALE = 2_000  # chars (~2 KB)
_MAX_SECTION_TYPE = 64
_MAX_SUGGESTED_SECTIONS = 25  # list length cap (SEC-INVAL-001)


class SuggestedSection(BaseModel):
    """One Dundun suggestion targeting a specific section type."""

    section_type: str = Field(min_length=1, max_length=_MAX_SECTION_TYPE)
    proposed_content: str = Field(min_length=1, max_length=_MAX_PROPOSED_CONTENT)
    rationale: str = Field(default="", max_length=_MAX_RATIONALE)

    @field_validator("section_type")
    @classmethod
    def _normalise_type(cls, v: str) -> str:
        normalised = v.strip().lower()
        if not normalised:
            raise ValueError("section_type must not be empty after stripping whitespace")
        return normalised


class ConversationSignalsWire(BaseModel):
    """What we forward to the FE. Superset of Dundun's ConversationSignals.

    extra="allow" tolerates future fields added by Dundun without a redeploy.
    """

    conversation_ended: bool = False
    suggested_sections: list[SuggestedSection] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


_DEFAULT_SIGNALS: dict[str, Any] = {"conversation_ended": False, "suggested_sections": []}


def _safe_error_summary(exc: Exception, idx: int) -> str:
    """Compact error summary safe to log — never includes input values.

    For Pydantic ValidationError, extract only the field path + error type
    (e.g. "item[3].proposed_content: string_too_long"). For any other
    exception, record the exception class name. The raw input (which may be
    LLM-generated user-like content or PII) is never logged (SEC-LOG-001).
    """
    if isinstance(exc, ValidationError):
        parts: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            parts.append(f"{loc}:{err.get('type', 'error')}")
        detail = ",".join(parts) if parts else "validation_error"
    else:
        detail = type(exc).__name__
    return f"item[{idx}]:{detail}"


def validate_signals(raw: Any) -> dict[str, Any]:
    """Parse raw signals dict from Dundun, drop invalid items, return clean dict.

    - Individual item failures: item is dropped with a warn-level log that
      records error types + field paths only (no raw input values).
    - Over-length list: trimmed to ``_MAX_SUGGESTED_SECTIONS``; overflow
      dropped with a warn log.
    - All items invalid: returns ``{"conversation_ended": False, "suggested_sections": []}``.
    - Top-level parse failure: returns the same defaults.
    - Never raises — always returns a dict safe to forward to FE.
    """
    if not isinstance(raw, dict):
        logger.warning(
            "signals_validation_failed reason=not_a_dict type=%s; using defaults",
            type(raw).__name__,
        )
        return dict(_DEFAULT_SIGNALS)

    # Parse valid items one by one; collect failures for observability.
    raw_items: list[Any] = raw.get("suggested_sections", [])
    if not isinstance(raw_items, list):
        raw_items = []

    # SEC-INVAL-001: cap list length before we spend cycles validating items.
    overflow_dropped = 0
    if len(raw_items) > _MAX_SUGGESTED_SECTIONS:
        overflow_dropped = len(raw_items) - _MAX_SUGGESTED_SECTIONS
        raw_items = raw_items[:_MAX_SUGGESTED_SECTIONS]
        logger.warning(
            "suggested_sections_overflow received=%d cap=%d overflow_dropped=%d",
            overflow_dropped + _MAX_SUGGESTED_SECTIONS,
            _MAX_SUGGESTED_SECTIONS,
            overflow_dropped,
        )

    valid_items: list[dict[str, Any]] = []
    invalid_reasons: list[str] = []

    for idx, item in enumerate(raw_items):
        try:
            parsed = SuggestedSection.model_validate(item)
            valid_items.append(parsed.model_dump())
        except Exception as exc:  # noqa: BLE001
            # SEC-LOG-001: never embed raw Pydantic error messages (they contain
            # input values) — summarise to field path + error type only.
            invalid_reasons.append(_safe_error_summary(exc, idx))

    dropped_count = len(raw_items) - len(valid_items)
    if dropped_count > 0:
        logger.warning(
            "suggested_sections_dropped dropped_count=%d invalid_reasons=%s",
            dropped_count,
            ";".join(invalid_reasons),
        )

    # Re-validate top-level fields (conversation_ended, extra fields) safely.
    try:
        wire = ConversationSignalsWire.model_validate({**raw, "suggested_sections": valid_items})
        return wire.model_dump()
    except Exception:  # noqa: BLE001
        logger.warning(
            "signals_top_level_validation_failed; using defaults with %d valid items",
            len(valid_items),
        )
        return {**_DEFAULT_SIGNALS, "suggested_sections": valid_items}
