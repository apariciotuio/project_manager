"""[RED] Logging formatter scrubs sensitive keys from log records."""

from __future__ import annotations

import json
import logging
from typing import Any


def _format_record(formatter: logging.Formatter, **extra: Any) -> dict[str, Any]:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return json.loads(formatter.format(record))


class TestJsonFormatterScrubsSensitiveKeys:
    def _formatter(self) -> logging.Formatter:
        from app.config.logging import JsonFormatter

        return JsonFormatter()

    def test_password_is_redacted(self) -> None:
        result = _format_record(self._formatter(), password="hunter2")
        assert result.get("password") == "***REDACTED***"
        assert "hunter2" not in json.dumps(result)

    def test_authorization_is_redacted(self) -> None:
        result = _format_record(self._formatter(), authorization="Bearer xyz123")
        assert result.get("authorization") == "***REDACTED***"
        assert "xyz123" not in json.dumps(result)

    def test_token_extra_is_redacted(self) -> None:
        result = _format_record(self._formatter(), token="super-secret-token")
        assert result.get("token") == "***REDACTED***"

    def test_secret_is_redacted(self) -> None:
        result = _format_record(self._formatter(), secret="my-secret-value")
        assert result.get("secret") == "***REDACTED***"

    def test_api_key_is_redacted(self) -> None:
        result = _format_record(self._formatter(), api_key="sk-12345")
        assert result.get("api_key") == "***REDACTED***"

    def test_credentials_is_redacted(self) -> None:
        result = _format_record(self._formatter(), credentials="user:pass")
        assert result.get("credentials") == "***REDACTED***"

    def test_benign_key_not_redacted(self) -> None:
        result = _format_record(self._formatter(), user_id="abc123", workspace="main")
        assert result.get("user_id") == "abc123"
        assert result.get("workspace") == "main"

    def test_case_insensitive_match(self) -> None:
        result = _format_record(self._formatter(), Authorization="Bearer abc")
        # key is lowercased in extra but we need to check both casings
        found = result.get("Authorization") or result.get("authorization")
        assert found == "***REDACTED***"

    def test_msg_field_not_redacted_by_key_scrubbing(self) -> None:
        """The main message string is not subject to key-based scrubbing."""
        result = _format_record(self._formatter(), user_id="safe")
        assert result["msg"] == "test message"

    def test_substring_match_in_key(self) -> None:
        """Key containing a sensitive substring is redacted (e.g. x_api_key)."""
        result = _format_record(self._formatter(), x_api_key="sk-9999")
        assert result.get("x_api_key") == "***REDACTED***"

    # ------------------------------------------------------------------
    # Recursive scrubbing (SF-1)
    # ------------------------------------------------------------------

    def test_nested_dict_sensitive_key_is_redacted(self) -> None:
        """Sensitive keys inside nested dicts must be redacted."""
        result = _format_record(
            self._formatter(),
            payload={"authorization": "Bearer xyz"},
        )
        raw = json.dumps(result)
        assert "Bearer xyz" not in raw
        assert "***REDACTED***" in raw
        assert result["payload"]["authorization"] == "***REDACTED***"

    def test_nested_dict_benign_key_not_redacted(self) -> None:
        """Benign keys inside nested dicts must be preserved."""
        result = _format_record(
            self._formatter(),
            payload={"user_id": "abc", "workspace": "main"},
        )
        assert result["payload"]["user_id"] == "abc"
        assert result["payload"]["workspace"] == "main"

    def test_list_of_dicts_sensitive_key_is_redacted(self) -> None:
        """Sensitive keys inside list-of-dicts must be redacted."""
        result = _format_record(
            self._formatter(),
            headers=[{"authorization": "Bearer abc"}, {"content-type": "application/json"}],
        )
        raw = json.dumps(result)
        assert "Bearer abc" not in raw
        assert result["headers"][0]["authorization"] == "***REDACTED***"
        assert result["headers"][1]["content-type"] == "application/json"

    def test_deeply_nested_dict_is_redacted(self) -> None:
        """Scrubbing must recurse beyond one level deep."""
        result = _format_record(
            self._formatter(),
            outer={"inner": {"password": "secret123"}},
        )
        raw = json.dumps(result)
        assert "secret123" not in raw
        assert result["outer"]["inner"]["password"] == "***REDACTED***"
