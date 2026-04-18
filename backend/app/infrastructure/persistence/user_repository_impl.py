"""SQLAlchemy implementation of IUserRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.user import User
from app.domain.repositories.user_repository import IUserRepository
from app.infrastructure.persistence.models.orm import UserORM


class EmailAlreadyLinkedError(Exception):
    """Raised when an email is already associated with a different Google account."""


def _to_domain(row: UserORM) -> User:
    return User(
        id=row.id,
        google_sub=row.google_sub,
        email=row.email,
        full_name=row.full_name,
        avatar_url=row.avatar_url,
        status=row.status,  # type: ignore[arg-type]
        is_superadmin=row.is_superadmin,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class UserRepositoryImpl(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return _to_domain(row) if row else None

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        stmt = select(UserORM).where(UserORM.google_sub == google_sub)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserORM).where(UserORM.email == email.lower())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def upsert(self, user: User) -> User:
        stmt = (
            pg_insert(UserORM)
            .values(
                id=user.id,
                google_sub=user.google_sub,
                email=user.email,
                full_name=user.full_name,
                avatar_url=user.avatar_url,
                status=user.status,
                is_superadmin=user.is_superadmin,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            .on_conflict_do_update(
                index_elements=[UserORM.google_sub],
                set_={
                    "email": user.email,
                    "full_name": user.full_name,
                    "avatar_url": user.avatar_url,
                    "status": user.status,
                    "is_superadmin": user.is_superadmin,
                    "updated_at": user.updated_at,
                },
            )
            .returning(UserORM)
        )
        try:
            result = await self._session.execute(stmt)
            row = result.scalar_one()
            await self._session.flush()
        except IntegrityError as exc:
            orig = str(exc.orig).lower()
            if "email" in orig or "uq_users_email_lower" in orig:
                raise EmailAlreadyLinkedError(user.email) from exc
            raise
        return _to_domain(row)
