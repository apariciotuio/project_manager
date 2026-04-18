"""EP-12 Audit integration — Jira export slice.

Scenarios:
  - POST /work-items/{id}/export/jira (202) → audit row action='jira_export_queued',
    category='domain', entity_type='work_item', outcome='success', ip_address+user_agent in context
  - background task success → audit row action='jira_export_completed', outcome='success', jira_key in context
  - background task failure → audit row action='jira_export_completed', outcome='failure', error in context

Strategy: override get_export_service with a controllable fake. For background task
audit assertions we use a capture-based fake AuditService and pass it through.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.adapters.jira_adapter import JiraAuthError, JiraIssue

_CSRF_TOKEN = "test-csrf-ep12-jira"
_WORKSPACE_ID = uuid4()
_USER_ID = uuid4()
_WORK_ITEM_ID = uuid4()
_JIRA_ISSUE = JiraIssue(
    key="PROJ-42",
    self_url="https://example.atlassian.net/rest/api/3/issue/42",
    id="42",
)


def _post(client: AsyncClient, url: str, json: Any) -> Any:
    return client.post(
        url,
        json=json,
        cookies={"csrf_token": _CSRF_TOKEN},
        headers={"X-CSRF-Token": _CSRF_TOKEN},
    )


class _CaptureAuditService:
    """Fake AuditService that captures log_event calls for assertion."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)

    def find(self, *, action: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("action") == action]


@pytest_asyncio.fixture
async def audit_capture() -> _CaptureAuditService:
    return _CaptureAuditService()


@pytest_asyncio.fixture
async def app_success(audit_capture):
    """App with fake ExportService (success) and captured AuditService."""
    from app.application.services.export_service import ExportService
    from app.main import create_app
    from app.presentation.dependencies import get_audit_service, get_current_user, get_export_service
    from app.presentation.middleware.auth_middleware import CurrentUser

    fastapi_app = create_app()

    authed_user = CurrentUser(
        id=_USER_ID,
        email="test@example.com",
        workspace_id=_WORKSPACE_ID,
        is_superadmin=False,
    )

    async def _fake_user():
        return authed_user

    fake_export = AsyncMock(spec=ExportService)
    fake_export.export_work_item_to_jira.return_value = _JIRA_ISSUE

    async def _fake_export():
        return fake_export

    async def _fake_audit():
        return audit_capture

    fastapi_app.dependency_overrides[get_current_user] = _fake_user
    fastapi_app.dependency_overrides[get_export_service] = _fake_export
    fastapi_app.dependency_overrides[get_audit_service] = _fake_audit

    yield fastapi_app


@pytest_asyncio.fixture
async def app_failure(audit_capture):
    """App with fake ExportService that raises JiraAuthError in background."""
    from app.application.services.export_service import ExportService
    from app.main import create_app
    from app.presentation.dependencies import get_audit_service, get_current_user, get_export_service
    from app.presentation.middleware.auth_middleware import CurrentUser

    fastapi_app = create_app()

    authed_user = CurrentUser(
        id=_USER_ID,
        email="test@example.com",
        workspace_id=_WORKSPACE_ID,
        is_superadmin=False,
    )

    async def _fake_user():
        return authed_user

    fake_export = AsyncMock(spec=ExportService)
    fake_export.export_work_item_to_jira.side_effect = Exception("JIRA_AUTH_ERROR: 401")

    async def _fake_export():
        return fake_export

    async def _fake_audit():
        return audit_capture

    fastapi_app.dependency_overrides[get_current_user] = _fake_user
    fastapi_app.dependency_overrides[get_export_service] = _fake_export
    fastapi_app.dependency_overrides[get_audit_service] = _fake_audit

    yield fastapi_app


@pytest_asyncio.fixture
async def http_success(app_success) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app_success),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def http_failure(app_failure) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app_failure),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_jira_export_queued_emits_audit(http_success, audit_capture) -> None:
    """202 response → jira_export_queued audit event with ip_address+user_agent."""
    resp = await _post(
        http_success,
        f"/api/v1/work-items/{_WORK_ITEM_ID}/export/jira",
        {"project_key": "PROJ"},
    )
    assert resp.status_code == 202, resp.text

    # Allow background task to execute
    await asyncio.sleep(0.05)

    queued = audit_capture.find(action="jira_export_queued")
    assert len(queued) >= 1, f"expected jira_export_queued, got {audit_capture.events}"
    ev = queued[0]
    assert ev["category"] == "domain"
    assert ev["entity_type"] == "work_item"
    assert ev["entity_id"] == _WORK_ITEM_ID
    ctx = ev.get("context", {})
    assert ctx.get("outcome") == "success"
    assert "ip_address" in ctx, f"ip_address missing: {ctx}"
    assert "user_agent" in ctx, f"user_agent missing: {ctx}"


@pytest.mark.asyncio
async def test_jira_export_completed_success_emits_audit(http_success, audit_capture) -> None:
    """Background success → jira_export_completed with outcome=success and jira_key."""
    resp = await _post(
        http_success,
        f"/api/v1/work-items/{_WORK_ITEM_ID}/export/jira",
        {"project_key": "PROJ"},
    )
    assert resp.status_code == 202, resp.text

    await asyncio.sleep(0.1)

    completed = audit_capture.find(action="jira_export_completed")
    assert len(completed) >= 1, f"expected jira_export_completed, got {audit_capture.events}"
    ev = completed[0]
    assert ev["category"] == "domain"
    assert ev["entity_type"] == "work_item"
    assert ev["entity_id"] == _WORK_ITEM_ID
    ctx = ev.get("context", {})
    assert ctx.get("outcome") == "success"
    assert ctx.get("jira_key") == "PROJ-42"


@pytest.mark.asyncio
async def test_jira_export_completed_failure_emits_audit(http_failure, audit_capture) -> None:
    """Background failure → jira_export_completed with outcome=failure and error in context."""
    resp = await _post(
        http_failure,
        f"/api/v1/work-items/{_WORK_ITEM_ID}/export/jira",
        {"project_key": "PROJ"},
    )
    assert resp.status_code == 202, resp.text

    await asyncio.sleep(0.1)

    completed = audit_capture.find(action="jira_export_completed")
    assert len(completed) >= 1, f"expected jira_export_completed failure, got {audit_capture.events}"
    ev = completed[0]
    assert ev["category"] == "domain"
    ctx = ev.get("context", {})
    assert ctx.get("outcome") == "failure"
    assert "error" in ctx, f"error missing from failure context: {ctx}"
