"""RLS session context helper.

Sets the PostgreSQL session-local config var used by workspace-isolation policies.
Must be called BEFORE any query on a new transaction.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def with_workspace(session: AsyncSession, workspace_id: UUID) -> None:
    """SET LOCAL app.current_workspace for RLS.

    Uses set_config(..., true) where true = is_local — scoped to current transaction.
    Commits and rollbacks reset it automatically.
    """
    await session.execute(
        text("SELECT set_config('app.current_workspace', :wid, true)"),
        {"wid": str(workspace_id)},
    )


async def get_scoped_session(
    factory: async_sessionmaker[AsyncSession],
    workspace_id: UUID,
) -> AsyncGenerator[AsyncSession]:
    """Yield a session with workspace RLS set.

    Usage (Phase 4 — controllers via Depends):
        async with get_scoped_session(session_factory, workspace_id) as session:
            ...

    NOT wired into controllers yet — Phase 4 will connect this.
    """
    async with factory() as session:
        async with session.begin():
            await with_workspace(session, workspace_id)
            yield session
