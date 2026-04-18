"""EP-00 Phase 10 — global error middleware.

Maps domain and adapter exceptions to the API error envelope. Anything not in
the explicit table falls through to `_internal_error_handler` which returns a
generic 500 and logs the full traceback. We never leak internals to the client.

Keep the mapping table here — not in the controllers — so the same exception
behaves consistently regardless of which route raised it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
    DraftForbiddenError,
    DuplicateTemplateError,
    InvalidSuggestionStateError,
    InvalidTransitionError,
    MandatoryValidationsPendingError,
    NotOwnerError,
    OwnerSuspendedError,
    SuggestionExpiredError,
    TargetUserSuspendedError,
    TemplateForbiddenError,
    TemplateNotFoundError,
    WorkItemDraftNotFoundError,
    WorkItemInvalidStateError,
    WorkItemNotFoundError,
)
from app.domain.repositories.oauth_state_repository import OAuthStateCollisionError
from app.infrastructure.adapters.google_oauth_adapter import OAuthExchangeError

logger = logging.getLogger(__name__)


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def _session_expired_handler(_: Request, exc: SessionExpiredError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=_envelope("SESSION_EXPIRED", str(exc) or "session expired"),
    )


async def _session_revoked_handler(_: Request, exc: SessionRevokedError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=_envelope("SESSION_REVOKED", str(exc) or "session revoked"),
    )


async def _invalid_state_handler(_: Request, exc: InvalidStateError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=_envelope("INVALID_OAUTH_STATE", str(exc) or "invalid state"),
    )


async def _no_workspace_handler(_: Request, __: NoWorkspaceAccessError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=_envelope("NO_WORKSPACE", "no active workspace membership"),
    )


async def _oauth_exchange_handler(_: Request, exc: OAuthExchangeError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content=_envelope("OAUTH_EXCHANGE_FAILED", str(exc) or "oauth exchange failed"),
    )


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    # Special case: WorkItemUpdateRequest rejects `state` field via extra="forbid".
    # Return a dedicated hint so clients know to use the transitions endpoint.
    if errors:
        first = errors[0]
        loc = first.get("loc", ())
        if loc and loc[-1] == "state":
            return JSONResponse(
                status_code=422,
                content=_envelope(
                    "VALIDATION_ERROR",
                    "use the transitions endpoint to change state",
                    {"reason": "use_transition_endpoint"},
                ),
            )
        # Surface the first offending field name for single-field errors
        field = str(loc[-1]) if loc else None
        # Pydantic v2 errors may contain non-serializable objects (e.g. ValueError in ctx)
        serializable_errors = [
            {k: (str(v) if k == "ctx" else v) for k, v in e.items()} for e in errors
        ]
        details: dict[str, Any] = {"errors": serializable_errors}
        if field:
            details["field"] = field
        return JSONResponse(
            status_code=422,
            content=_envelope("VALIDATION_ERROR", "request validation failed", details),
        )
    return JSONResponse(
        status_code=422,
        content=_envelope("VALIDATION_ERROR", "request validation failed", {"errors": errors}),
    )


# ---------------------------------------------------------------------------
# EP-01 domain exception handlers
# ---------------------------------------------------------------------------


async def _invalid_transition_handler(_: Request, exc: InvalidTransitionError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope(
            "INVALID_TRANSITION",
            str(exc),
            {"from_state": exc.from_state, "to_state": exc.to_state},
        ),
    )


async def _not_owner_handler(_: Request, exc: NotOwnerError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=_envelope("NOT_OWNER", str(exc)),
    )


async def _validations_pending_handler(
    _: Request, exc: MandatoryValidationsPendingError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope(
            "VALIDATIONS_PENDING",
            str(exc),
            {"pending_ids": list(exc.pending_ids)},
        ),
    )


async def _confirmation_required_handler(
    _: Request, exc: ConfirmationRequiredError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope(
            "CONFIRMATION_REQUIRED",
            str(exc),
            {"pending_validation_ids": list(exc.pending_ids)},
        ),
    )


async def _owner_suspended_handler(_: Request, exc: OwnerSuspendedError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope("OWNER_SUSPENDED", str(exc)),
    )


async def _target_user_suspended_handler(_: Request, exc: TargetUserSuspendedError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope("TARGET_USER_SUSPENDED", str(exc)),
    )


async def _work_item_not_found_handler(_: Request, exc: WorkItemNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_envelope("WORK_ITEM_NOT_FOUND", str(exc)),
    )


async def _cannot_delete_non_draft_handler(
    _: Request, exc: CannotDeleteNonDraftError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope("CANNOT_DELETE_NON_DRAFT", str(exc)),
    )


async def _creator_not_member_handler(_: Request, exc: CreatorNotMemberError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=_envelope("CREATOR_NOT_MEMBER", str(exc)),
    )


# ---------------------------------------------------------------------------
# EP-02 domain exception handlers
# ---------------------------------------------------------------------------


async def _work_item_invalid_state_handler(
    _: Request, exc: WorkItemInvalidStateError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=_envelope(
            "INVALID_STATE",
            str(exc),
            {"expected_state": exc.expected_state, "actual_state": exc.actual_state},
        ),
    )


async def _duplicate_template_handler(_: Request, exc: DuplicateTemplateError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=_envelope(
            "DUPLICATE_TEMPLATE",
            str(exc),
            {"type": exc.type_},
        ),
    )


async def _template_forbidden_handler(_: Request, exc: TemplateForbiddenError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=_envelope("FORBIDDEN", str(exc)),
    )


async def _template_not_found_handler(_: Request, exc: TemplateNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_envelope("TEMPLATE_NOT_FOUND", str(exc)),
    )


async def _draft_forbidden_handler(_: Request, exc: DraftForbiddenError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=_envelope("FORBIDDEN", str(exc) or "you do not own this draft"),
    )


async def _work_item_draft_not_found_handler(
    _: Request, exc: WorkItemDraftNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_envelope("DRAFT_NOT_FOUND", str(exc)),
    )


# ---------------------------------------------------------------------------
# EP-03 domain exception handlers
# ---------------------------------------------------------------------------


async def _suggestion_expired_handler(_: Request, exc: SuggestionExpiredError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope(
            "SUGGESTION_EXPIRED", str(exc), {"suggestion_id": str(exc.suggestion_id)}
        ),
    )


async def _invalid_suggestion_state_handler(
    _: Request, exc: InvalidSuggestionStateError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope("INVALID_SUGGESTION_STATE", str(exc)),
    )


async def _audit_authorization_denied(request: Request) -> None:
    """Fire-and-forget audit record for 403 responses.

    Wrapped in try/except — an audit failure must never mask the 403.
    """
    try:
        from app.application.services.audit_service import AuditService
        from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
        from app.infrastructure.persistence.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            audit = AuditService(AuditRepositoryImpl(session))
            path = request.url.path
            ip_address = request.client.host if request.client else None
            await audit.log_event(
                category="auth",
                action="authorization_denied",
                entity_type=path.split("/")[3] if len(path.split("/")) > 3 else None,
                context={
                    "outcome": "failure",
                    "path": path,
                    "method": request.method,
                    "ip_address": ip_address,
                },
            )
            await session.commit()
    except Exception:
        logger.exception("failed to write authorization_denied audit record")


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Controller-raised HTTPException already carries an envelope in `detail` — pass through.
    if exc.status_code == 403:
        await _audit_authorization_denied(request)

    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    message = exc.detail if isinstance(exc.detail, str) else "http error"
    return JSONResponse(status_code=exc.status_code, content=_envelope("HTTP_ERROR", message))


async def _oauth_state_collision_handler(_: Request, __: OAuthStateCollisionError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_envelope("INTERNAL_ERROR", "internal server error"),
    )


async def _internal_error_handler(request: Request, _: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=_envelope("INTERNAL_ERROR", "internal server error"),
    )


def _register(app: FastAPI, exc_type: type, handler: Any) -> None:
    app.add_exception_handler(exc_type, handler)


def register_error_handlers(app: FastAPI) -> None:
    _register(app, SessionExpiredError, _session_expired_handler)
    _register(app, SessionRevokedError, _session_revoked_handler)
    _register(app, InvalidStateError, _invalid_state_handler)
    _register(app, NoWorkspaceAccessError, _no_workspace_handler)
    _register(app, OAuthExchangeError, _oauth_exchange_handler)
    _register(app, OAuthStateCollisionError, _oauth_state_collision_handler)
    # EP-01 domain exceptions
    _register(app, InvalidTransitionError, _invalid_transition_handler)
    _register(app, NotOwnerError, _not_owner_handler)
    _register(app, MandatoryValidationsPendingError, _validations_pending_handler)
    _register(app, ConfirmationRequiredError, _confirmation_required_handler)
    _register(app, OwnerSuspendedError, _owner_suspended_handler)
    _register(app, TargetUserSuspendedError, _target_user_suspended_handler)
    _register(app, WorkItemNotFoundError, _work_item_not_found_handler)
    _register(app, CannotDeleteNonDraftError, _cannot_delete_non_draft_handler)
    _register(app, CreatorNotMemberError, _creator_not_member_handler)
    # EP-02 domain exceptions
    _register(app, WorkItemInvalidStateError, _work_item_invalid_state_handler)
    _register(app, DuplicateTemplateError, _duplicate_template_handler)
    _register(app, TemplateForbiddenError, _template_forbidden_handler)
    _register(app, TemplateNotFoundError, _template_not_found_handler)
    _register(app, DraftForbiddenError, _draft_forbidden_handler)
    _register(app, WorkItemDraftNotFoundError, _work_item_draft_not_found_handler)
    # EP-03 domain exceptions
    _register(app, SuggestionExpiredError, _suggestion_expired_handler)
    _register(app, InvalidSuggestionStateError, _invalid_suggestion_state_handler)
    _register(app, RequestValidationError, _validation_error_handler)
    _register(app, StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _internal_error_handler)
