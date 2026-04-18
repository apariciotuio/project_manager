"""EP-18 — Unit tests for MCP server auth context wiring.

Tests that:
1. workspace_id + user_id are read from a real JWT token, not freshly generated uuid4().
2. Missing MCP_TOKEN env var raises a clear startup error.
3. Expired/invalid token raises a clear startup error.
4. workspace_id embedded in the token is returned — no spoofing from client args.

RED phase — these tests will fail until server.py is fixed.
"""

from __future__ import annotations

import os
import time
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from jose import jwt as jose_jwt

# ---------------------------------------------------------------------------
# Helpers — build valid and invalid JWTs matching the existing JwtAdapter
# ---------------------------------------------------------------------------

_SECRET = "test-secret-at-least-32-chars-long-x"
_ALGORITHM = "HS256"
_ISSUER = "wmp"
_AUDIENCE = "wmp-web"


def _make_jwt(
    *,
    sub: str,
    email: str,
    workspace_id: str | None,
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    payload = {
        "sub": sub,
        "email": email,
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "exp": int(time.time()) + int(exp_delta.total_seconds()),
    }
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    return jose_jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


# ---------------------------------------------------------------------------
# Import the module under test after helpers are defined
# ---------------------------------------------------------------------------

from apps.mcp_server.server import load_auth_context_from_env  # noqa: E402


class TestLoadAuthContextFromEnv:
    """load_auth_context_from_env() must parse JWT and return (workspace_id, user_id)."""

    def test_returns_workspace_id_and_user_id_from_valid_token(self) -> None:
        ws_id = uuid4()
        user_id = uuid4()
        token = _make_jwt(sub=str(user_id), email="x@example.com", workspace_id=str(ws_id))

        with patch.dict(os.environ, {"MCP_TOKEN": token, "AUTH_JWT_SECRET": _SECRET}):
            result_ws, result_user = load_auth_context_from_env()
            assert result_ws == ws_id
            assert result_user == user_id

    def test_workspace_id_matches_token_not_a_fresh_uuid4(self) -> None:
        """The returned workspace_id must equal the one in the token, not a new uuid4."""
        ws_id = uuid4()
        user_id = uuid4()
        token = _make_jwt(sub=str(user_id), email="x@example.com", workspace_id=str(ws_id))

        with patch.dict(os.environ, {"MCP_TOKEN": token, "AUTH_JWT_SECRET": _SECRET}):
            r1_ws, _ = load_auth_context_from_env()
            r2_ws, _ = load_auth_context_from_env()
            # Both calls return the same workspace_id (from token), not fresh uuids
            assert r1_ws == ws_id
            assert r2_ws == ws_id
            assert r1_ws == r2_ws

    def test_raises_when_mcp_token_env_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_TOKEN", None)
            with pytest.raises(OSError, match="MCP_TOKEN"):
                load_auth_context_from_env()

    def test_raises_when_token_is_expired(self) -> None:
        ws_id = uuid4()
        user_id = uuid4()
        token = _make_jwt(
            sub=str(user_id),
            email="x@example.com",
            workspace_id=str(ws_id),
            exp_delta=timedelta(seconds=-10),  # already expired
        )

        with patch.dict(os.environ, {"MCP_TOKEN": token, "AUTH_JWT_SECRET": _SECRET}):
            with pytest.raises(ValueError, match="[Ee]xpir"):
                load_auth_context_from_env()

    def test_raises_when_token_signature_invalid(self) -> None:
        ws_id = uuid4()
        user_id = uuid4()
        token = _make_jwt(sub=str(user_id), email="x@example.com", workspace_id=str(ws_id))
        bad_token = token[:-4] + "XXXX"  # corrupt signature

        with patch.dict(os.environ, {"MCP_TOKEN": bad_token, "AUTH_JWT_SECRET": _SECRET}):
            with pytest.raises(ValueError, match="[Ii]nvalid"):
                load_auth_context_from_env()

    def test_raises_when_workspace_id_missing_from_token(self) -> None:
        user_id = uuid4()
        token = _make_jwt(
            sub=str(user_id), email="x@example.com", workspace_id=None
        )  # no workspace_id claim

        with patch.dict(os.environ, {"MCP_TOKEN": token, "AUTH_JWT_SECRET": _SECRET}):
            with pytest.raises(ValueError, match="workspace_id"):
                load_auth_context_from_env()


class TestCreateMcpServerUsesAuthContext:
    """create_mcp_server() must pass the real workspace_id to tool handlers."""

    def test_handle_call_tool_uses_token_workspace_not_uuid4(self) -> None:
        """_handle_tool_call must be called with the token's workspace_id, not a fresh one."""
        from apps.mcp_server.server import _resolve_auth_context

        ws_id = uuid4()
        user_id = uuid4()
        token = _make_jwt(sub=str(user_id), email="x@example.com", workspace_id=str(ws_id))

        with patch.dict(os.environ, {"MCP_TOKEN": token, "AUTH_JWT_SECRET": _SECRET}):
            result_ws, result_user = _resolve_auth_context()
            assert result_ws == ws_id
            assert result_user == user_id

    def test_resolve_auth_context_called_once_at_server_startup(self) -> None:
        """create_mcp_server() resolves auth context once at startup, not per call."""
        from apps.mcp_server.server import _resolve_auth_context, create_mcp_server

        ws_id = uuid4()
        user_id = uuid4()
        token = _make_jwt(sub=str(user_id), email="x@example.com", workspace_id=str(ws_id))

        with patch.dict(os.environ, {"MCP_TOKEN": token, "AUTH_JWT_SECRET": _SECRET}):
            with patch(
                "apps.mcp_server.server._resolve_auth_context", wraps=_resolve_auth_context
            ) as mock_resolve:
                create_mcp_server()
                # _resolve_auth_context was called exactly once (at startup)
                assert mock_resolve.call_count == 1
