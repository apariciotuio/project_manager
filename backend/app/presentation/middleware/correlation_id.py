import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.logging import correlation_id_var

CORRELATION_ID_HEADER = "X-Correlation-Id"


def _parse_correlation_id(raw: str | None) -> str:
    """Return *raw* if it is a valid UUID string, else generate a new UUID v4."""
    if raw:
        try:
            uuid.UUID(raw)
            return raw
        except ValueError:
            pass
    return str(uuid.uuid4())


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = _parse_correlation_id(request.headers.get(CORRELATION_ID_HEADER))
        token = correlation_id_var.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
