"""EP-00 + EP-01 global error middleware unit tests.

Spins up a throwaway FastAPI app with one route per exception type, registers
the real handlers, and asserts the envelope + status for each mapping.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.services.auth_service import (
    InvalidStateError,
    NoWorkspaceAccessError,
    SessionExpiredError,
    SessionRevokedError,
)
from app.domain.exceptions import (
    CannotDeleteNonDraftError,
    ConfirmationRequiredError,
    CreatorNotMemberError,
    InvalidTransitionError,
    MandatoryValidationsPendingError,
    NotOwnerError,
    OwnerSuspendedError,
    TargetUserSuspendedError,
    WorkItemNotFoundError,
)
from app.infrastructure.adapters.google_oauth_adapter import OAuthExchangeError
from app.presentation.middleware.error_middleware import register_error_handlers


def _build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom/session-expired")
    async def r_session_expired() -> None:
        raise SessionExpiredError("refresh expired")

    @app.get("/boom/session-revoked")
    async def r_session_revoked() -> None:
        raise SessionRevokedError("revoked")

    @app.get("/boom/invalid-state")
    async def r_invalid_state() -> None:
        raise InvalidStateError("state missing")

    @app.get("/boom/no-workspace")
    async def r_no_workspace() -> None:
        raise NoWorkspaceAccessError("alice@tuio.com")

    @app.get("/boom/oauth-exchange")
    async def r_oauth_exchange() -> None:
        raise OAuthExchangeError("upstream 502")

    @app.get("/boom/internal")
    async def r_internal() -> None:
        raise RuntimeError("this should never leak")

    # EP-01 domain exceptions
    @app.get("/boom/invalid-transition")
    async def r_invalid_transition() -> None:
        raise InvalidTransitionError("draft", "exported")

    @app.get("/boom/not-owner")
    async def r_not_owner() -> None:
        raise NotOwnerError(uuid4(), uuid4())

    @app.get("/boom/validations-pending")
    async def r_validations_pending() -> None:
        raise MandatoryValidationsPendingError(uuid4(), ("v1", "v2"))

    @app.get("/boom/confirmation-required")
    async def r_confirmation_required() -> None:
        raise ConfirmationRequiredError(("v1", "v2"))

    @app.get("/boom/owner-suspended")
    async def r_owner_suspended() -> None:
        raise OwnerSuspendedError(uuid4())

    @app.get("/boom/target-user-suspended")
    async def r_target_user_suspended() -> None:
        raise TargetUserSuspendedError(uuid4())

    @app.get("/boom/work-item-not-found")
    async def r_work_item_not_found() -> None:
        raise WorkItemNotFoundError(uuid4())

    @app.get("/boom/cannot-delete-non-draft")
    async def r_cannot_delete_non_draft() -> None:
        raise CannotDeleteNonDraftError(uuid4(), "in_review")

    @app.get("/boom/creator-not-member")
    async def r_creator_not_member() -> None:
        raise CreatorNotMemberError(uuid4(), uuid4())

    @app.get("/boom/http-error-plain")
    async def r_http_error_plain() -> None:
        raise StarletteHTTPException(status_code=404, detail="not found text")

    @app.get("/boom/http-error-envelope")
    async def r_http_error_envelope() -> None:
        raise StarletteHTTPException(
            status_code=403,
            detail={"error": {"code": "CUSTOM_CODE", "message": "custom", "details": {}}},
        )

    return app


@pytest.fixture
def app() -> FastAPI:
    return _build_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        yield c


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/boom/session-expired", 401, "SESSION_EXPIRED"),
        ("/boom/session-revoked", 401, "SESSION_REVOKED"),
        ("/boom/invalid-state", 400, "INVALID_OAUTH_STATE"),
        ("/boom/no-workspace", 403, "NO_WORKSPACE"),
        ("/boom/oauth-exchange", 502, "OAUTH_EXCHANGE_FAILED"),
    ],
)
async def test_domain_exceptions_map_to_envelope(client, path, status, code) -> None:
    resp = await client.get(path)
    assert resp.status_code == status
    body = resp.json()
    assert body["error"]["code"] == code
    assert "message" in body["error"]
    assert "details" in body["error"]


async def test_unhandled_exception_returns_generic_500(client) -> None:
    resp = await client.get("/boom/internal")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    # Never leak internal message
    assert "this should never leak" not in body["error"]["message"]


# ---------------------------------------------------------------------------
# EP-01 domain exception handlers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected_status", "expected_code"),
    [
        ("/boom/invalid-transition", 422, "INVALID_TRANSITION"),
        ("/boom/not-owner", 403, "NOT_OWNER"),
        ("/boom/validations-pending", 422, "VALIDATIONS_PENDING"),
        ("/boom/confirmation-required", 422, "CONFIRMATION_REQUIRED"),
        ("/boom/owner-suspended", 422, "OWNER_SUSPENDED"),
        ("/boom/target-user-suspended", 422, "TARGET_USER_SUSPENDED"),
        ("/boom/work-item-not-found", 404, "WORK_ITEM_NOT_FOUND"),
        ("/boom/cannot-delete-non-draft", 422, "CANNOT_DELETE_NON_DRAFT"),
        ("/boom/creator-not-member", 403, "CREATOR_NOT_MEMBER"),
    ],
)
async def test_ep01_domain_exceptions_map_to_envelope(
    client, path: str, expected_status: int, expected_code: str
) -> None:
    resp = await client.get(path)
    assert resp.status_code == expected_status
    body = resp.json()
    assert body["error"]["code"] == expected_code
    assert "message" in body["error"]
    assert "details" in body["error"]


async def test_invalid_transition_includes_from_and_to_state(client) -> None:
    resp = await client.get("/boom/invalid-transition")
    assert resp.status_code == 422
    details = resp.json()["error"]["details"]
    assert details["from_state"] == "draft"
    assert details["to_state"] == "exported"


async def test_validations_pending_includes_pending_ids(client) -> None:
    resp = await client.get("/boom/validations-pending")
    assert resp.status_code == 422
    details = resp.json()["error"]["details"]
    assert "pending_ids" in details
    assert len(details["pending_ids"]) == 2


async def test_confirmation_required_includes_pending_validation_ids(client) -> None:
    resp = await client.get("/boom/confirmation-required")
    assert resp.status_code == 422
    details = resp.json()["error"]["details"]
    assert "pending_validation_ids" in details


async def test_http_exception_with_plain_string_detail(client) -> None:
    resp = await client.get("/boom/http-error-plain")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "HTTP_ERROR"
    assert "not found" in body["error"]["message"]


async def test_http_exception_with_envelope_detail_passes_through(client) -> None:
    resp = await client.get("/boom/http-error-envelope")
    assert resp.status_code == 403
    body = resp.json()
    # Envelope passthrough — should keep the original code
    assert body["error"]["code"] == "CUSTOM_CODE"
