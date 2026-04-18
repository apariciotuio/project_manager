import json
import logging
from contextvars import ContextVar
from typing import Any

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

# Keys (or substrings of keys) whose values must never appear in logs.
_SENSITIVE_KEY_SUBSTRINGS = frozenset(
    {
        "authorization",
        "token",
        "password",
        "secret",
        "api_key",
        "credentials",
        "cookie",
        "set-cookie",
    }
)
_REDACTED = "***REDACTED***"

# LogRecord built-in attributes — we only scrub *extra* fields added by callers.
_LOG_RECORD_BUILTIN_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime"}


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return any(sub in lower for sub in _SENSITIVE_KEY_SUBSTRINGS)


def _scrub_value(key: str, value: Any) -> Any:
    if _is_sensitive_key(key):
        return _REDACTED
    if isinstance(value, dict):
        return _scrub(value)
    if isinstance(value, list):
        return [_scrub(item) if isinstance(item, dict) else item for item in value]
    return value


def _scrub(data: dict[str, Any]) -> dict[str, Any]:
    return {k: _scrub_value(k, v) for k, v in data.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": correlation_id_var.get(""),
        }
        if record.exc_info:
            log_entry["exc"] = self.formatException(record.exc_info)

        # Merge and scrub any extra fields added via logging.info(..., extra={...})
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _LOG_RECORD_BUILTIN_ATTRS and not k.startswith("_")
        }
        if extra:
            log_entry.update(_scrub(extra))

        return json.dumps(log_entry)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get("")  # type: ignore[attr-defined]
        return True


def configure_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())

    root = logging.getLogger()
    # Remove only previously installed JSON handlers, not caplog / third-party ones.
    for existing in list(root.handlers):
        if isinstance(existing.formatter, JsonFormatter):
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
