"""Cursor pagination helper — HMAC-signed, base64url-encoded cursors.

Usage:
    token = encode_cursor({"last_sort_value": "2024-01-15", "last_id": "uuid..."})
    payload = decode_cursor(token)  # None if tampered or missing

Token format: <base64url(json_body)>.<base64url(hmac8)>

The 8-byte HMAC suffix (64-bit) is not collision-resistant enough for long-lived
tokens, but it IS sufficient to prevent casual tampering with pagination cursors.
Cursors are short-lived (one page load) and carry no privilege — 64 bits is fine.

Signing key: settings.auth.jwt_secret (already a required secret — no new config needed).

This module is consumed by:
  - timeline list
  - work-item list
  - notifications list
  - versions list
  - audit log list
  - any other list endpoint that switches to cursor pagination (EP-12 MUST-FIX)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

_SIG_BYTES = 8


def _secret() -> bytes:
    # Defer import to avoid lru_cache trap at module load time (see project memory).
    return get_settings().auth.jwt_secret.encode()


def _sign(body: str) -> str:
    raw_sig = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()[:_SIG_BYTES]
    return base64.urlsafe_b64encode(raw_sig).rstrip(b"=").decode()


def encode_cursor(payload: dict[str, object]) -> str:
    """Encode a dict into a signed cursor token.

    Args:
        payload: Arbitrary JSON-serialisable dict. Typically
                 ``{"last_sort_value": ..., "last_id": ...}``.

    Returns:
        URL-safe string suitable for inclusion in a response ``pagination.cursor`` field.
    """
    body = (
        base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).rstrip(b"=").decode()
    )
    sig = _sign(body)
    return f"{body}.{sig}"


def decode_cursor(token: str | None) -> dict[str, object] | None:
    """Decode and verify a cursor token.

    Args:
        token: Value from the client ``?cursor=`` query parameter.

    Returns:
        The original payload dict, or ``None`` if the token is missing,
        malformed, or has been tampered with.
    """
    if not token:
        return None

    parts = token.rsplit(".", 1)
    if len(parts) != 2:
        return None

    body, claimed_sig = parts

    # Reject tokens with extra dots (e.g. "a.b.c" — rsplit gives ["a.b", "c"])
    # If body itself contains a dot that's fine — rsplit(1) handles it correctly.
    # But if claimed_sig contains a dot, the format is wrong.
    if "." in claimed_sig:
        return None

    expected_sig = _sign(body)
    if not hmac.compare_digest(expected_sig, claimed_sig):
        logger.debug("cursor signature mismatch — possible tamper")
        return None

    try:
        padded = body + "=" * (-len(body) % 4)
        raw = base64.urlsafe_b64decode(padded)
        decoded: dict[str, object] = json.loads(raw)
        return decoded
    except Exception:
        logger.debug("cursor body decode failed")
        return None
