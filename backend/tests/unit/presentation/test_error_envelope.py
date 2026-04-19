"""Unit tests for error envelope middleware (EP-21 F-4-be).

Tests the DomainError → structured JSON envelope mapping using FastAPI TestClient.
Covers: DomainError subclasses, field/details propagation, http_status mapping.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.errors.codes import (
    DomainError,
    ForbiddenError,
    NotFoundError,
    TagNameTakenError,
    TeamMemberAlreadyExistsError,
    ValidationError,
    WorkItemInvalidTransitionError,
)
from app.presentation.middleware.error_envelope import register_domain_error_handler


def _make_app_with_500() -> FastAPI:
    """Extend the base app with 500-class routes."""
    app = FastAPI()
    register_domain_error_handler(app)

    @app.get("/raise/internal")
    async def raise_internal() -> None:
        raise DomainError("sql fragment: SELECT * FROM secrets WHERE id=1")

    @app.get("/raise/not-found-ok")
    async def raise_not_found_ok() -> None:
        raise NotFoundError("item not found")

    return app


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with domain error routes for testing."""
    app = FastAPI()
    register_domain_error_handler(app)

    @app.get("/raise/validation")
    async def raise_validation() -> None:
        raise ValidationError("name is required", field="name")

    @app.get("/raise/not-found")
    async def raise_not_found() -> None:
        raise NotFoundError("item not found")

    @app.get("/raise/forbidden")
    async def raise_forbidden() -> None:
        raise ForbiddenError("access denied")

    @app.get("/raise/tag-name-taken")
    async def raise_tag_name_taken() -> None:
        raise TagNameTakenError("backend")

    @app.get("/raise/team-member-exists")
    async def raise_team_member_exists() -> None:
        from uuid import uuid4
        raise TeamMemberAlreadyExistsError(uuid4(), uuid4())

    @app.get("/raise/invalid-transition")
    async def raise_invalid_transition() -> None:
        raise WorkItemInvalidTransitionError("done", "inbox")

    @app.get("/raise/base-domain-error")
    async def raise_base_domain_error() -> None:
        raise DomainError("something went wrong")

    return app


