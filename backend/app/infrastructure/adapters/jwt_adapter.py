"""JWT adapter — wraps python-jose with typed errors.

EP-00 AD-01: HS256, stateless access tokens, short TTL. Refresh tokens are opaque
(stored in `sessions`), not JWTs.
"""

from __future__ import annotations

from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt


class TokenExpiredError(Exception):
    """JWT's `exp` claim is in the past."""


class TokenInvalidError(Exception):
    """Signature mismatch, malformed token, or missing required claim."""


class JwtAdapter:
    def __init__(
        self,
        *,
        secret: str,
        algorithm: str = "HS256",
        issuer: str = "wmp",
        audience: str = "wmp-web",
    ) -> None:
        if not secret or len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 bytes")
        self._secret = secret
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience

    def encode(self, payload: dict[str, Any]) -> str:
        stamped = {**payload, "iss": self._issuer, "aud": self._audience}
        token: str = jwt.encode(stamped, self._secret, algorithm=self._algorithm)
        return token

    def decode(self, token: str) -> dict[str, Any]:
        try:
            decoded: dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require_exp": True},
                audience=self._audience,
                issuer=self._issuer,
            )
            return decoded
        except ExpiredSignatureError as exc:
            raise TokenExpiredError(str(exc)) from exc
        except JWTError as exc:
            raise TokenInvalidError(str(exc)) from exc
