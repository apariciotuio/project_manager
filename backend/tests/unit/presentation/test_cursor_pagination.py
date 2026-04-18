"""Unit tests for cursor pagination helper — RED phase."""

from __future__ import annotations

import base64
import json

from app.presentation.pagination.cursor import decode_cursor, encode_cursor

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_round_trip_preserves_values() -> None:
    """encode → decode returns the original data unchanged."""
    payload = {
        "last_sort_value": "2024-01-15T10:00:00",
        "last_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    token = encode_cursor(payload)
    result = decode_cursor(token)
    assert result == payload


def test_decode_returns_none_on_empty_string() -> None:
    """decode_cursor(None) and decode_cursor('') both return None."""
    assert decode_cursor(None) is None
    assert decode_cursor("") is None


def test_decode_returns_none_on_tampered_signature() -> None:
    """A cursor with a modified signature is rejected (returns None)."""
    payload = {"last_id": "abc123", "last_sort_value": "x"}
    token = encode_cursor(payload)
    # Flip one character in the signature (last 12 chars are the sig)
    tampered = token[:-12] + ("A" if token[-12] != "A" else "B") + token[-11:]
    assert decode_cursor(tampered) is None


def test_decode_returns_none_on_tampered_body() -> None:
    """A cursor with a modified body (but intact sig) is rejected."""
    payload = {"last_id": "original", "last_sort_value": "v"}
    token = encode_cursor(payload)
    # The token format is <base64url_body>.<base64url_sig>
    parts = token.rsplit(".", 1)
    assert len(parts) == 2
    # Corrupt the body
    fake_body = (
        base64.urlsafe_b64encode(json.dumps({"last_id": "evil"}).encode()).rstrip(b"=").decode()
    )
    tampered = f"{fake_body}.{parts[1]}"
    assert decode_cursor(tampered) is None


def test_decode_returns_none_on_missing_separator() -> None:
    """Token without a dot separator is rejected."""
    assert decode_cursor("notavalidtokenatall") is None


def test_decode_returns_none_on_malformed_json() -> None:
    """Token with non-JSON body is rejected."""
    import hashlib
    import hmac

    from app.config.settings import get_settings

    secret = get_settings().auth.jwt_secret.encode()
    bad_body = base64.urlsafe_b64encode(b"not json").rstrip(b"=").decode()
    sig = hmac.new(secret, bad_body.encode(), hashlib.sha256).digest()[:8]
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    token = f"{bad_body}.{sig_b64}"
    assert decode_cursor(token) is None


def test_encode_produces_dot_separated_token() -> None:
    """Encoded cursor has exactly one '.' separator between body and signature."""
    payload = {"last_id": "x", "last_sort_value": "y"}
    token = encode_cursor(payload)
    assert token.count(".") == 1


def test_different_payloads_produce_different_tokens() -> None:
    """Two distinct payloads must not produce the same token."""
    t1 = encode_cursor({"last_id": "a", "last_sort_value": "1"})
    t2 = encode_cursor({"last_id": "b", "last_sort_value": "2"})
    assert t1 != t2


def test_decode_returns_none_on_completely_random_garbage() -> None:
    """Random garbage returns None, no exceptions."""
    assert decode_cursor("!!!garbage!!!") is None
    assert decode_cursor("a.b.c") is None
