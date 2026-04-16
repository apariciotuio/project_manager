from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config.logging import configure_logging
from app.presentation.controllers.auth import router as auth_router
from app.presentation.controllers.clarification_controller import (
    router as clarification_router,
)
from app.presentation.controllers.completeness_controller import (
    router as completeness_router,
)
from app.presentation.controllers.conversation_controller import (
    router as conversation_router,
)
from app.presentation.controllers.dundun_callback_controller import (
    router as dundun_callback_router,
)
from app.presentation.controllers.health import router as health_router
from app.presentation.controllers.specification_controller import (
    router as specification_router,
)
from app.presentation.controllers.suggestion_controller import router as suggestion_router
from app.presentation.controllers.template_controller import router as template_router
from app.presentation.controllers.work_item_controller import router as work_item_router
from app.presentation.controllers.work_item_draft_controller import (
    router as work_item_draft_router,
)
from app.presentation.middleware.correlation_id import CorrelationIDMiddleware
from app.presentation.middleware.error_middleware import register_error_handlers
from app.presentation.rate_limit import build_limiter


def _rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    import contextlib

    retry_after = 60  # fallback for "/minute" windows
    with contextlib.suppress(AttributeError):
        retry_after = int(exc.limit.limit.get_expiry())  # type: ignore[union-attr]

    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "TOO_MANY_REQUESTS",
                "message": "Rate limit exceeded",
                "details": {"limit": str(exc.detail)},
            }
        },
        headers={"Retry-After": str(retry_after)},
    )


def create_app() -> FastAPI:
    from app.config.settings import get_settings

    settings = get_settings()
    configure_logging(settings.app.log_level)

    app = FastAPI(
        title="Work Maturation Platform",
        version="0.1.0",
        debug=settings.app.debug,
    )

    limiter = build_limiter(settings.auth.rate_limit_per_minute)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    register_error_handlers(app)

    app.add_middleware(CorrelationIDMiddleware)
    cors_origins = settings.app.cors_allowed_origins
    if "*" in cors_origins:
        raise RuntimeError(
            "CORS misconfiguration: allow_credentials=True is incompatible with "
            "wildcard allow_origins. Set explicit origins in CORS_ALLOWED_ORIGINS."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(work_item_router, prefix="/api/v1")
    app.include_router(work_item_draft_router, prefix="/api/v1")
    app.include_router(template_router, prefix="/api/v1")
    app.include_router(dundun_callback_router, prefix="/api/v1")
    # EP-03 Phase 7 — conversation, suggestion, clarification
    # REST routes on /api/v1; WS route is also on conversation_router at /ws/conversations/...
    # which becomes /api/v1/ws/conversations/{thread_id}
    app.include_router(conversation_router, prefix="/api/v1")
    app.include_router(suggestion_router, prefix="/api/v1")
    app.include_router(clarification_router, prefix="/api/v1")
    # EP-04 Phase 8 — specification + completeness
    app.include_router(specification_router, prefix="/api/v1")
    app.include_router(completeness_router, prefix="/api/v1")

    return app


app = create_app()
