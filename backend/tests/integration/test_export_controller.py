"""Integration tests for POST /api/v1/work-items/{id}/export/jira — EP-11.

Strategy: override get_current_user + get_export_service to avoid DB/Jira deps.
Tests exercise the controller layer only: auth guard, workspace guard, 202 response.
"""
from __future__ import annotations

import secrets
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.adapters.jira_adapter import JiraIssue

_CSRF_TOKEN = "test-csrf-token-ep11"


def _post(client: AsyncClient, url: str, json: Any) -> Any:
    """POST with CSRF headers."""
    return client.post(
        url,
        json=json,
        cookies={"csrf_token": _CSRF_TOKEN},
        headers={"X-CSRF-Token": _CSRF_TOKEN},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_WORKSPACE_ID = uuid4()
_USER_ID = uuid4()
_WORK_ITEM_ID = uuid4()

_JIRA_ISSUE = JiraIssue(key="PROJ-99", self_url="https://example.atlassian.net/rest/api/3/issue/99", id="99")


@pytest_asyncio.fixture
async def app_with_overrides():
    """Create FastAPI app with auth + export service overridden."""
    from app.application.services.export_service import ExportService
    from app.main import create_app
    from app.presentation.dependencies import get_current_user, get_export_service
    from app.presentation.middleware.auth_middleware import CurrentUser

    fastapi_app = create_app()

    # Authenticated user with a workspace
    authed_user = CurrentUser(
        id=_USER_ID,
        email="test@example.com",
        workspace_id=_WORKSPACE_ID,
        is_superadmin=False,
    )

    async def _fake_current_user():
        return authed_user

    # Fake ExportService that returns a JiraIssue
    fake_service = AsyncMock(spec=ExportService)
    fake_service.export_work_item_to_jira.return_value = _JIRA_ISSUE

    async def _fake_export_service():
        return fake_service

    fastapi_app.dependency_overrides[get_current_user] = _fake_current_user
    fastapi_app.dependency_overrides[get_export_service] = _fake_export_service

    yield fastapi_app


@pytest_asyncio.fixture
async def app_unauthenticated():
    """App where get_current_user raises 401."""
    from fastapi import HTTPException
    from app.main import create_app
    from app.presentation.dependencies import get_current_user

    fastapi_app = create_app()

    async def _no_user():
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "MISSING_TOKEN", "message": "not logged in", "details": {}}},
        )

    fastapi_app.dependency_overrides[get_current_user] = _no_user
    yield fastapi_app


@pytest_asyncio.fixture
async def app_no_workspace():
    """App where user has no active workspace (workspace_id=None)."""
    from app.application.services.export_service import ExportService
    from app.main import create_app
    from app.presentation.dependencies import get_current_user, get_export_service
    from app.presentation.middleware.auth_middleware import CurrentUser

    fastapi_app = create_app()

    no_ws_user = CurrentUser(
        id=_USER_ID,
        email="test@example.com",
        workspace_id=None,
        is_superadmin=False,
    )

    async def _no_ws_user():
        return no_ws_user

    fake_service = AsyncMock(spec=ExportService)

    async def _fake_export_service():
        return fake_service

    fastapi_app.dependency_overrides[get_current_user] = _no_ws_user
    fastapi_app.dependency_overrides[get_export_service] = _fake_export_service
    yield fastapi_app


@pytest_asyncio.fixture
async def http(app_with_overrides) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def http_unauthed(app_unauthenticated) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app_unauthenticated),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def http_no_ws(app_no_workspace) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app_no_workspace),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_to_jira_returns_202(http: AsyncClient) -> None:
    resp = await _post(http, f"/api/v1/work-items/{_WORK_ITEM_ID}/export/jira", {"project_key": "PROJ"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["data"]["status"] == "queued"
    assert "job_id" in body["data"]


@pytest.mark.asyncio
async def test_export_to_jira_requires_authentication(http_unauthed: AsyncClient) -> None:
    resp = await _post(http_unauthed, f"/api/v1/work-items/{_WORK_ITEM_ID}/export/jira", {"project_key": "PROJ"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_to_jira_requires_workspace(http_no_ws: AsyncClient) -> None:
    """User authenticated but has no active workspace — should 401."""
    resp = await _post(http_no_ws, f"/api/v1/work-items/{_WORK_ITEM_ID}/export/jira", {"project_key": "PROJ"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "NO_WORKSPACE"


@pytest.mark.asyncio
async def test_export_to_jira_missing_project_key_returns_422(http: AsyncClient) -> None:
    resp = await _post(http, f"/api/v1/work-items/{_WORK_ITEM_ID}/export/jira", {})
    assert resp.status_code == 422
