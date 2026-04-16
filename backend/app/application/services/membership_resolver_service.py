"""MembershipResolverService — 0/1/N routing after OAuth callback.

Pure logic over `get_active_by_user_id`. No side effects, no audit writes (the
caller emits the `login_blocked_no_workspace` audit event when kind == 'no_access').
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.models.workspace_membership import WorkspaceMembership
from app.domain.repositories.workspace_membership_repository import (
    IWorkspaceMembershipRepository,
)

OutcomeKind = Literal["no_access", "single", "picker"]


@dataclass(frozen=True)
class ResolverOutcome:
    kind: OutcomeKind
    workspace_id: UUID | None
    choices: list[WorkspaceMembership]


class MembershipResolverService:
    def __init__(self, repo: IWorkspaceMembershipRepository) -> None:
        self._repo = repo

    async def resolve(
        self,
        *,
        user_id: UUID,
        last_chosen_workspace_id: UUID | None = None,
    ) -> ResolverOutcome:
        active = await self._repo.get_active_by_user_id(user_id)
        if not active:
            return ResolverOutcome(kind="no_access", workspace_id=None, choices=[])
        if len(active) == 1:
            return ResolverOutcome(
                kind="single", workspace_id=active[0].workspace_id, choices=[]
            )
        if last_chosen_workspace_id is not None and any(
            m.workspace_id == last_chosen_workspace_id for m in active
        ):
            return ResolverOutcome(
                kind="single", workspace_id=last_chosen_workspace_id, choices=[]
            )
        return ResolverOutcome(kind="picker", workspace_id=None, choices=list(active))
