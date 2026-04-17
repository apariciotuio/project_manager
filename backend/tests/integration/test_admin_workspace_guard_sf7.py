"""SF-7 regression — routing_rule + validation_rule_template controllers
require workspace_id in token (enforced by require_admin).

A token without workspace_id must be rejected with 401.
"""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"


def _token_no_workspace(user_id) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "nows@test.com",
            # workspace_id intentionally omitted
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE routing_rules, validation_rule_templates, projects, "
                "workspace_memberships, sessions, oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()
    fake_cache = FakeCache()

    async def _override_cache():
        yield fake_cache

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    yield fastapi_app

    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def http(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


@pytest_asyncio.fixture
def no_ws_token():
    return _token_no_workspace(uuid4())


def _expect_no_workspace(resp) -> None:
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "NO_WORKSPACE"


# ---------------------------------------------------------------------------
# routing_rule_controller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_routing_rules_no_workspace(http, no_ws_token):
    resp = await http.get("/api/v1/routing-rules", cookies={"access_token": no_ws_token})
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_create_routing_rule_no_workspace(http, no_ws_token):
    resp = await http.post(
        "/api/v1/routing-rules",
        json={"work_item_type": "bug"},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_get_routing_rule_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/routing-rules/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_patch_routing_rule_no_workspace(http, no_ws_token):
    resp = await http.patch(
        f"/api/v1/routing-rules/{uuid4()}",
        json={},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_delete_routing_rule_no_workspace(http, no_ws_token):
    resp = await http.delete(
        f"/api/v1/routing-rules/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


# ---------------------------------------------------------------------------
# validation_rule_template_controller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_vrt_no_workspace(http, no_ws_token):
    resp = await http.get(
        "/api/v1/validation-rule-templates",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_create_vrt_no_workspace(http, no_ws_token):
    resp = await http.post(
        "/api/v1/validation-rule-templates",
        json={"name": "Test", "requirement_type": "spec", "is_mandatory": True},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_get_vrt_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/validation-rule-templates/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_patch_vrt_no_workspace(http, no_ws_token):
    resp = await http.patch(
        f"/api/v1/validation-rule-templates/{uuid4()}",
        json={},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_delete_vrt_no_workspace(http, no_ws_token):
    resp = await http.delete(
        f"/api/v1/validation-rule-templates/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)
