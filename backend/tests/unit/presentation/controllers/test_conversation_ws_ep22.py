"""Unit tests for EP-22 WS proxy enrichment helpers — outbound snapshot + inbound signals.

These are controller-layer unit tests using extracted helper functions,
not full integration tests (those are in tests/integration/).

Covers:
  - _enrich_outbound_frame: attaches snapshot when thread has work_item_id
  - _enrich_outbound_frame: skips general threads (work_item_id=None)
  - _enrich_outbound_frame: overrides FE-supplied snapshot with server value
  - _enrich_outbound_frame: only enriches type==message frames
  - _enrich_inbound_frame: passes valid response frames through with signals
  - _enrich_inbound_frame: drops invalid suggested_section items
  - _enrich_inbound_frame: all-invalid → empty suggested_sections list (present)
  - _enrich_inbound_frame: non-response frames forwarded verbatim
"""
from __future__ import annotations

from uuid import uuid4


class TestEnrichOutboundFrame:
    async def test_message_frame_gets_snapshot_attached(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        work_item_id = uuid4()
        snapshot = {"summary": "hello", "context": "world"}

        async def _snapshot_provider(wid):
            return snapshot if wid == work_item_id else None

        frame = {"type": "message", "content": "question"}
        result = await _enrich_outbound_frame(
            frame, work_item_id=work_item_id, snapshot_provider=_snapshot_provider
        )

        assert result["context"]["sections_snapshot"] == snapshot

    async def test_general_thread_skips_enrichment(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        async def _snapshot_provider(_wid):
            return None

        frame = {"type": "message", "content": "question"}
        result = await _enrich_outbound_frame(
            frame, work_item_id=None, snapshot_provider=_snapshot_provider
        )
        # No context.sections_snapshot added for general threads
        assert "context" not in result or "sections_snapshot" not in result.get("context", {})

    async def test_fe_supplied_snapshot_overridden_by_server(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        work_item_id = uuid4()
        server_snapshot = {"summary": "server_value"}

        async def _snapshot_provider(_wid):
            return server_snapshot

        # FE sends its own snapshot
        frame = {
            "type": "message",
            "content": "hi",
            "context": {"sections_snapshot": {"summary": "fe_value"}, "other": "keep"},
        }
        result = await _enrich_outbound_frame(
            frame, work_item_id=work_item_id, snapshot_provider=_snapshot_provider
        )

        assert result["context"]["sections_snapshot"] == server_snapshot
        assert result["context"]["other"] == "keep"  # other FE context preserved

    async def test_non_message_frame_returned_verbatim(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_outbound_frame,
        )

        async def _snapshot_provider(_wid):
            return {"summary": "x"}

        frame = {"type": "ping"}
        result = await _enrich_outbound_frame(
            frame, work_item_id=uuid4(), snapshot_provider=_snapshot_provider
        )
        assert result == frame


class TestEnrichInboundFrame:
    def test_valid_response_frame_forwarded_with_signals(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {
            "type": "response",
            "response": "Here is my answer.",
            "signals": {
                "conversation_ended": False,
                "suggested_sections": [
                    {"section_type": "summary", "proposed_content": "Suggested summary."}
                ],
            },
        }
        result = _enrich_inbound_frame(frame)
        assert result["signals"]["suggested_sections"][0]["section_type"] == "summary"

    def test_invalid_suggested_section_dropped(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {
            "type": "response",
            "response": "text",
            "signals": {
                "suggested_sections": [
                    {"section_type": "summary", "proposed_content": "valid"},
                    {"section_type": "", "proposed_content": "invalid empty type"},
                ]
            },
        }
        result = _enrich_inbound_frame(frame)
        assert len(result["signals"]["suggested_sections"]) == 1
        assert result["signals"]["suggested_sections"][0]["section_type"] == "summary"

    def test_all_invalid_items_yields_empty_list(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {
            "type": "response",
            "response": "text",
            "signals": {
                "suggested_sections": [
                    {"section_type": "", "proposed_content": "bad"},
                    {"proposed_content": "missing type"},
                ]
            },
        }
        result = _enrich_inbound_frame(frame)
        assert result["signals"]["suggested_sections"] == []
        assert "suggested_sections" in result["signals"]

    def test_response_without_signals_gets_defaults(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {"type": "response", "response": "text"}
        result = _enrich_inbound_frame(frame)
        assert result["signals"]["suggested_sections"] == []
        assert result["signals"]["conversation_ended"] is False

    def test_non_response_frame_forwarded_verbatim(self) -> None:
        from app.presentation.controllers.conversation_controller import (
            _enrich_inbound_frame,
        )

        frame = {"type": "progress", "phase": "thinking", "detail": "..."}
        result = _enrich_inbound_frame(frame)
        assert result == frame
