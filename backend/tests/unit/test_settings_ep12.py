"""Unit tests for EP-12 AppSettings additions — max_body_bytes + csp_overrides.

RED phase: tests written against the public interface. They fail until
AppSettings grows max_body_bytes and csp_overrides fields.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# max_body_bytes
# ---------------------------------------------------------------------------


def test_max_body_bytes_default() -> None:
    """Default max_body_bytes is 1 MiB (1_048_576 bytes)."""
    from app.config.settings import AppSettings

    s = AppSettings()
    assert s.max_body_bytes == 1_048_576


def test_max_body_bytes_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_MAX_BODY_BYTES env var overrides the default."""
    monkeypatch.setenv("APP_MAX_BODY_BYTES", "2097152")
    from app.config.settings import AppSettings

    s = AppSettings()
    assert s.max_body_bytes == 2_097_152


def test_max_body_bytes_is_int() -> None:
    """max_body_bytes is always an int, not a string."""
    from app.config.settings import AppSettings

    s = AppSettings()
    assert isinstance(s.max_body_bytes, int)


# ---------------------------------------------------------------------------
# csp_overrides
# ---------------------------------------------------------------------------


def test_csp_overrides_default_is_empty_dict() -> None:
    """Default csp_overrides is an empty dict."""
    from app.config.settings import AppSettings

    s = AppSettings()
    assert s.csp_overrides == {}


def test_csp_overrides_env_single_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_CSP_OVERRIDES=script-src 'self' https://cdn.example.com parses to dict."""
    monkeypatch.setenv("APP_CSP_OVERRIDES", "script-src='self' https://cdn.example.com")
    from app.config.settings import AppSettings

    s = AppSettings()
    assert s.csp_overrides == {"script-src": "'self' https://cdn.example.com"}


def test_csp_overrides_env_multiple_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiple comma-separated key=value pairs are all parsed."""
    monkeypatch.setenv(
        "APP_CSP_OVERRIDES",
        "script-src='self' https://cdn.example.com,img-src='self' data: https:",
    )
    from app.config.settings import AppSettings

    s = AppSettings()
    assert s.csp_overrides == {
        "script-src": "'self' https://cdn.example.com",
        "img-src": "'self' data: https:",
    }


def test_csp_overrides_is_dict() -> None:
    """csp_overrides is always a dict."""
    from app.config.settings import AppSettings

    s = AppSettings()
    assert isinstance(s.csp_overrides, dict)
