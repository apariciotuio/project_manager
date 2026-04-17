"""Observability scaffolding — no-op tracing context manager.

Usage:
    from app.infrastructure.observability.tracing import span

    with span("work_item.create") as s:
        result = await service.create(...)

The span context manager is a pure no-op. No external tracing backend
(OTel, Jaeger, Zipkin, Datadog) is connected — decision #27 deferred
observability. This abstraction lets call-sites instrument NOW.

When adding a real backend:
1. Implement a real Span dataclass with .set_attribute(), .record_exception(), etc.
2. Replace NoOpSpan and the _span_impl factory in this module.
3. Zero call-site changes needed.

# TODO: EP-12 later phase — connect OTel backend when decided.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator


class NoOpSpan:
    """Span stub that accepts attribute/event calls and does nothing."""

    def set_attribute(self, key: str, value: object) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def set_status(self, status: str) -> None:
        pass


@contextmanager
def span(name: str) -> Generator[NoOpSpan, None, None]:
    """Create a tracing span context.

    Args:
        name: Logical operation name (e.g. ``"work_item.create"``).

    Yields:
        A NoOpSpan (currently). In a future real-backend implementation this
        would be an OTel ``Span`` with the same interface.
    """
    yield NoOpSpan()
