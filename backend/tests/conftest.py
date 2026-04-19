"""Shared test fixtures.

Session-scoped Postgres container per test run.
Settings are overridden to point at it.
"""

import secrets

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

from app.config.settings import Settings, get_settings


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session", autouse=True)
def override_settings(postgres_container):
    pg_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )

    test_settings = Settings.__new__(Settings)

    from app.config.settings import (
        AppSettings,
        AuthSettings,
        DatabaseSettings,
        DundunSettings,
        JiraSettings,
        MCPSettings,
        PuppetSettings,
    )

    test_settings.app = AppSettings(env="test", debug=False, log_level="WARNING")
    test_settings.database = DatabaseSettings(url=pg_url)
    test_settings.auth = AuthSettings()
    test_settings.dundun = DundunSettings(use_fake=True)
    test_settings.puppet = PuppetSettings(use_fake=True)
    test_settings.jira = JiraSettings()
    test_settings.mcp = MCPSettings()

    get_settings.cache_clear()

    import app.config.settings as settings_module

    original_get_settings = settings_module.get_settings

    def _test_get_settings() -> Settings:
        return test_settings

    get_settings.__wrapped__ = lambda: test_settings  # type: ignore[attr-defined]
    settings_module.get_settings = _test_get_settings  # type: ignore[assignment]

    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    yield test_settings

    settings_module.get_settings = original_get_settings  # type: ignore[assignment]
    get_settings.cache_clear()
    db_module._engine = None
    db_module._session_factory = None


@pytest.fixture(scope="session")
def migrated_database(override_settings):
    """Apply Alembic migrations once per session against the test container."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    cfg.set_main_option("sqlalchemy.url", override_settings.database.url)
    command.upgrade(cfg, "head")
    yield override_settings


@pytest.fixture(scope="session")
def _ensure_wmp_app_role(migrated_database, postgres_container):
    """Create a non-superuser role wmp_app for RLS tests.

    Runs once per session after migrations. Uses a synchronous psycopg2 connection
    (already available via testcontainers) so we avoid async bootstrap complexity.
    """
    import psycopg

    # testcontainers returns a psycopg2-style URL; psycopg3 uses postgresql://
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    with psycopg.connect(sync_url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = 'wmp_app'"
        ).fetchone()
        if not row:
            conn.execute("CREATE ROLE wmp_app NOSUPERUSER LOGIN PASSWORD 'wmp_app'")

        # Grant usage + DML on all current tables in public schema
        conn.execute("GRANT USAGE ON SCHEMA public TO wmp_app")
        conn.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO wmp_app"
        )

    return migrated_database


@pytest_asyncio.fixture
async def db_session(migrated_database):
    """Per-test async session with TRUNCATE cleanup.

    Each integration test gets a fresh session. After the test, every EP-00 and EP-01
    domain table is wiped via `TRUNCATE ... RESTART IDENTITY CASCADE` so tests never
    see rows from earlier cases.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "lock_unlock_requests, section_locks, attachments, work_item_tags, tags, "
                "puppet_ingest_requests, puppet_sync_outbox, integration_exports, integration_configs, "
                "routing_rules, projects, saved_searches, notifications, "
                "team_memberships, teams, timeline_events, comments, "
                "review_responses, validation_status, review_requests, "
                "validation_requirements, task_dependencies, task_node_section_links, "
                "task_nodes, work_item_versions, work_item_validators, "
                "work_item_section_versions, work_item_sections, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        # audit_events RULEs block DELETE — clear it by dropping+recreating the RULE
        # is too heavy; integration tests don't assert on row counts there.
    await engine.dispose()


@pytest_asyncio.fixture
async def rls_session(_ensure_wmp_app_role, postgres_container):
    """Per-test async session connected as non-superuser wmp_app role.

    RLS is ONLY enforced for non-superusers. Use this fixture for any test
    that asserts workspace isolation. The session uses the same testcontainer
    Postgres but connects as wmp_app (NOSUPERUSER).

    Cleanup is handled by db_session fixture — callers that need both fixtures
    should declare both; db_session runs TRUNCATE after the test.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # Build wmp_app URL from the container's connection URL
    base_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )
    # Replace credentials: postgresql+asyncpg://user:pass@host:port/db
    import re

    rls_url = re.sub(
        r"postgresql\+asyncpg://[^@]+@",
        "postgresql+asyncpg://wmp_app:wmp_app@",
        base_url,
    )

    engine = create_async_engine(rls_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(override_settings) -> AsyncClient:  # noqa: ARG001 — pytest fixture dep
    from app.main import create_app
    from app.presentation.dependencies import get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    app = create_app()

    # Replace the cache dep with an in-memory fake.
    fake_cache = FakeCache()

    async def _override_cache():
        yield fake_cache

    app.dependency_overrides[get_cache_adapter] = _override_cache

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def csrf_client(client: AsyncClient) -> AsyncClient:
    """CSRF-protected client for state-changing endpoints (POST/PUT/PATCH/DELETE).

    Auto-injects matching csrf_token cookie and X-CSRF-Token header on all requests.
    Use this fixture when testing endpoints guarded by CSRFMiddleware.
    """
    csrf_token = secrets.token_urlsafe(32)
    client.cookies.set("csrf_token", csrf_token)

    # Wrap request methods to auto-inject CSRF header
    original_request = client.request

    async def _request_with_csrf(method, url, **kwargs):
        if method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            headers = kwargs.get("headers") or {}
            headers["X-CSRF-Token"] = csrf_token
            kwargs["headers"] = headers
        return await original_request(method, url, **kwargs)

    client.request = _request_with_csrf  # type: ignore[method-assign]
    return client
