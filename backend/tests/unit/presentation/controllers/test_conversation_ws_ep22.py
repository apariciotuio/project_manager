"""EP-22 v2 — Unit tests for WS proxy enrichment helpers.

Covers:
  Outbound (_enrich_outbound_frame):
    - message frame gets sections_snapshot as array of {section_type, content, is_empty}
    - general thread (work_item_id=None) skips enrichment
    - FE-supplied snapshot overridden by server-authoritative array
    - non-message frames forwarded verbatim

  Inbound (_enrich_inbound_frame):
    - valid section_suggestion envelope forwarded with re-serialized response string
    - invalid section_type catalog drop → item removed, remaining forwarded
    - all items invalid → kind downgraded to question
    - malformed JSON in response → replaced with error envelope
    - non-response frames forwarded verbatim
    - signals passed through verbatim (conversation_ended)
    - missing response field → frame forwarded verbatim
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4


class TestEnrichOutboundFrame:
    async def test_message_frame_gets_snapshot_as_array(self) -> None:
        from app.domain.models.section import Section
        from app.domain.models.section_type import GenerationSource, SectionType
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        work_item_id = uuid4()
        user_id = uuid4()

        sec_obj = Section(
            id=uuid4(),
            work_item_id=work_item_id,
            section_type=SectionType.OBJECTIVE,
            content="Improve onboarding",
            display_order=1,
            is_required=True,
            generation_source=GenerationSource.MANUAL,
            version=1,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            created_by=user_id,
            updated_by=user_id,
        )
        sec_empty = Section(
            id=uuid4(),
            work_item_id=work_item_id,
            section_type=SectionType.SCOPE,
            content="   ",  # whitespace only → is_empty
            display_order=2,
            is_required=False,
            generation_source=GenerationSource.MANUAL,
            version=1,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            created_by=user_id,
            updated_by=user_id,
        )

        async def _snapshot_provider(wid: object) -> list[Section] | None:
            return [sec_obj, sec_empty] if wid == work_item_id else None

        frame = {"type": "message", "content": "question"}
        result = await _enrich_outbound_frame(
            frame, work_item_id=work_item_id, snapshot_provider=_snapshot_provider
        )

        snapshot = result["context"]["sections_snapshot"]
        assert isinstance(snapshot, list)
        assert len(snapshot) == 2
        obj_item = next(s for s in snapshot if s["section_type"] == SectionType.OBJECTIVE.value)
        empty_item = next(s for s in snapshot if s["section_type"] == SectionType.SCOPE.value)
        assert obj_item["content"] == "Improve onboarding"
        assert obj_item["is_empty"] is False
        assert empty_item["is_empty"] is True

    async def test_general_thread_skips_enrichment(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        async def _snapshot_provider(_wid: object) -> None:
            return None

        frame = {"type": "message", "content": "question"}
        result = await _enrich_outbound_frame(
            frame, work_item_id=None, snapshot_provider=_snapshot_provider
        )
        assert "context" not in result or "sections_snapshot" not in result.get("context", {})

    async def test_fe_supplied_snapshot_overridden_by_server(self) -> None:
        from app.domain.models.section import Section
        from app.domain.models.section_type import GenerationSource, SectionType
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        work_item_id = uuid4()
        user_id = uuid4()
        sec = Section(
            id=uuid4(),
            work_item_id=work_item_id,
            section_type=SectionType.OBJECTIVE,
            content="server content",
            display_order=1,
            is_required=True,
            generation_source=GenerationSource.MANUAL,
            version=1,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            created_by=user_id,
            updated_by=user_id,
        )

        async def _snapshot_provider(_wid: object) -> list[Section]:
            return [sec]

        frame = {
            "type": "message",
            "content": "hi",
            "context": {"sections_snapshot": {"stale": "fe_value"}, "other": "keep"},
        }
        result = await _enrich_outbound_frame(
            frame, work_item_id=work_item_id, snapshot_provider=_snapshot_provider
        )

        snapshot = result["context"]["sections_snapshot"]
        assert isinstance(snapshot, list)
        assert snapshot[0]["section_type"] == SectionType.OBJECTIVE.value
        assert result["context"]["other"] == "keep"

    async def test_non_message_frame_returned_verbatim(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        async def _snapshot_provider(_wid: object) -> list:
            return []

        frame = {"type": "ping"}
        result = await _enrich_outbound_frame(
            frame, work_item_id=uuid4(), snapshot_provider=_snapshot_provider
        )
        assert result == frame


class TestEnrichInboundFrame:
    def test_valid_section_suggestion_forwarded(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        envelope = {
            "kind": "section_suggestion",
            "message": "Here are suggestions",
            "suggested_sections": [
                {"section_type": "objectives", "proposed_content": "Improve onboarding"},
            ],
        }
        frame = {
            "type": "response",
            "response": json.dumps(envelope),
            "signals": {"conversation_ended": False},
        }
        result = _enrich_inbound_frame(frame)
        parsed_env = json.loads(result["response"])
        assert parsed_env["kind"] == "section_suggestion"
        assert parsed_env["suggested_sections"][0]["section_type"] == "objectives"
        # signals passed through
        assert result["signals"]["conversation_ended"] is False

    def test_catalog_drop_filters_invalid_section_type(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        envelope = {
            "kind": "section_suggestion",
            "message": "suggestions",
            "suggested_sections": [
                {"section_type": "objectives", "proposed_content": "valid"},
                {"section_type": "completely_made_up_type", "proposed_content": "dropped"},
            ],
        }
        frame = {
            "type": "response",
            "response": json.dumps(envelope),
            "signals": {"conversation_ended": False},
        }
        result = _enrich_inbound_frame(frame)
        parsed_env = json.loads(result["response"])
        assert parsed_env["kind"] == "section_suggestion"
        assert len(parsed_env["suggested_sections"]) == 1
        assert parsed_env["suggested_sections"][0]["section_type"] == "objectives"

    def test_all_items_invalid_downgrades_to_question(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        envelope = {
            "kind": "section_suggestion",
            "message": "Hello",
            "suggested_sections": [
                {"section_type": "fake_type", "proposed_content": "dropped"},
            ],
            "clarifications": [{"field": "f", "question": "q"}],
        }
        frame = {
            "type": "response",
            "response": json.dumps(envelope),
            "signals": {"conversation_ended": False},
        }
        result = _enrich_inbound_frame(frame)
        parsed_env = json.loads(result["response"])
        assert parsed_env["kind"] == "question"
        assert parsed_env["message"] == "Hello"

    def test_malformed_json_replaced_with_error_envelope(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {
            "type": "response",
            "response": "{not valid json!!!",
            "signals": {"conversation_ended": False},
        }
        result = _enrich_inbound_frame(frame)
        parsed_env = json.loads(result["response"])
        assert parsed_env["kind"] == "error"
        assert parsed_env["message"] == "malformed_response"

    def test_non_response_frame_forwarded_verbatim(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {"type": "progress", "phase": "thinking", "detail": "..."}
        result = _enrich_inbound_frame(frame)
        assert result == frame

    def test_question_envelope_forwarded_unchanged(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        envelope = {
            "kind": "question",
            "message": "What is the target user?",
            "clarifications": [{"field": "user", "question": "B2C or B2B?"}],
        }
        frame = {
            "type": "response",
            "response": json.dumps(envelope),
            "signals": {"conversation_ended": False},
        }
        result = _enrich_inbound_frame(frame)
        parsed_env = json.loads(result["response"])
        assert parsed_env["kind"] == "question"

    def test_missing_response_field_forwarded_verbatim_with_warn(self) -> None:
        """Spec §Inbound step 1: missing or non-string response → forward verbatim."""
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {"type": "response", "signals": {"conversation_ended": True}}
        result = _enrich_inbound_frame(frame)
        # Frame forwarded verbatim — response key still absent
        assert "response" not in result or result.get("response") is None
        assert result["signals"]["conversation_ended"] is True
