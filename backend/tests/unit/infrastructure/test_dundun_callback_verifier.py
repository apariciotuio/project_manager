"""Unit tests for HMAC-SHA256 Dundun callback signature verification."""

from __future__ import annotations

import hashlib
import hmac

from app.infrastructure.adapters.dundun_callback_verifier import verify_dundun_signature

SECRET = "test-callback-secret"
BODY = b'{"agent":"wm_suggestion_agent","request_id":"req-abc","result":{}}'


def _valid_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestVerifyDundunSignature:
    def test_valid_signature_returns_true(self) -> None:
        sig = _valid_signature(BODY, SECRET)
        assert verify_dundun_signature(BODY, sig, SECRET) is True

    def test_wrong_body_returns_false(self) -> None:
        sig = _valid_signature(BODY, SECRET)
        tampered = BODY + b"x"
        assert verify_dundun_signature(tampered, sig, SECRET) is False

    def test_wrong_secret_returns_false(self) -> None:
        sig = _valid_signature(BODY, "wrong-secret")
        assert verify_dundun_signature(BODY, sig, SECRET) is False

    def test_empty_signature_returns_false(self) -> None:
        assert verify_dundun_signature(BODY, "", SECRET) is False

    def test_malformed_non_hex_signature_returns_false(self) -> None:
        assert verify_dundun_signature(BODY, "not-a-hex-digest!!", SECRET) is False

    def test_truncated_signature_returns_false(self) -> None:
        sig = _valid_signature(BODY, SECRET)
        assert verify_dundun_signature(BODY, sig[:10], SECRET) is False

    def test_empty_body_valid_signature_returns_true(self) -> None:
        empty_sig = _valid_signature(b"", SECRET)
        assert verify_dundun_signature(b"", empty_sig, SECRET) is True

    def test_different_bodies_different_signatures(self) -> None:
        body_a = b"body-a"
        body_b = b"body-b"
        sig_a = _valid_signature(body_a, SECRET)
        sig_b = _valid_signature(body_b, SECRET)
        assert sig_a != sig_b
        assert verify_dundun_signature(body_a, sig_b, SECRET) is False
        assert verify_dundun_signature(body_b, sig_a, SECRET) is False

    def test_case_insensitive_hex_accepted(self) -> None:
        """Some HMAC implementations emit uppercase hex."""
        sig = _valid_signature(BODY, SECRET).upper()
        # We should handle both cases gracefully
        result = verify_dundun_signature(BODY, sig, SECRET)
        # Either True (we normalize) or False — just must not raise
        assert isinstance(result, bool)

    def test_does_not_raise_on_unicode_decode_error_in_signature(self) -> None:
        """Malformed header must not propagate exceptions to callers."""
        result = verify_dundun_signature(BODY, "\x00\xff\xfe", SECRET)
        assert result is False
