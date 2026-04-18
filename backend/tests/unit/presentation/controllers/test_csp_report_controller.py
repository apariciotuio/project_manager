"""Tests for CSP violation report endpoint — RED phase.

POST /api/v1/csp-report
- No auth required
- Accepts any JSON body (CSP report)
- Returns 204
- Logs at WARNING level
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.presentation.controllers.csp_report_controller import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_csp_report_returns_204() -> None:
    """Valid CSP report returns 204 No Content."""
    app = _build_app()
    client = TestClient(app)

    payload = {
        "csp-report": {
            "blocked-uri": "https://evil.com/xss.js",
            "violated-directive": "script-src 'self'",
            "document-uri": "https://app.example.com/dashboard",
        }
    }
    resp = client.post(
        "/api/v1/csp-report",
        content=json.dumps(payload),
        headers={"Content-Type": "application/csp-report"},
    )
    assert resp.status_code == 204


def test_csp_report_accepts_application_json() -> None:
    """Also accepts Content-Type: application/json (browser variants)."""
    app = _build_app()
    client = TestClient(app)

    resp = client.post(
        "/api/v1/csp-report",
        json={"csp-report": {"blocked-uri": "inline", "violated-directive": "script-src"}},
    )
    assert resp.status_code == 204


def test_csp_report_accepts_empty_body() -> None:
    """Empty body should not crash — return 204."""
    app = _build_app()
    client = TestClient(app)

    resp = client.post(
        "/api/v1/csp-report",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 204


def test_csp_report_logs_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Each CSP violation is logged at WARN level."""
    app = _build_app()
    client = TestClient(app)

    with caplog.at_level(
        logging.WARNING, logger="app.presentation.controllers.csp_report_controller"
    ):
        client.post(
            "/api/v1/csp-report",
            json={
                "csp-report": {
                    "blocked-uri": "https://evil.com",
                    "violated-directive": "script-src 'self'",
                }
            },
        )

    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_csp_report_log_contains_violation_details(caplog: pytest.LogCaptureFixture) -> None:
    """Log message contains the blocked-uri from the report."""
    app = _build_app()
    client = TestClient(app)

    with caplog.at_level(
        logging.WARNING, logger="app.presentation.controllers.csp_report_controller"
    ):
        client.post(
            "/api/v1/csp-report",
            json={"csp-report": {"blocked-uri": "https://tracking.evil.com/pixel.js"}},
        )

    assert any("tracking.evil.com" in r.getMessage() for r in caplog.records)


def test_csp_report_no_auth_required() -> None:
    """Endpoint is accessible without any Authorization header or cookie."""
    app = _build_app()
    client = TestClient(app)

    # No auth headers at all
    resp = client.post(
        "/api/v1/csp-report",
        json={"csp-report": {"blocked-uri": "data:text/html,<script>"}},
    )
    assert resp.status_code == 204


def test_csp_report_no_response_body() -> None:
    """204 response must have no body."""
    app = _build_app()
    client = TestClient(app)

    resp = client.post(
        "/api/v1/csp-report",
        json={"csp-report": {}},
    )
    assert resp.status_code == 204
    assert resp.content == b""
