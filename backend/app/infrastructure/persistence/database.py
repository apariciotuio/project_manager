from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # Deferred import so tests can monkeypatch `app.config.settings.get_settings`
        # without being defeated by a stale module-level binding captured here.
        from app.config.settings import get_settings
        from app.infrastructure.db.query_counter import register_query_counter

        settings = get_settings()
        _engine = create_async_engine(
            settings.database.url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=settings.app.debug,
        )
        register_query_counter(_engine, environment=settings.app.env)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
