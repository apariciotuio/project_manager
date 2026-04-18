"""Fake GoogleOAuthAdapter — in-memory, no HTTP."""

from __future__ import annotations

from urllib.parse import urlencode

from app.infrastructure.adapters.google_oauth_adapter import (
    GoogleClaims,
)


class FakeGoogleOAuthAdapter:
    """Drop-in replacement for `GoogleOAuthAdapter` in unit tests."""

    def __init__(
        self,
        *,
        claims: GoogleClaims | None = None,
        raise_on_exchange: Exception | None = None,
    ) -> None:
        self._claims = claims or GoogleClaims(
            sub="fake-sub",
            email="fake@tuio.com",
            name="Fake User",
            picture=None,
        )
        self._raise = raise_on_exchange
        self.exchange_calls: list[tuple[str, str]] = []

    def get_authorization_url(self, *, state: str, challenge: str) -> str:
        qs = urlencode(
            {
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": "openid email profile",
            }
        )
        return f"https://accounts.google.com/fake?{qs}"

    async def exchange_code(
        self,
        *,
        code: str,
        verifier: str,
        http_transport=None,  # noqa: ARG002 — unused, mirrors real signature
    ) -> GoogleClaims:
        self.exchange_calls.append((code, verifier))
        if self._raise:
            raise self._raise
        return self._claims

    def with_claims(self, claims: GoogleClaims) -> FakeGoogleOAuthAdapter:
        self._claims = claims
        return self
