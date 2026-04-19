"""EP-22 v2 — Unit tests for MorpheoResponse Pydantic models and parse_and_filter_envelope.

RED phase: all tests must FAIL before the module exists.
"""
from __future__ import annotations

import json


class TestMorpheoResponseParsing:
    """Round-trip parse/serialize for each of the 4 kinds."""

    def test_question_round_trip(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "question",
            "message": "What is the target user?",
            "clarifications": [{"field": "target_user", "question": "B2C o B2B?"}],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "question"
        assert result["message"] == "What is the target user?"
        assert result["clarifications"][0]["field"] == "target_user"
        assert warnings == []

    def test_section_suggestion_round_trip(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "Here are suggestions",
            "suggested_sections": [
                {
                    "section_type": "objectives",
                    "proposed_content": "Improve onboarding",
                    "rationale": "Low completion rate",
                }
            ],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "section_suggestion"
        assert result["suggested_sections"][0]["section_type"] == "objectives"
        assert warnings == []

    def test_po_review_round_trip(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "po_review",
            "message": "Review complete",
            "po_review": {
                "score": 75,
                "verdict": "needs_work",
                "agents_consulted": ["product", "architect"],
                "per_dimension": [
                    {
                        "dimension": "product",
                        "score": 70,
                        "verdict": "needs_work",
                        "findings": [
                            {
                                "severity": "high",
                                "title": "Missing metrics",
                                "description": "No success metrics defined",
                            }
                        ],
                        "missing_info": [{"field": "success_metric", "question": "How measured?"}],
                    }
                ],
                "action_items": [
                    {
                        "priority": "critical",
                        "title": "Add metrics",
                        "description": "Define success metrics",
                        "owner": "PO",
                    }
                ],
            },
            "comments": ["Good overall structure"],
            "clarifications": [{"field": "rollout_plan", "question": "When?"}],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "po_review"
        assert result["po_review"]["score"] == 75
        assert result["po_review"]["verdict"] == "needs_work"
        assert warnings == []

    def test_error_round_trip(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "error",
            "message": "The system could not produce a valid structured response.",
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "error"
        assert "message" in result
        assert warnings == []


class TestCatalogFiltering:
    """section_type catalog drop and overflow tests."""

    def test_invalid_section_type_dropped_with_warning(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": [
                {"section_type": "objectives", "proposed_content": "valid"},
                {"section_type": "not_in_catalog", "proposed_content": "invalid"},
            ],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "section_suggestion"
        assert len(result["suggested_sections"]) == 1
        assert result["suggested_sections"][0]["section_type"] == "objectives"
        assert len(warnings) == 1
        # Warning must not contain raw input values (SEC-LOG-001)
        assert "not_in_catalog" not in warnings[0]
        assert "invalid" not in warnings[0]

    def test_overflow_cap_25_items_max(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        sections = [
            {"section_type": "objectives", "proposed_content": f"content {i}"}
            for i in range(26)
        ]
        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": sections,
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert len(result["suggested_sections"]) == 25
        assert any("overflow" in w or "cap" in w or "dropped" in w for w in warnings)

    def test_all_items_invalid_downgrades_to_question(self) -> None:
        """All items outside catalog → kind downgraded to question."""
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "Here are suggestions",
            "suggested_sections": [
                {"section_type": "not_real", "proposed_content": "content"},
                {"section_type": "also_fake", "proposed_content": "content2"},
            ],
            "clarifications": [{"field": "f", "question": "q"}],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "question"
        assert result["message"] == "Here are suggestions"
        assert result["clarifications"] == [{"field": "f", "question": "q"}]
        assert len(warnings) >= 1


class TestItemLevelValidation:
    """Individual item validation failures."""

    def test_empty_proposed_content_dropped(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": [
                {"section_type": "objectives", "proposed_content": ""},  # empty → invalid
                {"section_type": "scope", "proposed_content": "valid content"},
            ],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert len(result["suggested_sections"]) == 1
        assert result["suggested_sections"][0]["section_type"] == "scope"
        assert len(warnings) >= 1

    def test_over_length_proposed_content_dropped(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": [
                {
                    "section_type": "objectives",
                    "proposed_content": "x" * 20_481,  # over 20KB cap
                },
                {"section_type": "scope", "proposed_content": "valid"},
            ],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert len(result["suggested_sections"]) == 1
        assert result["suggested_sections"][0]["section_type"] == "scope"

    def test_missing_required_field_dropped(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": [
                {"section_type": "objectives"},  # missing proposed_content
                {"section_type": "scope", "proposed_content": "valid"},
            ],
        })
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert len(result["suggested_sections"]) == 1
        assert result["suggested_sections"][0]["section_type"] == "scope"


class TestEnvelopeErrors:
    """Malformed JSON and invalid shape handling."""

    def test_malformed_json_returns_error_envelope(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        result_json, warnings = parse_and_filter_envelope("{not valid json")
        result = json.loads(result_json)
        assert result["kind"] == "error"
        assert result["message"] == "malformed_response"
        assert len(warnings) >= 1

    def test_invalid_shape_missing_required_field_returns_error(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        # Valid JSON but missing required 'message' for kind=question
        raw = json.dumps({"kind": "question"})
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "error"
        assert result["message"] == "invalid_response_shape"
        assert len(warnings) >= 1

    def test_invalid_shape_unknown_kind_returns_error(self) -> None:
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({"kind": "unknown_kind", "message": "test"})
        result_json, warnings = parse_and_filter_envelope(raw)
        result = json.loads(result_json)
        assert result["kind"] == "error"
        assert result["message"] == "invalid_response_shape"


class TestLogSanitization:
    """Warn messages must not contain raw input values (SEC-LOG-001)."""

    def test_warning_contains_no_raw_section_type(self) -> None:
        """The raw section_type value must NOT appear in warnings."""
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": [
                {
                    "section_type": "SECRET_CATALOG_VALUE_XYZ",
                    "proposed_content": "SECRET_CONTENT_VALUE_ABC",
                }
            ],
        })
        _, warnings = parse_and_filter_envelope(raw)
        for w in warnings:
            assert "SECRET_CATALOG_VALUE_XYZ" not in w
            assert "SECRET_CONTENT_VALUE_ABC" not in w

    def test_warning_contains_no_raw_content(self) -> None:
        """Invalid content values must not leak into warning strings."""
        from app.presentation.schemas.morpheo_response import parse_and_filter_envelope

        long_pii_content = "SENSITIVE_PII_DATA " * 2000
        raw = json.dumps({
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": [
                {
                    "section_type": "objectives",
                    "proposed_content": long_pii_content,  # too long → dropped
                }
            ],
        })
        _, warnings = parse_and_filter_envelope(raw)
        for w in warnings:
            assert "SENSITIVE_PII_DATA" not in w
