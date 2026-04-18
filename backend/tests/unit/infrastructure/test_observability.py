"""Unit tests for observability scaffolding (no-op metrics + tracing) — RED phase."""

from __future__ import annotations

import pytest

from app.infrastructure.observability.metrics import (
    MetricsRegistry,
    NoOpCounter,
    NoOpHistogram,
    counter,
    histogram,
)
from app.infrastructure.observability.tracing import span

# ---------------------------------------------------------------------------
# Metrics — Counter
# ---------------------------------------------------------------------------


def test_counter_inc_does_not_raise() -> None:
    """counter('name').inc() is a safe no-op — never raises."""
    c = counter("work_item.created")
    c.inc()  # must not raise
    c.inc(3)  # increment by value must not raise


def test_counter_value_is_zero_on_noop() -> None:
    """No-op counter always reports 0 (there is no real backend)."""
    c = counter("some.metric")
    c.inc()
    c.inc()
    assert c.value == 0  # no-op — no real storage


def test_counter_returns_noop_counter_type() -> None:
    """counter() returns a NoOpCounter instance."""
    c = counter("foo.bar")
    assert isinstance(c, NoOpCounter)


def test_counter_inc_with_labels_does_not_raise() -> None:
    """counter inc() with label kwarg is a no-op — does not raise."""
    c = counter("api.request")
    c.inc(labels={"method": "GET", "path": "/test"})


# ---------------------------------------------------------------------------
# Metrics — Histogram
# ---------------------------------------------------------------------------


def test_histogram_observe_does_not_raise() -> None:
    """histogram('name').observe(ms) is a safe no-op."""
    h = histogram("request.duration_ms")
    h.observe(42.0)  # must not raise
    h.observe(0.0)
    h.observe(9999.9)


def test_histogram_returns_noop_histogram_type() -> None:
    """histogram() returns a NoOpHistogram instance."""
    h = histogram("db.query_time_ms")
    assert isinstance(h, NoOpHistogram)


def test_histogram_observe_with_labels_does_not_raise() -> None:
    """histogram observe() with labels is a no-op."""
    h = histogram("endpoint.latency")
    h.observe(100.0, labels={"endpoint": "/api/v1/items"})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_returns_same_counter_by_name() -> None:
    """Calling counter() twice with the same name returns the same instance."""
    registry = MetricsRegistry()
    c1 = registry.counter("events.sent")
    c2 = registry.counter("events.sent")
    assert c1 is c2


def test_registry_returns_same_histogram_by_name() -> None:
    """Calling histogram() twice with the same name returns the same instance."""
    registry = MetricsRegistry()
    h1 = registry.histogram("query.ms")
    h2 = registry.histogram("query.ms")
    assert h1 is h2


# ---------------------------------------------------------------------------
# Tracing — span context manager
# ---------------------------------------------------------------------------


def test_span_context_manager_is_noop() -> None:
    """span() is a pure no-op context manager — no side effects."""
    with span("work_item.create") as s:
        assert s is not None  # must yield something (even None or a stub)


def test_span_nested_does_not_raise() -> None:
    """Nested spans do not raise."""
    with span("outer"), span("inner"):
        pass  # must not raise


def test_span_exception_propagates() -> None:
    """Exceptions inside a span propagate normally — the span doesn't swallow them."""
    with pytest.raises(ValueError, match="boom"), span("broken.op"):
        raise ValueError("boom")
