"""EP-12 — request schemas must reject unknown fields (extra='forbid').

Strict input validation. If a client sends a typo or an attacker-controlled
extra field, we reject the whole request rather than silently ignoring it.

Applies to FE-originated request schemas only. External webhook payloads
(Dundun, Puppet callbacks) are intentionally lenient (extra='ignore') so a
schema addition upstream doesn't break our callback handler — those
endpoints trust their HMAC auth + idempotency gates instead.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestFrontendRequestSchemasForbidExtra:
    """Every request schema that comes from our FE rejects unknown fields."""

    def test_create_thread_request_rejects_extra(self) -> None:
        from app.presentation.schemas.thread_schemas import CreateThreadRequest

        with pytest.raises(ValidationError):
            CreateThreadRequest.model_validate({"foo": "bar"})

    def test_generate_suggestions_request_rejects_extra(self) -> None:
        from app.presentation.schemas.suggestion_schemas import GenerateSuggestionsRequest

        with pytest.raises(ValidationError):
            GenerateSuggestionsRequest.model_validate({"malicious_field": 1})

    def test_patch_suggestion_status_request_rejects_extra(self) -> None:
        from app.presentation.schemas.suggestion_schemas import PatchSuggestionStatusRequest

        with pytest.raises(ValidationError):
            PatchSuggestionStatusRequest.model_validate(
                {"status": "accepted", "extra": "drop-me"}
            )

    def test_puppet_search_request_rejects_extra(self) -> None:
        from app.presentation.schemas.puppet_schemas import PuppetSearchRequest

        with pytest.raises(ValidationError):
            PuppetSearchRequest.model_validate({"query": "q", "unknown": 42})

    def test_work_item_create_request_rejects_extra(self) -> None:
        """Spot-check an already-strict schema so this test guards regression."""
        from app.presentation.schemas.work_item_schemas import WorkItemCreateRequest

        with pytest.raises(ValidationError):
            WorkItemCreateRequest.model_validate(
                {"title": "t", "original_input": "x", "injected": "y"}
            )

    def test_template_create_request_rejects_extra(self) -> None:
        from app.presentation.schemas.template_schemas import CreateTemplateRequest

        with pytest.raises(ValidationError):
            CreateTemplateRequest.model_validate({"name": "n", "rogue": 1})


class TestWebhookSchemasIgnoreExtra:
    """External webhook payloads accept unknown fields (forward-compat)."""

    def test_puppet_callback_ignores_extra(self) -> None:
        from uuid import uuid4

        from app.presentation.schemas.puppet_schemas import PuppetCallbackRequest

        parsed = PuppetCallbackRequest.model_validate(
            {
                "ingest_request_id": str(uuid4()),
                "status": "succeeded",
                "puppet_doc_id": "doc-1",
                "future_field_from_puppet": "ok",
            }
        )
        assert parsed.status == "succeeded"

    def test_dundun_callback_ignores_extra(self) -> None:
        from app.presentation.schemas.dundun_callback_schemas import DundunCallbackRequest

        parsed = DundunCallbackRequest.model_validate(
            {
                "agent": "wm_suggestion_agent",
                "request_id": "req-1",
                "status": "success",
                "future_dundun_field": "ok",
            }
        )
        assert parsed.agent == "wm_suggestion_agent"
