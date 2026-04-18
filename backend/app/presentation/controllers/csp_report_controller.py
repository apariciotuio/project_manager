"""CSP violation report endpoint.

POST /api/v1/csp-report
  - No authentication required (browsers send this before any user context)
  - Accepts: application/csp-report, application/json, or empty body
  - Returns: 204 No Content
  - Effect: logs violation details at WARNING level

Spec: EP-12 tasks-backend.md — Group 2, Content Security Policy
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter()

# No auth required: browsers POST CSP reports without user context.
# The endpoint is rate-limited globally by RateLimitMiddleware.


@router.post(
    "/api/v1/csp-report",
    status_code=204,
    response_class=Response,
    summary="CSP violation report receiver",
    include_in_schema=False,  # internal infra endpoint
)
async def csp_report(request: Request) -> Response:
    """Receive and log Content Security Policy violation reports."""
    try:
        body_bytes = await request.body()
        if body_bytes:
            import json

            try:
                report: Any = json.loads(body_bytes)
            except (json.JSONDecodeError, UnicodeDecodeError):
                report = {"raw": body_bytes.decode("utf-8", errors="replace")}
        else:
            report = {}
    except Exception:
        report = {}

    # Extract the most useful field for the log line
    csp_report_inner = report.get("csp-report", report) if isinstance(report, dict) else {}
    blocked_uri = (
        csp_report_inner.get("blocked-uri", "unknown")
        if isinstance(csp_report_inner, dict)
        else "unknown"
    )
    violated_directive = (
        csp_report_inner.get("violated-directive", "unknown")
        if isinstance(csp_report_inner, dict)
        else "unknown"
    )

    logger.warning(
        "CSP violation: blocked-uri=%s directive=%s report=%r",
        blocked_uri,
        violated_directive,
        csp_report_inner,
    )

    return Response(status_code=204)
