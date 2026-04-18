"""RED → GREEN tests for QueryCounterMiddleware.

Scenarios:
  - Counter increments once per SQL execution (via event listener)
  - Counter is per-request (ContextVar token reset between requests)
  - Production environment: counter disabled, no listener overhead
  - Budget exceeded emits WARNING log with endpoint + count
"""
from __future__ import annotations

import logging
from contextvars import copy_context
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Counter core — event listener behaviour
# ---------------------------------------------------------------------------

class TestQueryCounter:
    def test_increment_on_each_execute(self) -> None:
        """Each call to the listener increments the counter by 1."""
        from app.infrastructure.db.query_counter import (
            _query_count,
            before_cursor_execute_listener,
        )

        token = _query_count.set(0)
        try:
            # Fire listener 3 times
            for _ in range(3):
                before_cursor_execute_listener(None, None, None, None, None, False)
            assert _query_count.get() == 3
        finally:
            _query_count.reset(token)

    def test_counter_is_zero_after_reset(self) -> None:
        """ContextVar token reset restores counter to previous state."""
        from app.infrastructure.db.query_counter import _query_count, before_cursor_execute_listener

        token = _query_count.set(0)
        before_cursor_execute_listener(None, None, None, None, None, False)
        assert _query_count.get() == 1
        _query_count.reset(token)
        # After reset: original value (default None)
        assert _query_count.get() is None

    def test_counter_isolated_per_context(self) -> None:
        """Each copy_context() gets its own counter — simulates per-request isolation."""
        from app.infrastructure.db.query_counter import (
            _query_count,
            before_cursor_execute_listener,
        )

        results: list[int] = []

        def run_in_context(n: int) -> None:
            token = _query_count.set(0)
            for _ in range(n):
                before_cursor_execute_listener(None, None, None, None, None, False)
            results.append(_query_count.get())
            _query_count.reset(token)

        ctx1 = copy_context()
        ctx2 = copy_context()
        ctx1.run(run_in_context, 2)
        ctx2.run(run_in_context, 5)

        assert results == [2, 5]


# ---------------------------------------------------------------------------
# Budget check + WARNING log
# ---------------------------------------------------------------------------

