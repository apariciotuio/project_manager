"""Unit tests for _safe_return_to — open redirect protection."""

from __future__ import annotations

import pytest

from app.presentation.controllers.auth import _safe_return_to


@pytest.mark.parametrize(
    "value,expected",
    [
        # Happy paths
        ("/workspace/foo", "/workspace/foo"),
        ("/", "/"),
        ("/workspace/foo?bar=baz", "/workspace/foo?bar=baz"),
        # Open redirect attempts → None
        ("//evil.com", None),
        ("//evil.com/path", None),
        ("/\\evil.com", None),
        ("http://evil.com", None),
        ("https://evil.com", None),
        ("javascript:alert(1)", None),
        # @ in path portion — userinfo confusion
        ("/foo@evil.com", None),
        # No leading slash
        ("workspace/foo", None),
        ("evil.com/path", None),
        # None in → None out
        (None, None),
        # Scheme buried in path — blocked by "://"
        ("/path/with://embedded", None),
    ],
)
def test_safe_return_to(value: str | None, expected: str | None) -> None:
    assert _safe_return_to(value) == expected
