from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config.logging import configure_logging
from app.presentation.controllers.admin_controller import router as admin_router
from app.presentation.controllers.puppet_controller import router as puppet_router
from app.presentation.controllers.attachment_controller import router as attachment_router
from app.presentation.controllers.auth import router as auth_router
from app.presentation.controllers.clarification_controller import (
    router as clarification_router,
)
from app.presentation.controllers.comment_controller import router as comment_router
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
from app.presentation.controllers.integration_controller import router as integration_router
from app.presentation.controllers.routing_rule_controller import router as routing_rule_router
from app.presentation.controllers.validation_rule_template_controller import router as vrt_router
from app.presentation.controllers.lock_controller import router as lock_router
from app.presentation.controllers.next_step_controller import router as next_step_router
from app.presentation.controllers.notification_controller import router as notification_router
from app.presentation.controllers.project_controller import router as project_router
from app.presentation.controllers.ready_gate_controller import router as ready_gate_router
from app.presentation.controllers.review_controller import router as review_router
from app.presentation.controllers.validation_controller import router as validation_router
from app.presentation.controllers.saved_search_controller import router as saved_search_router
from app.presentation.controllers.search_controller import router as search_router
from app.presentation.controllers.dashboard_controller import router as dashboard_router
from app.presentation.controllers.specification_controller import (
    router as specification_router,
)
from app.presentation.controllers.suggestion_controller import router as suggestion_router
from app.presentation.controllers.tag_controller import router as tag_router
from app.presentation.controllers.task_controller import router as task_router
from app.presentation.controllers.team_controller import router as team_router
from app.presentation.controllers.template_controller import router as template_router
from app.presentation.controllers.timeline_controller import router as timeline_router
from app.presentation.controllers.version_controller import router as version_router
from app.presentation.controllers.work_item_controller import router as work_item_router
from app.presentation.controllers.work_item_draft_controller import (
    router as work_item_draft_router,
)
from app.presentation.controllers.workspace_controller import (
    router as workspace_router,
)
from app.presentation.middleware.body_size_limit import BodySizeLimitMiddleware
from app.presentation.middleware.correlation_id import CorrelationIDMiddleware
from app.presentation.middleware.cors_policy import CORSPolicyMiddleware
from app.presentation.middleware.error_envelope import register_domain_error_handler
from app.presentation.middleware.error_middleware import register_error_handlers
from app.presentation.middleware.request_logging import RequestLoggingMiddleware
from app.presentation.middleware.security_headers import SecurityHeadersMiddleware
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
    from app.application.events import register_event_subscribers
    from app.application.events.event_bus import get_global_bus
    from app.config.settings import get_settings

    settings = get_settings()
    configure_logging(settings.app.log_level)

    # Wire event subscribers on the global bus once at startup.
    register_event_subscribers(get_global_bus())

    app = FastAPI(
        title="Work Maturation Platform",
        version="0.1.0",
        debug=settings.app.debug,
    )

    limiter = build_limiter(settings.auth.rate_limit_per_minute)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    register_error_handlers(app)
    register_domain_error_handler(app)

    # Middleware registration — Starlette add_middleware is LIFO:
    # last added = outermost (runs first on request, last on response).
    #
    # Execution order outermost → innermost:
    #   CorrelationIDMiddleware       — generates/passes X-Correlation-ID ContextVar
    #   RequestLoggingMiddleware      — structured log line per request
    #   BodySizeLimitMiddleware       — early 413 before auth/CORS cost
    #   CORSPolicyMiddleware          — strict allowlist; handles preflight
    #   SecurityHeadersMiddleware     — CSP, X-Frame-Options, HSTS on every response
    #
    # Add in reverse order so CorrelationID is outermost.
    app.add_middleware(
        SecurityHeadersMiddleware,
        csp_overrides=settings.app.csp_overrides,
    )
    app.add_middleware(
        CORSPolicyMiddleware,
        allowed_origins=settings.app.cors_allowed_origins,
        env=settings.app.env,
    )
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_bytes=settings.app.max_body_bytes,
        large_body_prefixes=["/api/v1/attachments"],
        large_body_limit=10 * 1024 * 1024,
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(workspace_router, prefix="/api/v1")
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
    app.include_router(next_step_router, prefix="/api/v1")
    # EP-05 — task hierarchy + dependencies
    app.include_router(task_router, prefix="/api/v1")
    # EP-06 — reviews + validation + ready gate
    app.include_router(review_router, prefix="/api/v1")
    app.include_router(validation_router, prefix="/api/v1")
    app.include_router(ready_gate_router, prefix="/api/v1")
    # EP-07 — comments + timeline + versions
    app.include_router(comment_router, prefix="/api/v1")
    app.include_router(timeline_router, prefix="/api/v1")
    app.include_router(version_router, prefix="/api/v1")
    # EP-15 — tags
    app.include_router(tag_router, prefix="/api/v1")
    # EP-16 — attachments
    app.include_router(attachment_router, prefix="/api/v1")
    # EP-17 — section locks
    app.include_router(lock_router, prefix="/api/v1")
    # EP-08 — teams + notifications
    app.include_router(team_router, prefix="/api/v1")
    app.include_router(notification_router, prefix="/api/v1")
    # EP-09 — saved searches
    app.include_router(saved_search_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    # EP-10 — projects + admin + routing rules + validation templates
    app.include_router(project_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(routing_rule_router, prefix="/api/v1")
    app.include_router(vrt_router, prefix="/api/v1")
    # EP-11 — integrations
    app.include_router(integration_router, prefix="/api/v1")
    # EP-13 — Puppet ingest callback + search + admin
    app.include_router(puppet_router, prefix="/api/v1")

    return app


app = create_app()
