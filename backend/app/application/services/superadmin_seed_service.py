"""SuperadminSeedService — flips `is_superadmin` on first login of seeded emails.

Config seed only. Subsequent promotions go through the admin API (EP-10).
Idempotent: re-running on an already-superadmin user emits no audit event.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.application.services.audit_service import AuditService
from app.domain.models.user import User
from app.domain.repositories.user_repository import IUserRepository


class SuperadminSeedService:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        audit_service: AuditService,
        seeded_emails: Iterable[str],
    ) -> None:
        self._users = user_repo
        self._audit = audit_service
        self._seeded = frozenset(e.strip().lower() for e in seeded_emails if e.strip())

    async def on_user_created(self, user: User) -> None:
        if user.email not in self._seeded:
            return
        if user.is_superadmin:
            return  # already promoted — idempotent

        user.is_superadmin = True
        await self._users.upsert(user)
        await self._audit.log_event(
            category="auth",
            action="superadmin_seeded",
            actor_id=user.id,
            actor_display=user.email,
            context={"source": "env_seed"},
        )
