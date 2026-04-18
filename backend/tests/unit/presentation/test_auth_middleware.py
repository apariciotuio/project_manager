"""AuthMiddleware unit tests — cookie-based JWT validation + typed CurrentUser."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.presentation.middleware.auth_middleware import (
    CurrentUser,
    build_current_user_dependency,
)


@pytest.fixture
def jwt_adapter() -> JwtAdapter:
    return JwtAdapter(secret="mw-test-secret-must-be-at-least-32b", algorithm="HS256")


@pytest.fixture
def app(jwt_adapter: JwtAdapter) -> FastAPI:
    get_user = build_current_user_dependency(jwt_adapter)
    api = FastAPI()

    @api.get("/me")
    async def me(user: CurrentUser = Depends(get_user)) -> dict:
        return {
            "id": str(user.id),
            "email": user.email,
            "workspace_id": str(user.workspace_id) if user.workspace_id else None,
            "is_superadmin": user.is_superadmin,
        }

    return api


async def _call(app: FastAPI, *, cookie: str | None = None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cookies = {"access_token": cookie} if cookie else None
        return await client.get("/me", cookies=cookies)


def _valid_token(adapter: JwtAdapter, **overrides) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "email": "a@tuio.com",
        "workspace_id": str(uuid4()),
        "is_superadmin": False,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    payload.update(overrides)
    return adapter.encode(payload)


async def test_missing_cookie_returns_401_missing_token(app) -> None:
    resp = await _call(app)
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["error"]["code"] == "MISSING_TOKEN"


async def test_valid_token_injects_current_user(app, jwt_adapter) -> None:
    sub = uuid4()
    ws = uuid4()
    token = _valid_token(jwt_adapter, sub=str(sub), workspace_id=str(ws), is_superadmin=True)
    resp = await _call(app, cookie=token)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(sub)
    assert body["workspace_id"] == str(ws)
    assert body["is_superadmin"] is True


async def test_expired_token_returns_401_token_expired(app, jwt_adapter) -> None:
    past = int((datetime.now(UTC) - timedelta(seconds=5)).timestamp())
    token = _valid_token(jwt_adapter, exp=past)
    resp = await _call(app, cookie=token)
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "TOKEN_EXPIRED"


async def test_tampered_token_returns_401_invalid_token(app, jwt_adapter) -> None:
    token = _valid_token(jwt_adapter)
    tampered = token[:-4] + "AAAA"
    resp = await _call(app, cookie=tampered)
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_TOKEN"


async def test_token_signed_with_different_secret_returns_invalid(app) -> None:
    other = JwtAdapter(secret="other-secret-also-32-bytes-long-xx", algorithm="HS256")
    token = _valid_token(other)
    resp = await _call(app, cookie=token)
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_TOKEN"


async def test_workspace_id_nullable_in_claims(app, jwt_adapter) -> None:
    """Picker routing issues a JWT with workspace_id=None; middleware must accept."""
    token = _valid_token(jwt_adapter, workspace_id=None)
    resp = await _call(app, cookie=token)
    assert resp.status_code == 200
    assert resp.json()["workspace_id"] is None


async def test_malformed_sub_claim_returns_invalid_token(app, jwt_adapter) -> None:
    token = _valid_token(jwt_adapter, sub="not-a-uuid")
    resp = await _call(app, cookie=token)
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_TOKEN"
