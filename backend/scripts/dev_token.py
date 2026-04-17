"""Emit a ready-to-use access token for a seed user.

Local dev only. Prints the token to stdout so it can be captured into an
env var or curl header for smoke-testing the API end-to-end.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/dev_token.py [email]          # default: first superadmin
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config.settings import get_settings
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.models.orm import (
    UserORM,
    WorkspaceMembershipORM,
    WorkspaceORM,
)


async def run(email: str | None) -> int:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(UserORM)
        if email:
            stmt = stmt.where(UserORM.email == email.lower())
        else:
            stmt = stmt.where(UserORM.is_superadmin == True).limit(1)  # noqa: E712
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is None:
            print("[dev-token] no matching user", file=sys.stderr)
            return 1

        membership_stmt = (
            select(WorkspaceMembershipORM, WorkspaceORM)
            .join(WorkspaceORM, WorkspaceMembershipORM.workspace_id == WorkspaceORM.id)
            .where(
                WorkspaceMembershipORM.user_id == user.id,
                WorkspaceMembershipORM.state == "active",
            )
            .limit(1)
        )
        row = (await session.execute(membership_stmt)).first()
        workspace_id = row[0].workspace_id if row else None
        workspace_slug = row[1].slug if row else None

    jwt_adapter = JwtAdapter(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        issuer=settings.auth.jwt_issuer,
        audience=settings.auth.jwt_audience,
    )
    now = datetime.now(UTC)
    exp = now + timedelta(hours=8)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "is_superadmin": user.is_superadmin,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt_adapter.encode(payload)

    print(f"# user       : {user.email}")
    print(f"# user_id    : {user.id}")
    print(f"# workspace  : {workspace_slug} ({workspace_id})")
    print(f"# expires    : {exp.isoformat()}")
    print(token)
    return 0


if __name__ == "__main__":
    email_arg = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(asyncio.run(run(email_arg)))