class TestBudgetWarning:
    def test_warning_logged_when_budget_exceeded(self, caplog: pytest.LogCaptureFixture) -> None:
        """check_query_budget emits WARNING when count > budget."""
        from app.infrastructure.db.query_counter import _query_count, check_query_budget

        token = _query_count.set(25)
        try:
            with caplog.at_level(logging.WARNING, logger="app.infrastructure.db.query_counter"):
                check_query_budget(endpoint="/api/v1/work-items", budget=20)
            assert any(
                "N+1 WARNING" in r.message and "/api/v1/work-items" in r.message and "25" in r.message
                for r in caplog.records
            )
        finally:
            _query_count.reset(token)

    def test_no_warning_within_budget(self, caplog: pytest.LogCaptureFixture) -> None:
        """check_query_budget is silent when count <= budget."""
        from app.infrastructure.db.query_counter import _query_count, check_query_budget

        token = _query_count.set(10)
        try:
            with caplog.at_level(logging.WARNING, logger="app.infrastructure.db.query_counter"):
                check_query_budget(endpoint="/api/v1/work-items", budget=20)
            assert not any("N+1 WARNING" in r.message for r in caplog.records)
        finally:
            _query_count.reset(token)

    def test_warning_includes_count_and_budget(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log line includes both actual count and budget for actionable context."""
        from app.infrastructure.db.query_counter import _query_count, check_query_budget

        token = _query_count.set(42)
        try:
            with caplog.at_level(logging.WARNING, logger="app.infrastructure.db.query_counter"):
                check_query_budget(endpoint="/api/v1/tasks", budget=20)
            record = next(r for r in caplog.records if "N+1 WARNING" in r.message)
            assert "42" in record.message
            assert "20" in record.message
            assert "/api/v1/tasks" in record.message
        finally:
            _query_count.reset(token)


# ---------------------------------------------------------------------------
# Production guard — listener must NOT be registered in production
# ---------------------------------------------------------------------------

class TestProductionGuard:
    def test_register_listener_skipped_in_production(self) -> None:
        """register_query_counter does nothing when environment is 'production'."""
        from app.infrastructure.db.query_counter import register_query_counter

        mock_engine = MagicMock()
        mock_engine.sync_engine = MagicMock()

        register_query_counter(mock_engine, environment="production")

        mock_engine.sync_engine.connect.assert_not_called()
        # event.listen should NOT have been called
        from sqlalchemy import event as sa_event
        # The sync engine's event should not have received a listener
        mock_engine.sync_engine.dispatch.before_cursor_execute.assert_not_called() if hasattr(
            mock_engine.sync_engine, "dispatch"
        ) else None

    def test_register_listener_active_in_development(self) -> None:
        """register_query_counter calls event.listen for development."""
        from app.infrastructure.db.query_counter import (
            before_cursor_execute_listener,
            register_query_counter,
        )

        mock_engine = MagicMock()
        mock_sync = MagicMock()
        mock_engine.sync_engine = mock_sync

        with patch("app.infrastructure.db.query_counter.event") as mock_event:
            register_query_counter(mock_engine, environment="development")
            mock_event.listen.assert_called_once_with(
                mock_sync,
                "before_cursor_execute",
                before_cursor_execute_listener,
            )

    def test_register_listener_active_in_staging(self) -> None:
        """register_query_counter calls event.listen for staging."""
        from app.infrastructure.db.query_counter import (
            before_cursor_execute_listener,
            register_query_counter,
        )

        mock_engine = MagicMock()
        mock_sync = MagicMock()
        mock_engine.sync_engine = mock_sync

        with patch("app.infrastructure.db.query_counter.event") as mock_event:
            register_query_counter(mock_engine, environment="staging")
            mock_event.listen.assert_called_once_with(
                mock_sync,
                "before_cursor_execute",
                before_cursor_execute_listener,
            )

    def test_register_listener_skipped_in_prod_alias(self) -> None:
        """'prod' alias is also treated as production."""
        from app.infrastructure.db.query_counter import register_query_counter

        mock_engine = MagicMock()
        mock_engine.sync_engine = MagicMock()

        with patch("app.infrastructure.db.query_counter.event") as mock_event:
            register_query_counter(mock_engine, environment="prod")
            mock_event.listen.assert_not_called()


# ---------------------------------------------------------------------------
# Middleware — request lifecycle
# ---------------------------------------------------------------------------

class TestQueryCounterMiddleware:
    def test_middleware_resets_counter_between_requests(self) -> None:
        """Each request starts with a fresh counter (token reset on exit)."""
        import asyncio
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        from app.infrastructure.db.query_counter import _query_count
        from app.presentation.middleware.query_counter import QueryCounterMiddleware

        captured: list[int | None] = []

        async def endpoint(request: Request) -> PlainTextResponse:
            captured.append(_query_count.get())
            return PlainTextResponse("ok")

        starlette_app = Starlette(routes=[Route("/test", endpoint)])
        starlette_app.add_middleware(
            QueryCounterMiddleware,
            budget=20,
            environment="development",
        )

        client = TestClient(starlette_app, raise_server_exceptions=True)
        client.get("/test")
        client.get("/test")

        # Both requests should see counter starting at 0
        assert captured == [0, 0]

    def test_middleware_skips_budget_check_in_production(self, caplog: pytest.LogCaptureFixture) -> None:
        """No WARNING logged in production regardless of query count."""
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        from app.infrastructure.db.query_counter import _query_count, before_cursor_execute_listener
        from app.presentation.middleware.query_counter import QueryCounterMiddleware

        async def endpoint(request: Request) -> PlainTextResponse:
            # Simulate 30 queries
            for _ in range(30):
                before_cursor_execute_listener(None, None, None, None, None, False)
            return PlainTextResponse("ok")

        starlette_app = Starlette(routes=[Route("/test", endpoint)])
        starlette_app.add_middleware(
            QueryCounterMiddleware,
            budget=20,
            environment="production",
        )

        client = TestClient(starlette_app, raise_server_exceptions=True)
        with caplog.at_level(logging.WARNING, logger="app.infrastructure.db.query_counter"):
            client.get("/test")

        assert not any("N+1 WARNING" in r.message for r in caplog.records)
