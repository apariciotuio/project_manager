"""FastAPI dependency wiring for EP-00 and EP-01 controllers.

Kept centralised so repos, services, and adapters share a single construction path.
Each request gets its own AsyncSession; services built on top of it are request-scoped.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.events.event_bus import EventBus

if TYPE_CHECKING:
    from app.application.services.draft_service import DraftService
    from app.application.services.template_service import TemplateService
    from app.domain.ports.cache import ICache
    from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
        AssistantSuggestionRepositoryImpl,
    )
    from app.infrastructure.persistence.gap_finding_repository_impl import (
        GapFindingRepositoryImpl,
    )
from app.application.services.audit_service import AuditService
from app.application.services.auth_service import AuthService
from app.application.services.membership_resolver_service import (
    MembershipResolverService,
)
from app.application.services.superadmin_seed_service import SuperadminSeedService
from app.application.services.work_item_service import WorkItemService
from app.config.settings import Settings, get_settings
from app.infrastructure.adapters.google_oauth_adapter import GoogleOAuthAdapter
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.oauth_state_repository_impl import (
    OAuthStateRepositoryImpl,
)
from app.infrastructure.persistence.session_context import with_workspace
from app.infrastructure.persistence.session_repository_impl import SessionRepositoryImpl
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.work_item_repository_impl import (
    WorkItemRepositoryImpl,
)
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import (
    WorkspaceRepositoryImpl,
)
from app.presentation.middleware.auth_middleware import (
    CurrentUser,
    build_current_user_dependency,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_jwt_adapter() -> JwtAdapter:
    settings = get_settings()
    return JwtAdapter(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        issuer=settings.auth.jwt_issuer,
        audience=settings.auth.jwt_audience,
    )


def get_google_oauth_adapter() -> GoogleOAuthAdapter:
    settings = get_settings()
    return GoogleOAuthAdapter(
        client_id=settings.auth.google_client_id,
        client_secret=settings.auth.google_client_secret,
        redirect_uri=settings.auth.google_redirect_uri,
    )


def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    google_oauth: GoogleOAuthAdapter = Depends(get_google_oauth_adapter),
    jwt_adapter: JwtAdapter = Depends(get_jwt_adapter),
) -> AuthService:
    audit_repo = AuditRepositoryImpl(session)
    audit = AuditService(audit_repo)
    user_repo = UserRepositoryImpl(session)
    return AuthService(
        user_repo=user_repo,
        session_repo=SessionRepositoryImpl(session),
        oauth_state_repo=OAuthStateRepositoryImpl(session),
        google_oauth=google_oauth,
        jwt_adapter=jwt_adapter,
        audit_service=audit,
        superadmin_seed=SuperadminSeedService(
            user_repo=user_repo,
            audit_service=audit,
            seeded_emails=settings.auth.seed_superadmin_emails,
        ),
        membership_resolver=MembershipResolverService(
            WorkspaceMembershipRepositoryImpl(session)
        ),
        access_token_ttl_seconds=settings.auth.access_token_ttl_seconds,
        refresh_token_ttl_seconds=settings.auth.refresh_token_ttl_seconds,
        oauth_state_ttl_seconds=settings.auth.oauth_state_ttl_seconds,
    )


def get_user_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepositoryImpl:
    return UserRepositoryImpl(session)


def get_workspace_repo(
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceRepositoryImpl:
    return WorkspaceRepositoryImpl(session)


def get_membership_repo(
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceMembershipRepositoryImpl:
    return WorkspaceMembershipRepositoryImpl(session)


async def get_current_user(
    request: Request,
    jwt_adapter: JwtAdapter = Depends(get_jwt_adapter),
) -> CurrentUser:
    """Per-request auth check. Delegates to the closure built by the middleware factory."""
    return await build_current_user_dependency(jwt_adapter)(request)


async def get_scoped_session(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession]:
    """Yield an AsyncSession with workspace RLS SET LOCAL applied.

    Requires current_user to have a non-None workspace_id — 401 is raised by
    get_current_user before we reach this dep if the JWT is invalid.
    """
    if current_user.workspace_id is None:
        from fastapi import HTTPException
        from fastapi import status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "NO_WORKSPACE",
                    "message": "no workspace in token",
                    "details": {},
                }
            },
        )
    factory = get_session_factory()
    async with factory() as session:
        try:
            await with_workspace(session, current_user.workspace_id)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_work_item_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> WorkItemService:
    """Build WorkItemService for the current request with workspace-scoped session."""
    audit_repo = AuditRepositoryImpl(session)
    audit = AuditService(audit_repo)
    return WorkItemService(
        work_items=WorkItemRepositoryImpl(session),
        users=UserRepositoryImpl(session),
        memberships=WorkspaceMembershipRepositoryImpl(session),
        audit=audit,
        events=EventBus(),
    )


def get_draft_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> DraftService:
    from app.application.services.draft_service import DraftService
    from app.infrastructure.persistence.work_item_draft_repository_impl import (
        WorkItemDraftRepositoryImpl,
    )

    return DraftService(
        draft_repo=WorkItemDraftRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
    )


def get_draft_service_unscoped(
    session: AsyncSession = Depends(get_db_session),
) -> DraftService:
    """DraftService without RLS scope (for pre-creation drafts — no workspace context needed)."""
    from app.application.services.draft_service import DraftService
    from app.infrastructure.persistence.work_item_draft_repository_impl import (
        WorkItemDraftRepositoryImpl,
    )

    return DraftService(
        draft_repo=WorkItemDraftRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
    )


async def get_cache_adapter() -> AsyncGenerator[ICache]:
    """Yield a cache adapter scoped to the request; close the Redis client afterwards.

    Tests override this dep with an in-memory FakeCache so they don't need a Redis
    container. See tests/conftest.py::client.
    """
    from app.infrastructure.adapters.redis_cache_adapter import RedisCacheAdapter

    settings = get_settings()
    cache = RedisCacheAdapter(url=settings.redis.url)
    try:
        yield cache
    finally:
        await cache.close()


def get_template_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: ICache = Depends(get_cache_adapter),
) -> TemplateService:
    from app.application.services.template_service import TemplateService
    from app.infrastructure.persistence.template_repository_impl import TemplateRepositoryImpl

    return TemplateService(
        template_repo=TemplateRepositoryImpl(session),
        cache=cache,
    )


def get_membership_repo_scoped(
    session: AsyncSession = Depends(get_scoped_session),
) -> WorkspaceMembershipRepositoryImpl:
    """Membership repo bound to the workspace-scoped (RLS-applied) session."""
    return WorkspaceMembershipRepositoryImpl(session)


def get_membership_for_current_user(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> GetMembershipDep:
    """Return a callable that resolves the current user's membership in their workspace."""
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl as _MR,
    )

    return _MR(session)  # type: ignore[return-value]


async def get_callback_session() -> AsyncGenerator[AsyncSession]:
    """Unscoped (no RLS) session for the Dundun callback endpoint.

    The callback is authenticated via HMAC — there is no workspace context, so
    we cannot apply SET LOCAL app.current_workspace_id here.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_assistant_suggestion_repo(
    session: AsyncSession = Depends(get_callback_session),
) -> AssistantSuggestionRepositoryImpl:
    from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
        AssistantSuggestionRepositoryImpl,
    )

    return AssistantSuggestionRepositoryImpl(session)


def get_gap_finding_repo(
    session: AsyncSession = Depends(get_callback_session),
) -> GapFindingRepositoryImpl:
    from app.infrastructure.persistence.gap_finding_repository_impl import (
        GapFindingRepositoryImpl,
    )

    return GapFindingRepositoryImpl(session)