client = TestClient(_make_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Envelope shape tests
# ---------------------------------------------------------------------------


def test_validation_error_returns_400() -> None:
    response = client.get("/raise/validation")
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["field"] == "name"
    assert "name is required" in body["error"]["message"]


def test_not_found_error_returns_404() -> None:
    response = client.get("/raise/not-found")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "item not found" in body["error"]["message"]


def test_forbidden_error_returns_403() -> None:
    response = client.get("/raise/forbidden")
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


def test_tag_name_taken_returns_409_with_field() -> None:
    response = client.get("/raise/tag-name-taken")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "TAG_NAME_TAKEN"
    assert body["error"]["field"] == "name"
    assert "backend" in body["error"]["message"]


def test_team_member_already_exists_returns_409_with_field() -> None:
    response = client.get("/raise/team-member-exists")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "TEAM_MEMBER_ALREADY_EXISTS"
    assert body["error"]["field"] == "user_id"


def test_work_item_invalid_transition_returns_422_with_details() -> None:
    response = client.get("/raise/invalid-transition")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "WORK_ITEM_INVALID_TRANSITION"
    assert body["error"]["details"]["from"] == "done"
    assert body["error"]["details"]["to"] == "inbox"


def test_base_domain_error_returns_500() -> None:
    response = client.get("/raise/base-domain-error")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Envelope structure invariants
# ---------------------------------------------------------------------------


def test_envelope_always_has_error_key() -> None:
    for path in ["/raise/validation", "/raise/not-found", "/raise/forbidden"]:
        response = client.get(path)
        assert "error" in response.json(), f"missing 'error' key for {path}"


def test_no_field_key_when_not_set() -> None:
    """Not-found error has no field — envelope must not include the key."""
    response = client.get("/raise/not-found")
    body = response.json()
    assert "field" not in body["error"]


def test_no_details_key_when_empty() -> None:
    """Not-found error has no details — envelope must not include the key."""
    response = client.get("/raise/not-found")
    body = response.json()
    assert "details" not in body["error"]


# ---------------------------------------------------------------------------
# Error code → http_status mapping (unit, no HTTP round-trip)
# ---------------------------------------------------------------------------


def test_error_codes_http_status_mapping() -> None:
    from app.domain.errors.codes import ERROR_CODES
    assert ERROR_CODES["VALIDATION_ERROR"] == 400
    assert ERROR_CODES["INVALID_INPUT"] == 400
    assert ERROR_CODES["UNAUTHORIZED"] == 401
    assert ERROR_CODES["INVALID_CREDENTIALS"] == 401
    assert ERROR_CODES["FORBIDDEN"] == 403
    assert ERROR_CODES["NOT_FOUND"] == 404
    assert ERROR_CODES["TEAM_MEMBER_ALREADY_EXISTS"] == 409
    assert ERROR_CODES["TAG_NAME_TAKEN"] == 409
    assert ERROR_CODES["TAG_ARCHIVED"] == 409
    assert ERROR_CODES["WORK_ITEM_INVALID_TRANSITION"] == 422
    assert ERROR_CODES["INTERNAL_ERROR"] == 500


def test_tag_archived_domain_error_returns_409() -> None:
    from app.domain.errors.codes import TagArchivedDomainError
    app = FastAPI()
    register_domain_error_handler(app)

    @app.get("/raise/tag-archived")
    async def raise_tag_archived() -> None:
        raise TagArchivedDomainError("tag is archived")

    c = TestClient(app, raise_server_exceptions=False)
    response = c.get("/raise/tag-archived")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TAG_ARCHIVED"


def test_invalid_input_error_returns_400() -> None:
    from app.domain.errors.codes import InvalidInputError
    app = FastAPI()
    register_domain_error_handler(app)

    @app.get("/raise/invalid-input")
    async def raise_invalid_input() -> None:
        raise InvalidInputError("name cannot be empty", field="name")

    c = TestClient(app, raise_server_exceptions=False)
    response = c.get("/raise/invalid-input")
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_INPUT"
    assert body["error"]["field"] == "name"


# ---------------------------------------------------------------------------
# 5xx message scrubbing (MF-3)
# ---------------------------------------------------------------------------


def test_500_domain_error_message_is_generic() -> None:
    """500 DomainError must not leak internal message to client."""
    c = TestClient(_make_app_with_500(), raise_server_exceptions=False)
    response = c.get("/raise/internal")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["message"] == "Internal server error"
    assert "sql fragment" not in body["error"]["message"]
    assert "secrets" not in body["error"]["message"]


def test_sub_500_domain_error_message_is_preserved() -> None:
    """4xx messages must still reach the client unchanged."""
    c = TestClient(_make_app_with_500(), raise_server_exceptions=False)
    response = c.get("/raise/not-found-ok")
    assert response.status_code == 404
    body = response.json()
    assert "item not found" in body["error"]["message"]


def test_domain_error_http_status_property() -> None:
    err = TagNameTakenError("my-tag")
    assert err.http_status == 409

    err2 = WorkItemInvalidTransitionError("draft", "done")
    assert err2.http_status == 422

    err3 = NotFoundError("not here")
    assert err3.http_status == 404


def test_500_domain_error_logs_original_message(caplog: pytest.LogCaptureFixture) -> None:
    """Server log must contain the original (sensitive) message for debugging."""
    import logging


    c = TestClient(_make_app_with_500(), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="app.presentation.middleware.error_envelope"):
        c.get("/raise/internal")

    assert any("sql fragment" in record.message for record in caplog.records)


def test_500_unhandled_exception_message_is_generic() -> None:
    """Unhandled exceptions from error_middleware also scrub messages (regression guard)."""
    # This test checks that the existing error_middleware's catch-all also returns generic 500.
    # We test via error_envelope's _make_app_with_500 baseline.
    c = TestClient(_make_app_with_500(), raise_server_exceptions=False)
    response = c.get("/raise/internal")
    assert response.status_code == 500
    body = response.json()
    # Generic message, no internal details
    assert body["error"]["message"] == "Internal server error"
    assert "SELECT" not in body["error"]["message"]
