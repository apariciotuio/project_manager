"""Unit tests for correlation_id logging integration — RED phase.

Verifies that JsonFormatter and CorrelationIdFilter propagate the
correlation_id ContextVar into every log record.
"""

from __future__ import annotations

import json
import logging

from app.config.logging import (
    CorrelationIdFilter,
    JsonFormatter,
    configure_logging,
    correlation_id_var,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_logger(name: str = "test.correlation") -> tuple[logging.Logger, list[logging.LogRecord]]:
    """Return a logger wired with JsonFormatter + CorrelationIdFilter, and a records sink."""
    records: list[logging.LogRecord] = []

    class _Sink(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False
    handler = _Sink()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger, records


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_json_formatter_includes_correlation_id_field() -> None:
    """JsonFormatter embeds correlation_id from ContextVar in JSON output."""
    cid = "aaaa1111-bbbb-2222-cccc-333344445555"
    token = correlation_id_var.set(cid)
    try:
        logger, records = _make_logger("test.json_fmt")
        logger.info("hello")
    finally:
        correlation_id_var.reset(token)

    assert len(records) == 1
    formatted = JsonFormatter().format(records[0])
    parsed = json.loads(formatted)
    # correlation_id must be present in the JSON blob after reset — but the
    # formatter captures the ContextVar at format-time, so we format inside the token scope.
    token2 = correlation_id_var.set(cid)
    try:
        formatted2 = JsonFormatter().format(records[0])
    finally:
        correlation_id_var.reset(token2)
    parsed2 = json.loads(formatted2)
    assert parsed2["correlation_id"] == cid


def test_correlation_id_filter_attaches_to_record() -> None:
    """CorrelationIdFilter sets record.correlation_id from ContextVar."""
    cid = "deadbeef-dead-beef-dead-beefdeadbeef"
    token = correlation_id_var.set(cid)
    try:
        logger, records = _make_logger("test.filter")
        logger.warning("test warning")
    finally:
        correlation_id_var.reset(token)

    assert len(records) == 1
    assert getattr(records[0], "correlation_id", None) == cid


def test_correlation_id_defaults_to_empty_string_when_not_set() -> None:
    """When ContextVar has no value, correlation_id defaults to empty string in log."""
    # Ensure no value set
    correlation_id_var.set("")
    logger, records = _make_logger("test.default_cid")
    logger.info("no correlation")

    assert len(records) == 1
    assert getattr(records[0], "correlation_id", None) == ""


def test_json_formatter_output_is_valid_json() -> None:
    """JsonFormatter always produces parseable JSON."""
    logger, records = _make_logger("test.valid_json")
    logger.info("structured message")

    formatted = JsonFormatter().format(records[0])
    parsed = json.loads(formatted)
    assert "ts" in parsed
    assert "level" in parsed
    assert "logger" in parsed
    assert "msg" in parsed
    assert "correlation_id" in parsed


def test_json_formatter_includes_exception_info() -> None:
    """Exceptions are serialised into the 'exc' field."""
    logger, records = _make_logger("test.exc_info")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("caught it")

    formatted = JsonFormatter().format(records[0])
    parsed = json.loads(formatted)
    assert "exc" in parsed
    assert "ValueError" in parsed["exc"]


def test_configure_logging_does_not_duplicate_handlers() -> None:
    """Calling configure_logging twice does not install duplicate JsonFormatter handlers."""
    configure_logging("INFO")
    configure_logging("INFO")
    root = logging.getLogger()
    json_handlers = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
    assert len(json_handlers) == 1
