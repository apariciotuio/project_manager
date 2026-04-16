"""GoogleOAuthAdapter unit tests — httpx mocked, no real Google calls."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.infrastructure.adapters.google_oauth_adapter import (
    GoogleClaims,
    GoogleOAuthAdapter,
    OAuthExchangeError,
)


@pytest.fixture
def adapter() -> GoogleOAuthAdapter:
    return GoogleOAuthAdapter(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost:17004/api/v1/auth/google/callback",
    )


class TestAuthorizationUrl:
    def test_contains_required_params(self, adapter: GoogleOAuthAdapter) -> None:
        url = adapter.get_authorization_url(state="st-1", challenge="ch-1")
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        assert parsed.netloc == "accounts.google.com"
        assert qs["response_type"] == ["code"]
        assert qs["client_id"] == ["client-id"]
        assert qs["state"] == ["st-1"]
        assert qs["code_challenge"] == ["ch-1"]
        assert qs["code_challenge_method"] == ["S256"]
        assert "openid" in qs["scope"][0]
        assert "email" in qs["scope"][0]
        assert "profile" in qs["scope"][0]


class TestExchangeCode:
    async def test_happy_path_returns_claims(self, adapter: GoogleOAuthAdapter) -> None:
        # id_token with pre-computed HS256 disabled: our adapter trusts the token
        # endpoint response since HTTPS + client secret guarantees authenticity.
        # We mock both /token and /oauth2/v3/tokeninfo (Google's verification endpoint).
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "at",
                        "id_token": "id-token-string",
                        "expires_in": 3600,
                        "token_type": "Bearer",
                    },
                )
            if request.url.path == "/tokeninfo":
                return httpx.Response(
                    200,
                    json={
                        "sub": "google-sub-1",
                        "email": "alice@tuio.com",
                        "email_verified": "true",
                        "name": "Alice",
                        "picture": "https://example.com/a.png",
                        "aud": "client-id",
                        "iss": "accounts.google.com",
                        "exp": str(int(__import__("time").time()) + 3600),
                    },
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        claims = await adapter.exchange_code(
            code="auth-code", verifier="verifier-1", http_transport=transport
        )
        assert isinstance(claims, GoogleClaims)
        assert claims.sub == "google-sub-1"
        assert claims.email == "alice@tuio.com"
        assert claims.name == "Alice"
        assert claims.picture == "https://example.com/a.png"

    async def test_non_2xx_from_token_endpoint_raises(self, adapter: GoogleOAuthAdapter) -> None:
        transport = httpx.MockTransport(
            lambda _: httpx.Response(400, json={"error": "invalid_grant"})
        )
        with pytest.raises(OAuthExchangeError, match="400"):
            await adapter.exchange_code(
                code="bad", verifier="v", http_transport=transport
            )

    async def test_tokeninfo_audience_mismatch_raises(self, adapter: GoogleOAuthAdapter) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "x",
                    "email": "e@tuio.com",
                    "name": "X",
                    "aud": "someone-else",  # ← wrong audience
                    "iss": "accounts.google.com",
                    "exp": str(int(__import__("time").time()) + 3600),
                },
            )

        with pytest.raises(OAuthExchangeError, match="audience"):
            await adapter.exchange_code(
                code="c", verifier="v", http_transport=httpx.MockTransport(handler)
            )

    async def test_email_not_verified_raises(self, adapter: GoogleOAuthAdapter) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "x",
                    "email": "e@tuio.com",
                    "email_verified": "false",
                    "name": "X",
                    "aud": "client-id",
                    "iss": "accounts.google.com",
                    "exp": str(int(__import__("time").time()) + 3600),
                },
            )

        with pytest.raises(OAuthExchangeError, match="email"):
            await adapter.exchange_code(
                code="c", verifier="v", http_transport=httpx.MockTransport(handler)
            )

    async def test_email_verified_missing_defaults_to_rejected(
        self, adapter: GoogleOAuthAdapter
    ) -> None:
        """email_verified absent must default to rejected (fail-closed), not trusted."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "x",
                    "email": "e@tuio.com",
                    # email_verified intentionally absent
                    "name": "X",
                    "aud": "client-id",
                    "iss": "accounts.google.com",
                    "exp": str(int(__import__("time").time()) + 3600),
                },
            )

        with pytest.raises(OAuthExchangeError, match="email"):
            await adapter.exchange_code(
                code="c", verifier="v", http_transport=httpx.MockTransport(handler)
            )

    async def test_invalid_issuer_raises(self, adapter: GoogleOAuthAdapter) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "x",
                    "email": "e@tuio.com",
                    "email_verified": "true",
                    "name": "X",
                    "aud": "client-id",
                    "iss": "evil.com",
                    "exp": str(int(__import__("time").time()) + 3600),
                },
            )

        with pytest.raises(OAuthExchangeError, match="invalid_id_token"):
            await adapter.exchange_code(
                code="c", verifier="v", http_transport=httpx.MockTransport(handler)
            )

    async def test_missing_issuer_raises(self, adapter: GoogleOAuthAdapter) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "x",
                    "email": "e@tuio.com",
                    "email_verified": "true",
                    "name": "X",
                    "aud": "client-id",
                    # iss missing
                    "exp": str(int(__import__("time").time()) + 3600),
                },
            )

        with pytest.raises(OAuthExchangeError, match="invalid_id_token"):
            await adapter.exchange_code(
                code="c", verifier="v", http_transport=httpx.MockTransport(handler)
            )

    async def test_expired_token_raises(self, adapter: GoogleOAuthAdapter) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "x",
                    "email": "e@tuio.com",
                    "email_verified": "true",
                    "name": "X",
                    "aud": "client-id",
                    "iss": "accounts.google.com",
                    "exp": str(int(__import__("time").time()) - 1),  # already expired
                },
            )

        with pytest.raises(OAuthExchangeError, match="expired"):
            await adapter.exchange_code(
                code="c", verifier="v", http_transport=httpx.MockTransport(handler)
            )

    async def test_wrong_aud_raises(self, adapter: GoogleOAuthAdapter) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "x",
                    "email": "e@tuio.com",
                    "email_verified": "true",
                    "name": "X",
                    "aud": "different-client",
                    "iss": "accounts.google.com",
                    "exp": str(int(__import__("time").time()) + 3600),
                },
            )

        with pytest.raises(OAuthExchangeError, match="audience"):
            await adapter.exchange_code(
                code="c", verifier="v", http_transport=httpx.MockTransport(handler)
            )

    async def test_email_verified_bool_true_accepted(
        self, adapter: GoogleOAuthAdapter
    ) -> None:
        """id_token payload returns bool True (not string) — must be accepted."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/token":
                return httpx.Response(
                    200,
                    json={"access_token": "at", "id_token": "tok", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "sub": "google-sub-bool",
                    "email": "bool@tuio.com",
                    "email_verified": True,  # bool, not string
                    "name": "Bool User",
                    "picture": None,
                    "aud": "client-id",
                    "iss": "accounts.google.com",
                    "exp": int(__import__("time").time()) + 3600,
                },
            )

        claims = await adapter.exchange_code(
            code="c", verifier="v", http_transport=httpx.MockTransport(handler)
        )
        assert claims.email == "bool@tuio.com"
