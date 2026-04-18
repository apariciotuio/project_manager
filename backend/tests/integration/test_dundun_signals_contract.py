"""EP-22 — Contract test: ConversationSignalsWire vs Dundun's ConversationSignals.

Guards against schema drift between our wire schema and Dundun's entity.

State as of EP-22 implementation:
- Dundun's ConversationSignals only has `conversation_ended` (no suggested_sections yet).
- Our ConversationSignalsWire extends it with `suggested_sections`.
- Dundun PR #1 (adding suggested_sections) is pending cross-repo.

This test verifies:
1. All fields in Dundun's ConversationSignals are accepted by our ConversationSignalsWire.
2. Our ConversationSignalsWire defaults produce valid output even when Dundun sends minimal signals.
3. When Dundun adds `suggested_sections` (after PR #1), our schema accepts it without breaking.

Does NOT require Dundun to be installed as a package dependency.
Uses a direct import from the sibling repo at the known path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_DUNDUN_CALLBACK_PATH = Path(
    "/home/david/Workspace_Tuio/agents_workspace/dundun/src/dundun/temporal/shared/entities/callback.py"
)

pytestmark = pytest.mark.skipif(
    not _DUNDUN_CALLBACK_PATH.exists(),
    reason="Dundun repo not available at expected path",
)


def _load_dundun_callback():
    """Dynamically load Dundun's callback.py without requiring it as an installed package."""
    spec = importlib.util.spec_from_file_location("dundun_callback", _DUNDUN_CALLBACK_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class TestDundunSignalsContract:
    def test_dundun_signals_fields_accepted_by_wire_schema(self) -> None:
        """All fields Dundun currently emits are accepted by ConversationSignalsWire."""
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        dundun_mod = _load_dundun_callback()
        dundun_signals = dundun_mod.ConversationSignals()
        as_dict = dundun_signals.model_dump()

        wire = ConversationSignalsWire.model_validate(as_dict)
        assert wire.conversation_ended == dundun_signals.conversation_ended

    def test_minimal_dundun_signal_produces_empty_suggested_sections(self) -> None:
        """When Dundun hasn't added suggested_sections yet, our schema defaults to []."""
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        # Simulate Dundun's current minimal output
        minimal = {"conversation_ended": False}
        wire = ConversationSignalsWire.model_validate(minimal)
        assert wire.suggested_sections == []
        assert wire.conversation_ended is False

    def test_future_dundun_signals_with_suggested_sections_accepted(self) -> None:
        """After Dundun PR #1, our schema accepts the extended shape."""
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        future_payload = {
            "conversation_ended": False,
            "suggested_sections": [
                {
                    "section_type": "summary",
                    "proposed_content": "Suggested summary content.",
                    "rationale": "Based on the conversation context.",
                }
            ],
        }
        wire = ConversationSignalsWire.model_validate(future_payload)
        assert len(wire.suggested_sections) == 1
        assert wire.suggested_sections[0].section_type == "summary"

    def test_wire_schema_tolerates_unknown_fields_from_future_dundun(self) -> None:
        """extra=allow means future Dundun fields don't break our proxy."""
        from app.presentation.schemas.dundun_signals import ConversationSignalsWire

        with_future_field = {
            "conversation_ended": False,
            "suggested_sections": [],
            "future_field_added_in_dundun_v2": "some_value",
        }
        wire = ConversationSignalsWire.model_validate(with_future_field)
        assert wire.suggested_sections == []
