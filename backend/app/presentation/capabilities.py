"""Capability-based authorization gate for FastAPI routes — EP-12.

Usage:

    @router.post(
        "/work-items/{id}/review",
        dependencies=[Depends(build_require_capabilities("review"))],
    )
    async def review_work_item(...): ...

Semantics:

- Requires an authenticated ``CurrentUser`` (the dependency itself depends
  on ``get_current_user``; plug it into the route's ``dependencies=[]``).
- Loads the caller's capabilities from the active ``workspace_memberships``
  row keyed by ``(user.id, user.workspace_id)`` via the provided repo.
- All declared capabilities must be present. Missing any → HTTP 403.
- No ``workspace_id`` in the caller's token → HTTP 403 (prevents anonymous
  cross-workspace checks).
- ``is_superadmin == True`` bypasses the check; the bypass is logged at
  INFO with the list of required capabilities for audit.
- Empty capability list (``build_require_capabilities()``) is treated as a
  noop — any authenticated user passes. Intended for routes that already
  gate on authentication alone; the empty-list branch exists so callers
  can wire a placeholder without special-casing in the route definition.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)


class _CapabilityRepo(Protocol):
    """Minimal repo contract for capability lookup.

    Keeps the dependency decoupled from the full IWorkspaceMembershipRepository
    so tests can pass a fake without implementing the whole interface.
    """

    async def get_capabilities_for(
        self, user_id: UUID, workspace_id: UUID
    ) -> list[str] | None: ...


def build_require_capabilities(
    *required: str,
) -> Callable[..., Awaitable[CurrentUser]]:
    """Factory: returns a FastAPI dependency enforcing ``required`` capabilities.

    The returned callable is async and takes:
      - ``user: CurrentUser`` — from the existing ``get_current_user`` dep.
      - ``repo: _CapabilityRepo`` — injected via
        ``Depends(get_capability_repo)`` (wired in ``app.main.create_app`` and
        overridden by tests).
    """
    from app.presentation.dependencies import get_capability_repo

    required_set = frozenset(required)

    async def _dep(
        user: CurrentUser,
        repo: _CapabilityRepo = Depends(get_capability_repo),
    ) -> CurrentUser:
        # Superadmin bypass — log for audit, short-circuit.
        if user.is_superadmin:
            if required_set:
                logger.info(
                    "capability_check_superadmin_bypass user_id=%s required=%s",
                    user.id,
                    sorted(required_set),
                )
            return user

        # Empty required list → noop gate (documented behavior).
        if not required_set:
            return user

        if user.workspace_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "NO_WORKSPACE",
                        "message": "caller lacks an active workspace",
                        "details": {},
                    }
                },
            )

        caps = await repo.get_capabilities_for(user.id, user.workspace_id)
        held = set(caps) if caps is not None else set()
        missing = required_set - held
        if missing:
            logger.warning(
                "capability_check_denied user_id=%s workspace_id=%s "
                "required=%s held=%s missing=%s",
                user.id,
                user.workspace_id,
                sorted(required_set),
                sorted(held),
                sorted(missing),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "INSUFFICIENT_CAPABILITY",
                        "message": "missing required capability",
                        "details": {"required": sorted(required_set)},
                    }
                },
            )
        return user

    return _dep
