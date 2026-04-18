"""EP-21 F-4-be — DomainError → error envelope handler.

Registers a FastAPI exception handler that maps DomainError subclasses to the
structured error envelope format.  The existing error_middleware.py handles all
legacy exception types; this module handles the new DomainError hierarchy.

Wire up via ``register_domain_error_handler(app)`` called after the existing
``register_error_handlers(app)`` in main.py so DomainError takes precedence
over the catch-all Exception handler.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging import correlation_id_var
from app.domain.errors.codes import DomainError

logger = logging.getLogger(__name__)

_GENERIC_SERVER_ERROR = "Internal server error"


def _envelope(
    code: str,
    message: str,
    *,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if field is not None:
        payload["field"] = field
    if details:
        payload["details"] = details
    return {"error": payload}


async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:  # noqa: ARG001
    status = exc.http_status
    if status >= 500:
        correlation_id = correlation_id_var.get("")
        logger.error(
            "DomainError 5xx: code=%s message=%r correlation_id=%s\n%s",
            exc.code,
            exc.message,
            correlation_id,
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
        client_message = _GENERIC_SERVER_ERROR
    else:
        client_message = exc.message

    return JSONResponse(
        status_code=status,
        content=_envelope(
            exc.code,
            client_message,
            field=exc.field,
            details=exc.details if exc.details else None,
        ),
    )


def register_domain_error_handler(app: FastAPI) -> None:
    """Register the DomainError handler on the FastAPI app.

    Call this AFTER ``register_error_handlers`` so the DomainError handler
    is evaluated before the generic Exception catch-all.
    """
    app.add_exception_handler(DomainError, _domain_error_handler)  # type: ignore[arg-type]  # Starlette's signature uses Exception; DomainError is a subclass
