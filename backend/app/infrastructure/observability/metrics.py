"""Observability scaffolding — no-op metrics registry.

Controllers and services instrument with:
    from app.infrastructure.observability.metrics import counter, histogram

    counter("work_item.created").inc()
    histogram("request.duration_ms").observe(elapsed_ms)

The current implementation is a no-op. No external backend (Prometheus,
StatsD, etc.) is connected — decision #27 deferred observability. This
abstraction lets every call-site instrument NOW so when we hook up a real
backend (Phase N of EP-12 or a future EP) we only change this module.

When adding a real backend:
1. Implement PrometheusCounter / PrometheusHistogram with the same interface.
2. Swap MetricsRegistry._counter_cls / _histogram_cls.
3. Zero call-site changes needed.

# TODO: EP-12 later phase — connect real Prometheus backend when decided.
"""

from __future__ import annotations

from typing import Any


class NoOpCounter:
    """Counter that accepts .inc() calls and always reports value=0."""

    @property
    def value(self) -> int:
        return 0

    def inc(self, amount: int = 1, labels: dict[str, str] | None = None) -> None:
        pass  # no-op


class NoOpHistogram:
    """Histogram that accepts .observe() calls and does nothing."""

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        pass  # no-op


class MetricsRegistry:
    """Thread-safe singleton-per-name registry for metrics.

    Returns the same NoOpCounter / NoOpHistogram instance for the same name
    so callers can check identity in tests.
    """

    def __init__(self) -> None:
        self._counters: dict[str, NoOpCounter] = {}
        self._histograms: dict[str, NoOpHistogram] = {}

    def counter(self, name: str) -> NoOpCounter:
        if name not in self._counters:
            self._counters[name] = NoOpCounter()
        return self._counters[name]

    def histogram(self, name: str) -> NoOpHistogram:
        if name not in self._histograms:
            self._histograms[name] = NoOpHistogram()
        return self._histograms[name]


# Module-level registry — shared across the process. Import and call directly:
#   from app.infrastructure.observability.metrics import counter, histogram
_registry = MetricsRegistry()


def counter(name: str) -> NoOpCounter:
    """Return (or create) the named counter from the global registry."""
    return _registry.counter(name)


def histogram(name: str) -> NoOpHistogram:
    """Return (or create) the named histogram from the global registry."""
    return _registry.histogram(name)
