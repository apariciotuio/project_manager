"""Jira HTTP adapter — PAT-authenticated, httpx-based.

Scope: single-issue creation for MVP export flow (EP-11).
Retry policy: up to 2 retries on 5xx with exponential backoff (1s, 2s).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_TIMEOUT_SECONDS = 30.0


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class JiraError(Exception):
    """Base class for all Jira adapter errors."""


class JiraValidationError(JiraError):
    """HTTP 400 or 422 — bad request body; caller owns diagnosis."""

    def __init__(self, raw_body: str) -> None:
        self.raw_body = raw_body
        super().__init__(f"Jira validation error: {raw_body}")


class JiraAuthError(JiraError):
    """HTTP 401 or 403 — bad credentials or insufficient permissions."""


class JiraRateLimited(JiraError):
    """HTTP 429 — caller should back off."""

    def __init__(self, retry_after: int | None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Jira rate limited; retry_after={retry_after}")


class JiraUnavailable(JiraError):
    """5xx after all retries exhausted."""


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JiraIssue:
    key: str
    self_url: str
    id: str


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _build_adf(text: str) -> dict[str, Any]:
    """Wrap plain text as Atlassian Document Format paragraph."""
    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


class JiraClient:
    """Minimal Jira Cloud client for issue creation.

    Args:
        base_url:    e.g. "https://yourorg.atlassian.net"
        email:       Atlassian account email (used in Basic Auth username)
        api_token:   Atlassian API token (PAT)
        _transport:  Injected transport for testing (httpx.MockTransport)
        _retry_sleep: Set to False in tests to skip asyncio.sleep delays
    """

    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        api_token: str,
        _transport: httpx.MockTransport | None = None,
        _retry_sleep: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(email, api_token)
        self._transport = _transport
        self._retry_sleep = _retry_sleep

    def _build_client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {
            "auth": self._auth,
            "timeout": _TIMEOUT_SECONDS,
            "headers": {"Accept": "application/json", "Content-Type": "application/json"},
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    async def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str,
        project_key: str,
        labels: list[str] | None = None,
    ) -> JiraIssue:
        """POST /rest/api/3/issue and return a JiraIssue on HTTP 201.

        Raises:
            JiraValidationError:  400/422
            JiraAuthError:        401/403
            JiraRateLimited:      429
            JiraUnavailable:      5xx after retries
        """
        url = f"{self._base_url}/rest/api/3/issue"
        body: dict[str, Any] = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": _build_adf(description),
                "issuetype": {"name": issue_type},
            }
        }
        if labels:
            body["fields"]["labels"] = labels

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._post(url, body)
            except JiraUnavailable as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    delay = 2**attempt  # 1s, 2s
                    logger.warning(
                        "Jira 5xx on attempt %d/%d; retrying in %ds",
                        attempt + 1,
                        _MAX_RETRIES + 1,
                        delay,
                    )
                    if self._retry_sleep:
                        await asyncio.sleep(delay)
                    continue
                raise
            else:
                return response

        # mypy: last_exc is set if we reach here
        raise last_exc  # type: ignore[misc]

    async def _post(self, url: str, body: dict[str, Any]) -> JiraIssue:
        async with self._build_client() as client:
            resp = await client.post(url, json=body)

        status = resp.status_code
        raw = resp.text

        if status == 201:
            data = resp.json()
            return JiraIssue(
                key=data["key"],
                self_url=data["self"],
                id=str(data["id"]),
            )

        if status in (400, 422):
            raise JiraValidationError(raw)

        if status in (401, 403):
            raise JiraAuthError(f"HTTP {status}: {raw}")

        if status == 429:
            retry_after_raw = resp.headers.get("Retry-After")
            retry_after = int(retry_after_raw) if retry_after_raw else None
            raise JiraRateLimited(retry_after)

        if status >= 500:
            raise JiraUnavailable(f"HTTP {status}: {raw}")

        raise JiraError(f"Unexpected Jira response: HTTP {status}: {raw}")
