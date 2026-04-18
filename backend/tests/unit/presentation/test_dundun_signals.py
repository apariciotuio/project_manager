"""Unit tests for ConversationSignalsWire + SuggestedSection Pydantic models — EP-22.

8 triangulation cases covering valid, invalid, oversized, and normalisation paths.
RED phase: these tests fail before dundun_signals.py exists.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestSuggestedSection:
    def test_valid_minimal(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        s = SuggestedSection(section_type="problem_statement", proposed_content="Content here.")
        assert s.section_type == "problem_statement"
        assert s.rationale == ""

    def test_section_type_normalised_to_lowercase(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        s = SuggestedSection(section_type="  Acceptance_Criteria  ", proposed_content="x")
        assert s.section_type == "acceptance_criteria"

    def test_missing_section_type_raises(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        with pytest.raises(ValidationError):
            SuggestedSection(proposed_content="content")  # type: ignore[call-arg]

    def test_empty_proposed_content_raises(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        with pytest.raises(ValidationError):
            SuggestedSection(section_type="problem_statement", proposed_content="")

    def test_proposed_content_over_20kb_raises(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        big = "x" * 20_001
        with pytest.raises(ValidationError):
            SuggestedSection(section_type="problem_statement", proposed_content=big)

    def test_proposed_content_exactly_20kb_is_valid(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        ok = "x" * 20_000
        s = SuggestedSection(section_type="problem_statement", proposed_content=ok)
        assert len(s.proposed_content) == 20_000

    def test_rationale_over_2kb_raises(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        big_rationale = "r" * 2_001
        with pytest.raises(ValidationError):
            SuggestedSection(
                section_type="problem_statement",
                proposed_content="valid",
                rationale=big_rationale,
            )

    def test_section_type_empty_after_strip_raises(self) -> None:
        from app.presentation.schemas.dundun_signals import SuggestedSection

        with pytest.raises(ValidationError):
            SuggestedSection(section_type="   ", proposed_content="content")


class TestConversationSignalsWire:
    def test_valid_empty_signals(self) -> None:
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        sig = ConversationSignalsWire()
        assert sig.conversation_ended is False
        assert sig.suggested_sections == []

    def test_valid_with_two_suggestions(self) -> None:
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        sig = ConversationSignalsWire(
            suggested_sections=[
                {"section_type": "problem_statement", "proposed_content": "Problem."},
                {"section_type": "stakeholders", "proposed_content": "Users."},
            ]
        )
        assert len(sig.suggested_sections) == 2

    def test_unknown_extra_top_level_field_tolerated(self) -> None:
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        sig = ConversationSignalsWire.model_validate(
            {"future_field": "future_value", "suggested_sections": []}
        )
        assert sig.suggested_sections == []

    def test_conversation_ended_true(self) -> None:
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        sig = ConversationSignalsWire(conversation_ended=True, suggested_sections=[])
        assert sig.conversation_ended is True


class TestValidateSignals:
    def test_valid_signals_returned_as_dict(self) -> None:
        from app.presentation.schemas.dundun_signals import validate_signals

        raw = {
            "conversation_ended": False,
            "suggested_sections": [
                {"section_type": "problem_statement", "proposed_content": "P"}
            ],
        }
        result = validate_signals(raw)
        assert result["suggested_sections"][0]["section_type"] == "problem_statement"

    def test_invalid_item_dropped_returns_survivors(self) -> None:
        from app.presentation.schemas.dundun_signals import validate_signals

        raw = {
            "suggested_sections": [
                {"section_type": "valid_type", "proposed_content": "OK"},
                {"section_type": "", "proposed_content": "bad"},  # invalid — empty type
            ]
        }
        result = validate_signals(raw)
        assert len(result["suggested_sections"]) == 1
        assert result["suggested_sections"][0]["section_type"] == "valid_type"

    def test_all_invalid_items_returns_empty_list(self) -> None:
        from app.presentation.schemas.dundun_signals import validate_signals

        raw = {
            "suggested_sections": [
                {"section_type": "", "proposed_content": "bad"},
                {"proposed_content": "missing_type"},
            ]
        }
        result = validate_signals(raw)
        assert result["suggested_sections"] == []
        assert "suggested_sections" in result

    def test_top_level_invalid_returns_defaults(self) -> None:
        from app.presentation.schemas.dundun_signals import validate_signals

        result = validate_signals(None)  # type: ignore[arg-type]
        assert result == {"conversation_ended": False, "suggested_sections": []}

    def test_suggested_sections_always_present(self) -> None:
        from app.presentation.schemas.dundun_signals import validate_signals

        result = validate_signals({})
        assert "suggested_sections" in result
