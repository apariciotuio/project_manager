"""SF-3 — Dashboard controller: /dashboards/person/{user_id} must reject cross-user access.

Tests that user A cannot view user B's metrics unless A is a superadmin.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"


def _make_token(
    user_id: UUID,
    workspace_id: UUID,
    *,
    is_superadmin: bool = False,
) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@test.com",
            "workspace_id": str(workspace_id),
            "is_superadmin": is_superadmin,
            "exp": int(time.time()) + 3600,
        }
    )


@pytest.fixture
def app_with_fake_service(override_settings) -> FastAPI:
    """Stand-alone FastAPI app with faked PersonDashboardService dependency."""
    from app.main import create_app
    from app.presentation.dependencies import (
        get_cache_adapter,
        get_person_dashboard_service,
    )
    from tests.fakes.fake_repositories import FakeCache

    class FakePersonDashboardService:
        async def get_metrics(self, user_id: UUID, *, workspace_id: UUID) -> dict[str, Any]:
            return {
                "owned_by_state": {},
                "overloaded": False,
                "pending_reviews_count": 0,
                "inbox_count": 0,
            }

    fastapi_app = create_app()
    fake_cache = FakeCache()

    async def _override_cache():
        yield fake_cache

    async def _override_service():
        yield FakePersonDashboardService()

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    fastapi_app.dependency_overrides[get_person_dashboard_service] = _override_service
    return fastapi_app


@pytest.mark.asyncio
async def test_sf3_user_can_read_own_dashboard(app_with_fake_service: FastAPI) -> None:
    """User A can read their own dashboard."""
    user_id = uuid4()
    ws_id = uuid4()
    token = _make_token(user_id, ws_id)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_fake_service), base_url="http://test"
    ) as client:
        r = await client.get(
            f"/api/v1/dashboards/person/{user_id}",
            cookies={"access_token": token},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_sf3_user_cannot_read_other_users_dashboard(app_with_fake_service: FastAPI) -> None:
    """User A cannot read user B's dashboard — must return 403."""
    user_a = uuid4()
    user_b = uuid4()
    ws_id = uuid4()
    token_a = _make_token(user_a, ws_id)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_fake_service), base_url="http://test"
    ) as client:
        r = await client.get(
            f"/api/v1/dashboards/person/{user_b}",
            cookies={"access_token": token_a},
        )
    assert r.status_code == 403, (
        f"User A reading user B's dashboard should be 403, got {r.status_code}"
    )


@pytest.mark.asyncio
async def test_sf3_superadmin_can_read_any_dashboard(app_with_fake_service: FastAPI) -> None:
    """Superadmin can read any user's dashboard."""
    admin_id = uuid4()
    target_id = uuid4()
    ws_id = uuid4()
    token = _make_token(admin_id, ws_id, is_superadmin=True)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_fake_service), base_url="http://test"
    ) as client:
        r = await client.get(
            f"/api/v1/dashboards/person/{target_id}",
            cookies={"access_token": token},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_sf3_unauthenticated_returns_401(app_with_fake_service: FastAPI) -> None:
    """No token → 401."""
    user_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app_with_fake_service), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/v1/dashboards/person/{user_id}")
    assert r.status_code == 401
