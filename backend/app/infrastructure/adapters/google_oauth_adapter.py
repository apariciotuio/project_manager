"""Google OAuth adapter — authorization URL + token exchange.

Uses Google's `tokeninfo` endpoint to verify the ID token server-side. This avoids
pulling in JWKS and RSA verification just for auth bootstrap. Trust anchor is HTTPS
+ the `aud` claim matching our own `client_id`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"
_SCOPES = "openid email profile"
_VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class OAuthExchangeError(Exception):
    """Google token exchange or ID-token verification failed."""


@dataclass(frozen=True)
class GoogleClaims:
    sub: str
    email: str
    name: str
    picture: str | None


class GoogleOAuthAdapter:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def get_authorization_url(self, *, state: str, challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": _SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_AUTH_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(
        self,
        *,
        code: str,
        verifier: str,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> GoogleClaims:
        async with httpx.AsyncClient(transport=http_transport, timeout=10.0) as client:
            token_resp = await client.post(
                _TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": self._redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
            if token_resp.status_code >= 400:
                raise OAuthExchangeError(
                    f"Google token endpoint returned {token_resp.status_code}"
                )
            token_data = token_resp.json()
            id_token = token_data.get("id_token")
            if not id_token:
                raise OAuthExchangeError("Google response missing id_token")

            info_resp = await client.get(
                _TOKENINFO_ENDPOINT, params={"id_token": id_token}
            )
            if info_resp.status_code >= 400:
                raise OAuthExchangeError(
                    f"Google tokeninfo returned {info_resp.status_code}"
                )
            info = info_resp.json()

        # --- validate token claims ---

        # iss must be one of the known Google issuers
        iss = info.get("iss")
        if iss not in _VALID_ISSUERS:
            raise OAuthExchangeError(
                f"invalid_id_token: unexpected issuer {iss!r}"
            )

        # aud must match our client_id
        if info.get("aud") != self._client_id:
            raise OAuthExchangeError(
                f"id_token audience mismatch: got {info.get('aud')!r}"
            )

        # exp must be in the future
        exp = info.get("exp")
        try:
            if int(exp) <= int(time.time()):
                raise OAuthExchangeError("invalid_id_token: token has expired")
        except (TypeError, ValueError) as exc:
            raise OAuthExchangeError("invalid_id_token: missing or invalid exp claim") from exc

        # email_verified — accept both string "true" and bool True; default to "false"
        raw_verified = info.get("email_verified", "false")
        if isinstance(raw_verified, bool):
            verified = raw_verified
        else:
            verified = str(raw_verified).lower() == "true"
        if not verified:
            raise OAuthExchangeError("Google email not verified")

        email = info.get("email")
        sub = info.get("sub")
        name = info.get("name")
        if not sub or not email or not name:
            raise OAuthExchangeError("Google response missing required claim")

        return GoogleClaims(
            sub=sub,
            email=email,
            name=name,
            picture=info.get("picture"),
        )
