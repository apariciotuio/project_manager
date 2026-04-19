"""Unit tests for server.py — mcp_* opaque token acceptance via verify service.

Tests that _decode_token dispatches to _decode_mcp_opaque_token for mcp_* tokens.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.application.services.mcp_token_verify_service import (
    MCPTokenExpired,
    MCPTokenInvalid,
)

_WORKSPACE_ID = uuid4()
_USER_ID = uuid4()
_TOKEN_ID = uuid4()


def test_decode_token_dispatches_mcp_prefix_to_opaque_handler() -> None:
    """_decode_token with mcp_* prefix calls _decode_mcp_opaque_token, not JWT path."""
    import apps.mcp_server.server as srv

    expected = (_WORKSPACE_ID, _USER_ID)
    call_args: list[str] = []

    def _mock_opaque(token: str) -> tuple:
        call_args.append(token)
        return expected

    with patch.object(srv, "_decode_mcp_opaque_token", _mock_opaque):
        result = srv._decode_token("mcp_" + "a" * 43)

    assert result == expected
    assert len(call_args) == 1
    assert call_args[0].startswith("mcp_")


def test_decode_token_jwt_prefix_does_not_call_opaque_handler() -> None:
    """Non-mcp_* tokens do NOT call _decode_mcp_opaque_token."""
    import apps.mcp_server.server as srv

    call_count = 0

    def _mock_opaque(token: str) -> tuple:
        nonlocal call_count
        call_count += 1
        return (_WORKSPACE_ID, _USER_ID)

    with patch.object(srv, "_decode_mcp_opaque_token", _mock_opaque):
        try:
            srv._decode_token("not-a-mcp-token")
        except ValueError:
            pass  # expected — bad JWT

    assert call_count == 0


def test_decode_mcp_opaque_token_reraises_expired_as_value_error() -> None:
    """_decode_mcp_opaque_token wraps MCPTokenExpired in ValueError."""
    import apps.mcp_server.server as srv

    async def _raise_expired() -> tuple:
        raise MCPTokenExpired("token expired")

    with patch("apps.mcp_server.server.asyncio.run", side_effect=MCPTokenExpired("expired")):
        with pytest.raises(ValueError, match="expired"):
            srv._decode_mcp_opaque_token("mcp_" + "a" * 43)


def test_decode_mcp_opaque_token_reraises_invalid_as_value_error() -> None:
    """_decode_mcp_opaque_token wraps MCPTokenInvalid in ValueError."""
    import apps.mcp_server.server as srv

    with patch("apps.mcp_server.server.asyncio.run", side_effect=MCPTokenInvalid("bad token")):
        with pytest.raises(ValueError, match="invalid"):
            srv._decode_mcp_opaque_token("mcp_" + "a" * 43)
