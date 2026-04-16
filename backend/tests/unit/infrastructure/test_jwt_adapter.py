"""JwtAdapter unit tests — HS256 encode/decode + tamper detection."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from app.infrastructure.adapters.jwt_adapter import (
    JwtAdapter,
    TokenExpiredError,
    TokenInvalidError,
)

SECRET = "a-test-secret-32-bytes-long-abcd"


@pytest.fixture
def adapter() -> JwtAdapter:
    return JwtAdapter(
        secret=SECRET,
        algorithm="HS256",
        issuer="wmp",
        audience="wmp-web",
    )


def test_encode_decode_roundtrip(adapter: JwtAdapter) -> None:
    claims = {
        "sub": "user-123",
        "email": "a@tuio.com",
        "workspace_id": "ws-1",
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    token = adapter.encode(claims)
    decoded = adapter.decode(token)
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "a@tuio.com"
    assert decoded["workspace_id"] == "ws-1"


def test_decode_rejects_tampered_signature(adapter: JwtAdapter) -> None:
    token = adapter.encode(
        {"sub": "u", "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp())}
    )
    tampered = token[:-4] + "XXXX"
    with pytest.raises(TokenInvalidError):
        adapter.decode(tampered)


def test_decode_rejects_expired_token(adapter: JwtAdapter) -> None:
    past = int((datetime.now(timezone.utc) - timedelta(seconds=10)).timestamp())
    token = adapter.encode({"sub": "u", "exp": past})
    with pytest.raises(TokenExpiredError):
        adapter.decode(token)


def test_decode_rejects_token_signed_with_different_secret(adapter: JwtAdapter) -> None:
    other = JwtAdapter(
        secret="completely-different-32b-secret-x",
        algorithm="HS256",
        issuer="wmp",
        audience="wmp-web",
    )
    token = other.encode(
        {"sub": "u", "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())}
    )
    with pytest.raises(TokenInvalidError):
        adapter.decode(token)


def test_decode_rejects_malformed_token(adapter: JwtAdapter) -> None:
    with pytest.raises(TokenInvalidError):
        adapter.decode("not-a-jwt")


def test_encode_requires_exp_claim(adapter: JwtAdapter) -> None:
    # By convention, callers must set `exp`. Decode of a tokenless of `exp` should
    # still succeed (python-jose doesn't enforce exp by default) — this test just
    # guards that we DO enforce it at decode time.
    token = adapter.encode({"sub": "u"})
    # Default decode rejects missing exp in our adapter.
    with pytest.raises(TokenInvalidError):
        adapter.decode(token)


def test_near_expiry_boundary(adapter: JwtAdapter) -> None:
    # Token that expires in 1 second — sleep 2s — must raise expired.
    soon = int(time.time()) + 1
    token = adapter.encode({"sub": "u", "exp": soon})
    time.sleep(2)
    with pytest.raises(TokenExpiredError):
        adapter.decode(token)


# ---------------------------------------------------------------------------
# iss / aud enforcement
# ---------------------------------------------------------------------------


def _future_exp() -> int:
    return int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())


def test_encode_stamps_iss_and_aud(adapter: JwtAdapter) -> None:
    token = adapter.encode({"sub": "u", "exp": _future_exp()})
    decoded = adapter.decode(token)
    assert decoded["iss"] == "wmp"
    assert decoded["aud"] == "wmp-web"


def test_decode_rejects_wrong_issuer(adapter: JwtAdapter) -> None:
    wrong_iss = JwtAdapter(
        secret=SECRET,
        algorithm="HS256",
        issuer="evil-iss",
        audience="wmp-web",
    )
    token = wrong_iss.encode({"sub": "u", "exp": _future_exp()})
    with pytest.raises(TokenInvalidError):
        adapter.decode(token)


def test_decode_rejects_wrong_audience(adapter: JwtAdapter) -> None:
    wrong_aud = JwtAdapter(
        secret=SECRET,
        algorithm="HS256",
        issuer="wmp",
        audience="wrong-audience",
    )
    token = wrong_aud.encode({"sub": "u", "exp": _future_exp()})
    with pytest.raises(TokenInvalidError):
        adapter.decode(token)


def test_roundtrip_with_custom_iss_aud() -> None:
    custom = JwtAdapter(
        secret=SECRET,
        algorithm="HS256",
        issuer="custom-svc",
        audience="custom-client",
    )
    token = custom.encode({"sub": "u", "exp": _future_exp()})
    decoded = custom.decode(token)
    assert decoded["iss"] == "custom-svc"
    assert decoded["aud"] == "custom-client"
