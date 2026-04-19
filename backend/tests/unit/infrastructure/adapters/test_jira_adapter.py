"""Unit tests for JiraClient — RED phase.

Uses httpx.MockTransport to avoid network calls.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.infrastructure.adapters.jira_adapter import (
    JiraAuthError,
    JiraClient,
    JiraIssue,
    JiraRateLimited,
    JiraUnavailable,
    JiraValidationError,
)


def _mock_transport(status_code: int, body: dict | str, headers: dict | None = None) -> httpx.MockTransport:
    """Build a synchronous mock transport that returns a fixed response."""
    raw = json.dumps(body) if isinstance(body, dict) else body
    _headers = {"Content-Type": "application/json", **(headers or {})}

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            content=raw.encode(),
            headers=_headers,
        )

    return httpx.MockTransport(_handler)


def _make_client(transport: httpx.MockTransport) -> JiraClient:
    return JiraClient(
        base_url="https://example.atlassian.net",
        email="user@example.com",
        api_token="token123",
        _transport=transport,
    )


# ---------------------------------------------------------------------------
# 201 — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_201_returns_jira_issue() -> None:
    transport = _mock_transport(
        201,
        {"id": "10001", "key": "PROJ-42", "self": "https://example.atlassian.net/rest/api/3/issue/10001"},
    )
    client = _make_client(transport)

    result = await client.create_issue(
        summary="Fix the thing",
        description="Broken in prod.",
        issue_type="Bug",
        project_key="PROJ",
        labels=["backend"],
    )

    assert isinstance(result, JiraIssue)
    assert result.key == "PROJ-42"
    assert result.id == "10001"
    assert "PROJ-42" in result.self_url or "10001" in result.self_url


# ---------------------------------------------------------------------------
# 400 — validation error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_400_raises_validation_error() -> None:
    body = {"errorMessages": [], "errors": {"summary": "Field required"}}
    transport = _mock_transport(400, body)
    client = _make_client(transport)

    with pytest.raises(JiraValidationError) as exc_info:
        await client.create_issue(
            summary="",
            description="",
            issue_type="Bug",
            project_key="PROJ",
        )

    assert "summary" in str(exc_info.value).lower() or exc_info.value.raw_body


# ---------------------------------------------------------------------------
# 422 — also validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_422_raises_validation_error() -> None:
    body = {"errorMessages": ["Invalid issue type"], "errors": {}}
    transport = _mock_transport(422, body)
    client = _make_client(transport)

    with pytest.raises(JiraValidationError):
        await client.create_issue(
            summary="Title",
            description="desc",
            issue_type="NonExistent",
            project_key="PROJ",
        )


# ---------------------------------------------------------------------------
# 401/403 — auth errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_401_raises_auth_error() -> None:
    transport = _mock_transport(401, {"message": "Unauthorized"})
    client = _make_client(transport)

    with pytest.raises(JiraAuthError):
        await client.create_issue("T", "D", "Task", "PROJ")


@pytest.mark.asyncio
async def test_create_issue_403_raises_auth_error() -> None:
    transport = _mock_transport(403, {"message": "Forbidden"})
    client = _make_client(transport)

    with pytest.raises(JiraAuthError):
        await client.create_issue("T", "D", "Task", "PROJ")


# ---------------------------------------------------------------------------
# 429 — rate limited
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_429_raises_rate_limited_with_retry_after() -> None:
    transport = _mock_transport(429, {"message": "rate limit"}, headers={"Retry-After": "30"})
    client = _make_client(transport)

    with pytest.raises(JiraRateLimited) as exc_info:
        await client.create_issue("T", "D", "Task", "PROJ")

    assert exc_info.value.retry_after == 30


@pytest.mark.asyncio
async def test_create_issue_429_no_retry_after_header() -> None:
    transport = _mock_transport(429, {"message": "rate limit"})
    client = _make_client(transport)

    with pytest.raises(JiraRateLimited) as exc_info:
        await client.create_issue("T", "D", "Task", "PROJ")

    assert exc_info.value.retry_after is None


# ---------------------------------------------------------------------------
# 5xx — server errors with retry logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_5xx_retries_twice_then_raises_unavailable() -> None:
    """Three 500 responses in a row → JiraUnavailable after 2 retries."""
    call_count = 0

    def _always_500(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            500,
            content=b'{"message":"internal"}',
            headers={"Content-Type": "application/json"},
        )

    client = JiraClient(
        base_url="https://example.atlassian.net",
        email="user@example.com",
        api_token="token123",
        _transport=httpx.MockTransport(_always_500),
        _retry_sleep=False,  # skip actual sleep in tests
    )

    with pytest.raises(JiraUnavailable):
        await client.create_issue("T", "D", "Task", "PROJ")

    # initial attempt + 2 retries = 3 total
    assert call_count == 3


@pytest.mark.asyncio
async def test_create_issue_5xx_succeeds_on_second_attempt() -> None:
    """First 500, then 201 — should return JiraIssue."""
    call_count = 0

    def _flaky(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                500,
                content=b'{"message":"oops"}',
                headers={"Content-Type": "application/json"},
            )
        return httpx.Response(
            201,
            content=json.dumps({
                "id": "10001",
                "key": "PROJ-1",
                "self": "https://example.atlassian.net/rest/api/3/issue/10001",
            }).encode(),
            headers={"Content-Type": "application/json"},
        )

    client = JiraClient(
        base_url="https://example.atlassian.net",
        email="user@example.com",
        api_token="token123",
        _transport=httpx.MockTransport(_flaky),
        _retry_sleep=False,
    )

    result = await client.create_issue("T", "D", "Task", "PROJ")
    assert result.key == "PROJ-1"
    assert call_count == 2


# ---------------------------------------------------------------------------
# ADF body construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_sends_adf_description() -> None:
    """Verifies the request body wraps description as ADF paragraph block."""
    captured_body: dict | None = None

    def _capture(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content)
        return httpx.Response(
            201,
            content=json.dumps({
                "id": "1",
                "key": "X-1",
                "self": "https://x.atlassian.net/rest/api/3/issue/1",
            }).encode(),
            headers={"Content-Type": "application/json"},
        )

    client = JiraClient(
        base_url="https://example.atlassian.net",
        email="user@example.com",
        api_token="token123",
        _transport=httpx.MockTransport(_capture),
    )
    await client.create_issue("My title", "Plain text desc", "Story", "PROJ", labels=["tag1"])

    assert captured_body is not None
    fields = captured_body["fields"]
    assert fields["summary"] == "My title"
    assert fields["issuetype"] == {"name": "Story"}
    assert fields["project"] == {"key": "PROJ"}
    assert fields["labels"] == ["tag1"]
    # ADF structure check
    desc = fields["description"]
    assert desc["type"] == "doc"
    assert desc["version"] == 1
    content = desc["content"]
    assert content[0]["type"] == "paragraph"
    assert content[0]["content"][0]["type"] == "text"
    assert content[0]["content"][0]["text"] == "Plain text desc"
