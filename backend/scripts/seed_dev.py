"""Dev bootstrap seed.

Creates the initial workspace and memberships for the superadmin emails declared
in `AUTH_SEED_SUPERADMIN_EMAILS`. Run AFTER each seeded user has attempted Google
login at least once (the login is expected to fail with `no_workspace` on the
first attempt — it creates the `users` row, which this script then attaches to a
freshly-created workspace).

Usage (from repo root):

    cd backend && source .venv/bin/activate
    python scripts/seed_dev.py

Idempotent — safe to re-run. Skips users that haven't logged in yet with a
warning.
"""

from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.models.orm import (
    UserORM,
    WorkspaceMembershipORM,
    WorkspaceORM,
)

WORKSPACE_NAME = "Tuio"
WORKSPACE_SLUG = "tuio"
DEFAULT_ROLE = "Workspace Admin"


async def _get_user_by_email(session: AsyncSession, email: str) -> UserORM | None:
    stmt = select(UserORM).where(UserORM.email == email.lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_workspace_by_slug(session: AsyncSession, slug: str) -> WorkspaceORM | None:
    stmt = select(WorkspaceORM).where(WorkspaceORM.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_membership(
    session: AsyncSession, *, workspace_id, user_id
) -> WorkspaceMembershipORM | None:
    stmt = select(WorkspaceMembershipORM).where(
        WorkspaceMembershipORM.workspace_id == workspace_id,
        WorkspaceMembershipORM.user_id == user_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def run() -> int:
    settings = get_settings()
    emails = [e.strip().lower() for e in settings.auth.seed_superadmin_emails if e.strip()]
    if not emails:
        print("[seed] AUTH_SEED_SUPERADMIN_EMAILS is empty — nothing to do.")
        return 0

    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            users: list[UserORM] = []
            for email in emails:
                user = await _get_user_by_email(session, email)
                if user is None:
                    print(
                        f"[seed] WARN: user {email!r} not in DB — login once with that "
                        f"Google account first, then re-run this script."
                    )
                    continue
                if not user.is_superadmin:
                    user.is_superadmin = True
                    print(f"[seed] flipped is_superadmin=true for {email}")
                users.append(user)

            if not users:
                print("[seed] no seeded users found in DB; aborting workspace creation.")
                return 1

            workspace = await _get_workspace_by_slug(session, WORKSPACE_SLUG)
            if workspace is None:
                workspace = WorkspaceORM(
                    id=uuid4(),
                    name=WORKSPACE_NAME,
                    slug=WORKSPACE_SLUG,
                    created_by=users[0].id,
                    status="active",
                )
                session.add(workspace)
                await session.flush()
                print(f"[seed] created workspace {WORKSPACE_SLUG!r} (id={workspace.id})")
            else:
                print(f"[seed] workspace {WORKSPACE_SLUG!r} already exists")

            for user in users:
                existing = await _get_membership(
                    session, workspace_id=workspace.id, user_id=user.id
                )
                if existing is None:
                    session.add(
                        WorkspaceMembershipORM(
                            id=uuid4(),
                            workspace_id=workspace.id,
                            user_id=user.id,
                            role=DEFAULT_ROLE,
                            state="active",
                            is_default=True,
                        )
                    )
                    print(f"[seed] added membership {user.email} → {WORKSPACE_SLUG}")
                elif existing.state != "active":
                    existing.state = "active"
                    print(f"[seed] re-activated membership {user.email} → {WORKSPACE_SLUG}")
                else:
                    print(f"[seed] membership already active: {user.email} → {WORKSPACE_SLUG}")

    print("[seed] done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
