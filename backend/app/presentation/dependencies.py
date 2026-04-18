"""FastAPI dependency wiring for EP-00, EP-01, EP-02, EP-03 controllers.

Kept centralised so repos, services, and adapters share a single construction path.
Each request gets its own AsyncSession; services built on top of it are request-scoped.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.events.event_bus import EventBus, get_global_bus

if TYPE_CHECKING:
    from app.application.services.notification_service import ExtendedNotificationService
    from app.application.services.clarification_service import ClarificationService
    from app.application.services.ready_gate_service import ReadyGateService
    from app.application.services.review_request_service import ReviewRequestService
    from app.application.services.review_response_service import ReviewResponseService
    from app.application.services.validation_service import ValidationService
    from app.application.services.comment_service import CommentService
    from app.application.services.completeness_service import (
        CompletenessService,
        GapService,
    )
    from app.application.services.conversation_service import ConversationService
    from app.application.services.dependency_service import DependencyService
    from app.application.services.draft_service import DraftService
    from app.application.services.export_service import ExportService
    from app.application.services.integration_service import IntegrationService
    from app.application.services.next_step_service import NextStepService
    from app.application.services.project_service import ProjectService
    from app.application.services.puppet_sync_service import PuppetSyncService
    from app.application.services.review_service import ReviewService
    from app.application.services.section_service import SectionService
    from app.application.services.suggestion_service import SuggestionService
    from app.application.services.task_service import TaskService
    from app.application.services.team_service import NotificationService, TeamService
    from app.application.services.diff_service import DiffService
    from app.application.services.template_service import TemplateService
    from app.application.services.timeline_service import TimelineService
    from app.application.services.versioning_service import VersioningService
    from app.application.services.saved_search_service import SavedSearchService
    from app.application.services.search_service import SearchService
    from app.application.services.dashboard_service import DashboardService
    from app.application.services.person_dashboard_service import PersonDashboardService
    from app.application.services.team_dashboard_service import TeamDashboardService
    from app.application.services.pipeline_service import PipelineQueryService
    from app.application.services.kanban_service import KanbanService
    from app.application.services.inbox_service import InboxService
    from app.application.services.validation_rule_template_service import ValidationRuleTemplateService
    from app.domain.ports.cache import ICache
    from app.domain.ports.dundun import DundunClient
    from app.domain.repositories.timeline_repository import ITimelineEventRepository
    from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
        AssistantSuggestionRepositoryImpl,
    )
    from app.infrastructure.persistence.attachment_repository_impl import (
        AttachmentRepositoryImpl,
    )
    from app.infrastructure.persistence.conversation_thread_repository_impl import (
        ConversationThreadRepositoryImpl,
    )
    from app.infrastructure.persistence.gap_finding_repository_impl import (
        GapFindingRepositoryImpl,
    )
    from app.infrastructure.persistence.lock_repository_impl import (
        SectionLockRepositoryImpl,
    )
    from app.infrastructure.persistence.saved_search_repository_impl import (
        SavedSearchRepositoryImpl,
    )
    from app.infrastructure.persistence.tag_repository_impl import (
        TagRepositoryImpl,
        WorkItemTagRepositoryImpl,
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


@lru_cache(maxsize=1)
def _cached_jwt_adapter() -> JwtAdapter:
    settings = get_settings()
    return JwtAdapter(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        issuer=settings.auth.jwt_issuer,
        audience=settings.auth.jwt_audience,
    )


def get_jwt_adapter() -> JwtAdapter:
    """Return a process-wide shared JwtAdapter.

    JwtAdapter is stateless after construction (secret + algorithm pinned);
    sharing avoids per-request re-instantiation, which mattered most on the
    WS endpoint where the adapter was being constructed inside the handler.
    """
    return _cached_jwt_adapter()


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


def get_capability_repo(
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceMembershipRepositoryImpl:
    """Narrow repo handle for the ``require_capabilities`` FastAPI dependency.

    Returns the same ``WorkspaceMembershipRepositoryImpl`` as
    ``get_membership_repo`` — the capability dependency uses only the
    ``get_capabilities_for(user_id, workspace_id)`` method. A separate name
    keeps the override surface small for tests.
    """
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


def get_work_item_repo_scoped(
    session: AsyncSession = Depends(get_scoped_session),
) -> WorkItemRepositoryImpl:
    """WorkItemRepositoryImpl bound to the workspace-scoped (RLS-applied) session."""
    return WorkItemRepositoryImpl(session)


def get_work_item_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> WorkItemService:
    """Build WorkItemService for the current request with workspace-scoped session."""
    from app.application.services.ready_gate_service import ReadyGateService
    from app.infrastructure.persistence.review_repository_impl import (
        ValidationRequirementRepositoryImpl,
        ValidationStatusRepositoryImpl,
    )

    # AuditService.isolated() opens its own session per log_event() call so
    # that failure audit rows (written in the except block before re-raising)
    # are committed even when the main request session is rolled back.
    audit = AuditService.isolated(get_session_factory())
    ready_gate = ReadyGateService(
        requirement_repo=ValidationRequirementRepositoryImpl(session),
        status_repo=ValidationStatusRepositoryImpl(session),
    )
    return WorkItemService(
        work_items=WorkItemRepositoryImpl(session),
        users=UserRepositoryImpl(session),
        memberships=WorkspaceMembershipRepositoryImpl(session),
        audit=audit,
        events=get_global_bus(),
        ready_gate=ready_gate,
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


_IN_MEMORY_CACHE: ICache | None = None


async def get_cache_adapter() -> AsyncGenerator[ICache]:
    """Yield the singleton InMemoryCacheAdapter for the lifetime of the request.

    Tests override this dep with a FakeCache injected directly.
    """
    global _IN_MEMORY_CACHE
    if _IN_MEMORY_CACHE is None:
        from app.infrastructure.adapters.in_memory_cache_adapter import (
            InMemoryCacheAdapter,
        )
        _IN_MEMORY_CACHE = InMemoryCacheAdapter()
    yield _IN_MEMORY_CACHE


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


# ---------------------------------------------------------------------------
# EP-03 — Dundun client, Conversation, Suggestion, Clarification
# ---------------------------------------------------------------------------


def get_dundun_client() -> DundunClient:
    """Construct the Dundun client from settings.

    Tests override this dep via app.dependency_overrides to inject FakeDundunClient.
    When settings.dundun.use_fake is True the test conftest override takes precedence.
    """
    from app.config.settings import get_settings
    from app.infrastructure.adapters.dundun_http_client import DundunHTTPClient

    s = get_settings()
    return DundunHTTPClient(  # type: ignore[return-value]
        base_url=s.dundun.base_url,
        service_key=s.dundun.service_key,
        http_timeout=s.dundun.http_timeout,
    )


def get_conversation_thread_repo(
    session: AsyncSession = Depends(get_scoped_session),
) -> ConversationThreadRepositoryImpl:
    from app.infrastructure.persistence.conversation_thread_repository_impl import (
        ConversationThreadRepositoryImpl,
    )

    return ConversationThreadRepositoryImpl(session)


def get_conversation_service(
    session: AsyncSession = Depends(get_scoped_session),
    dundun: DundunClient = Depends(get_dundun_client),
) -> ConversationService:
    from app.application.services.conversation_service import ConversationService
    from app.infrastructure.persistence.conversation_thread_repository_impl import (
        ConversationThreadRepositoryImpl,
    )

    return ConversationService(
        thread_repo=ConversationThreadRepositoryImpl(session),
        dundun_client=dundun,
    )


def get_suggestion_service(
    session: AsyncSession = Depends(get_scoped_session),
    dundun: DundunClient = Depends(get_dundun_client),
    current_user: CurrentUser = Depends(get_current_user),
) -> SuggestionService:
    from app.application.services.section_service import SectionService
    from app.application.services.suggestion_service import SuggestionService
    from app.application.services.versioning_service import VersioningService
    from app.config.settings import get_settings
    from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
        AssistantSuggestionRepositoryImpl,
    )
    from app.infrastructure.persistence.section_repository_impl import (
        SectionRepositoryImpl,
        SectionVersionRepositoryImpl,
    )
    from app.infrastructure.persistence.task_node_repository_impl import TaskNodeRepositoryImpl
    from app.infrastructure.persistence.work_item_version_repository_impl import (
        WorkItemVersionRepositoryImpl,
    )

    versioning = VersioningService(
        session=session,
        repo=WorkItemVersionRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
        section_repo=SectionRepositoryImpl(session),
        task_node_repo=TaskNodeRepositoryImpl(session),
    )
    section_svc = SectionService(
        section_repo=SectionRepositoryImpl(session),
        section_version_repo=SectionVersionRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
        versioning_service=versioning,
    )
    s = get_settings()
    return SuggestionService(
        suggestion_repo=AssistantSuggestionRepositoryImpl(session),
        dundun_client=dundun,
        callback_url=s.dundun.callback_url,
        section_service=section_svc,
        versioning_service=versioning,
        workspace_id=current_user.workspace_id,
    )


def get_clarification_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: ICache = Depends(get_cache_adapter),
    dundun: DundunClient = Depends(get_dundun_client),
) -> ClarificationService:
    from app.application.services.clarification_service import ClarificationService
    from app.config.settings import get_settings
    from app.domain.gap_detection.gap_detector import GapDetector
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl

    s = get_settings()
    return ClarificationService(
        gap_detector=GapDetector(),
        work_item_repo=WorkItemRepositoryImpl(session),
        dundun_client=dundun,
        cache=cache,
        callback_url=s.dundun.callback_url,
    )


# ---------------------------------------------------------------------------
# EP-04 — Section, Completeness, Gaps
# ---------------------------------------------------------------------------


def get_section_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: ICache = Depends(get_cache_adapter),
) -> SectionService:
    from app.application.services.section_service import SectionService
    from app.application.services.versioning_service import VersioningService
    from app.infrastructure.persistence.section_repository_impl import (
        SectionRepositoryImpl,
        SectionVersionRepositoryImpl,
    )
    from app.infrastructure.persistence.task_node_repository_impl import TaskNodeRepositoryImpl
    from app.infrastructure.persistence.work_item_version_repository_impl import (
        WorkItemVersionRepositoryImpl,
    )

    versioning = VersioningService(
        session=session,
        repo=WorkItemVersionRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
        section_repo=SectionRepositoryImpl(session),
        task_node_repo=TaskNodeRepositoryImpl(session),
    )
    return SectionService(
        section_repo=SectionRepositoryImpl(session),
        section_version_repo=SectionVersionRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
        cache=cache,
        versioning_service=versioning,
    )


def get_completeness_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: ICache = Depends(get_cache_adapter),
) -> CompletenessService:
    from app.application.services.completeness_service import CompletenessService
    from app.infrastructure.persistence.section_repository_impl import (
        SectionRepositoryImpl,
        ValidatorRepositoryImpl,
    )
    from app.infrastructure.persistence.task_node_repository_impl import TaskNodeRepositoryImpl

    return CompletenessService(
        work_item_repo=WorkItemRepositoryImpl(session),
        section_repo=SectionRepositoryImpl(session),
        validator_repo=ValidatorRepositoryImpl(session),
        cache=cache,
        task_node_repo=TaskNodeRepositoryImpl(session),
    )


def get_gap_service(
    completeness: CompletenessService = Depends(get_completeness_service),
) -> GapService:
    from app.application.services.completeness_service import GapService

    return GapService(completeness)


def get_next_step_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: ICache = Depends(get_cache_adapter),
) -> NextStepService:
    from app.application.services.completeness_service import CompletenessService, GapService
    from app.application.services.next_step_service import NextStepService
    from app.infrastructure.persistence.section_repository_impl import (
        SectionRepositoryImpl,
        ValidatorRepositoryImpl,
    )
    from app.infrastructure.persistence.task_node_repository_impl import TaskNodeRepositoryImpl

    completeness = CompletenessService(
        work_item_repo=WorkItemRepositoryImpl(session),
        section_repo=SectionRepositoryImpl(session),
        validator_repo=ValidatorRepositoryImpl(session),
        cache=cache,
        task_node_repo=TaskNodeRepositoryImpl(session),
    )
    gap_svc = GapService(completeness)
    return NextStepService(
        work_item_repo=WorkItemRepositoryImpl(session),
        completeness_service=completeness,
        gap_service=gap_svc,
    )


async def get_thread_repo_for_ws() -> AsyncGenerator[ConversationThreadRepositoryImpl]:
    """Yield an unscoped thread repo for WS handshake.

    RLS is not applied — ownership is enforced by `user_id` match in the controller.
    Async generator so the session stays open for the duration of the lookup.
    """
    from app.infrastructure.persistence.conversation_thread_repository_impl import (
        ConversationThreadRepositoryImpl,
    )
    from app.infrastructure.persistence.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        yield ConversationThreadRepositoryImpl(session)


# ---------------------------------------------------------------------------
# EP-05 — Task hierarchy + dependencies
# ---------------------------------------------------------------------------


def get_task_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: ICache = Depends(get_cache_adapter),
) -> TaskService:
    from app.application.services.task_service import TaskService
    from app.infrastructure.persistence.task_node_repository_impl import (
        TaskDependencyRepositoryImpl,
        TaskNodeRepositoryImpl,
        TaskSectionLinkRepositoryImpl,
    )

    return TaskService(
        node_repo=TaskNodeRepositoryImpl(session),
        dep_repo=TaskDependencyRepositoryImpl(session),
        link_repo=TaskSectionLinkRepositoryImpl(session),
        cache=cache,
    )


def get_dependency_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> DependencyService:
    from app.application.services.dependency_service import DependencyService
    from app.infrastructure.persistence.task_node_repository_impl import (
        TaskDependencyRepositoryImpl,
        TaskNodeRepositoryImpl,
    )

    return DependencyService(
        node_repo=TaskNodeRepositoryImpl(session),
        dep_repo=TaskDependencyRepositoryImpl(session),
    )


# ---------------------------------------------------------------------------
# EP-06 — Reviews + Validation
# ---------------------------------------------------------------------------


def get_review_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> ReviewService:
    """Legacy stub — kept for backward compat with existing controller wiring."""
    from app.application.services.review_service import ReviewService
    from app.infrastructure.persistence.review_repository_impl import (
        ReviewRequestRepositoryImpl,
        ReviewResponseRepositoryImpl,
    )

    return ReviewService(
        review_request_repo=ReviewRequestRepositoryImpl(session),
        review_response_repo=ReviewResponseRepositoryImpl(session),
    )


def get_review_request_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> ReviewRequestService:
    from app.application.services.review_request_service import ReviewRequestService
    from app.infrastructure.persistence.review_repository_impl import (
        ReviewRequestRepositoryImpl,
        ReviewResponseRepositoryImpl,
    )

    return ReviewRequestService(
        review_request_repo=ReviewRequestRepositoryImpl(session),
        review_response_repo=ReviewResponseRepositoryImpl(session),
        events=EventBus(),
    )


def get_review_response_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> ReviewResponseService:
    from app.application.services.review_response_service import ReviewResponseService
    from app.infrastructure.persistence.review_repository_impl import (
        ReviewRequestRepositoryImpl,
        ReviewResponseRepositoryImpl,
    )

    return ReviewResponseService(
        review_request_repo=ReviewRequestRepositoryImpl(session),
        review_response_repo=ReviewResponseRepositoryImpl(session),
        events=EventBus(),
    )


def get_validation_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> ValidationService:
    from app.application.services.validation_service import ValidationService
    from app.infrastructure.persistence.review_repository_impl import (
        ReviewRequestRepositoryImpl,
        ValidationRequirementRepositoryImpl,
        ValidationStatusRepositoryImpl,
    )

    return ValidationService(
        requirement_repo=ValidationRequirementRepositoryImpl(session),
        status_repo=ValidationStatusRepositoryImpl(session),
        review_request_repo=ReviewRequestRepositoryImpl(session),
        events=EventBus(),
    )


def get_ready_gate_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> ReadyGateService:
    from app.application.services.ready_gate_service import ReadyGateService
    from app.infrastructure.persistence.review_repository_impl import (
        ValidationRequirementRepositoryImpl,
        ValidationStatusRepositoryImpl,
    )

    return ReadyGateService(
        requirement_repo=ValidationRequirementRepositoryImpl(session),
        status_repo=ValidationStatusRepositoryImpl(session),
    )


# ---------------------------------------------------------------------------
# EP-07 — Comments + Timeline
# ---------------------------------------------------------------------------


def get_comment_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> CommentService:
    from app.application.services.comment_service import CommentService
    from app.infrastructure.persistence.comment_repository_impl import (
        CommentRepositoryImpl,
    )
    from app.infrastructure.persistence.timeline_repository_impl import (
        TimelineEventRepositoryImpl,
    )

    return CommentService(
        comment_repo=CommentRepositoryImpl(session),
        timeline_repo=TimelineEventRepositoryImpl(session),
    )


def get_timeline_repo(
    session: AsyncSession = Depends(get_scoped_session),
) -> ITimelineEventRepository:
    from app.infrastructure.persistence.timeline_repository_impl import (
        TimelineEventRepositoryImpl,
    )

    return TimelineEventRepositoryImpl(session)


async def get_conversation_service_for_ws(user: object) -> ConversationService:  # noqa: ARG001
    """Build ConversationService for the WS path (no FastAPI DI available there)."""
    from app.application.services.conversation_service import ConversationService
    from app.infrastructure.persistence.conversation_thread_repository_impl import (
        ConversationThreadRepositoryImpl,
    )
    from app.infrastructure.persistence.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        dundun = get_dundun_client()
        return ConversationService(
            thread_repo=ConversationThreadRepositoryImpl(session),
            dundun_client=dundun,
        )


# ---------------------------------------------------------------------------
# EP-13 — Puppet sync
# ---------------------------------------------------------------------------


def get_puppet_sync_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> PuppetSyncService:
    from app.application.services.puppet_sync_service import PuppetSyncService
    from app.infrastructure.persistence.puppet_outbox_repository_impl import (
        PuppetOutboxRepositoryImpl,
    )

    return PuppetSyncService(outbox_repo=PuppetOutboxRepositoryImpl(session))


# ---------------------------------------------------------------------------
# EP-15 — Tags
# ---------------------------------------------------------------------------


def get_tag_repo(
    session: AsyncSession = Depends(get_scoped_session),
) -> TagRepositoryImpl:
    from app.infrastructure.persistence.tag_repository_impl import TagRepositoryImpl

    return TagRepositoryImpl(session)


def get_work_item_tag_repo(
    session: AsyncSession = Depends(get_scoped_session),
) -> WorkItemTagRepositoryImpl:
    from app.infrastructure.persistence.tag_repository_impl import WorkItemTagRepositoryImpl

    return WorkItemTagRepositoryImpl(session)


# ---------------------------------------------------------------------------
# EP-16 — Attachments
# ---------------------------------------------------------------------------


def get_attachment_repo(
    session: AsyncSession = Depends(get_scoped_session),
) -> AttachmentRepositoryImpl:
    from app.infrastructure.persistence.attachment_repository_impl import (
        AttachmentRepositoryImpl,
    )

    return AttachmentRepositoryImpl(session)


# ---------------------------------------------------------------------------
# EP-17 — Section locks
# ---------------------------------------------------------------------------


def get_lock_repo(
    session: AsyncSession = Depends(get_scoped_session),
) -> SectionLockRepositoryImpl:
    from app.infrastructure.persistence.lock_repository_impl import SectionLockRepositoryImpl

    return SectionLockRepositoryImpl(session)


# ---------------------------------------------------------------------------
# EP-08 — Teams + Notifications
# ---------------------------------------------------------------------------


def get_team_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> TeamService:
    from app.application.services.team_service import TeamService
    from app.infrastructure.persistence.team_repository_impl import (
        TeamMembershipRepositoryImpl,
        TeamRepositoryImpl,
    )

    return TeamService(
        team_repo=TeamRepositoryImpl(session),
        membership_repo=TeamMembershipRepositoryImpl(session),
    )


def get_notification_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> NotificationService:
    from app.application.services.team_service import NotificationService
    from app.infrastructure.persistence.team_repository_impl import (
        NotificationRepositoryImpl,
    )

    return NotificationService(
        notification_repo=NotificationRepositoryImpl(session),
    )


def get_extended_notification_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> "ExtendedNotificationService":
    from app.application.services.notification_service import ExtendedNotificationService
    from app.infrastructure.persistence.team_repository_impl import (
        NotificationRepositoryImpl,
    )

    return ExtendedNotificationService(
        notification_repo=NotificationRepositoryImpl(session),
    )


def get_inbox_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> "InboxService":
    from app.application.services.inbox_service import InboxService
    from app.infrastructure.persistence.inbox_repository_impl import InboxRepositoryImpl

    return InboxService(inbox_repo=InboxRepositoryImpl(session))


# ---------------------------------------------------------------------------
# EP-09 — Saved Searches
# ---------------------------------------------------------------------------


def get_saved_search_repo(
    session: AsyncSession = Depends(get_scoped_session),
) -> SavedSearchRepositoryImpl:
    from app.infrastructure.persistence.saved_search_repository_impl import (
        SavedSearchRepositoryImpl,
    )

    return SavedSearchRepositoryImpl(session)


def get_saved_search_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> "SavedSearchService":
    from app.application.services.saved_search_service import SavedSearchService
    from app.infrastructure.persistence.saved_search_repository_impl import (
        SavedSearchRepositoryImpl,
    )

    return SavedSearchService(repo=SavedSearchRepositoryImpl(session))


def get_dashboard_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: "ICache" = Depends(get_cache_adapter),
) -> "DashboardService":
    from app.application.services.dashboard_service import DashboardService
    return DashboardService(session=session, cache=cache)


def get_person_dashboard_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: "ICache" = Depends(get_cache_adapter),
) -> "PersonDashboardService":
    from app.application.services.person_dashboard_service import PersonDashboardService
    return PersonDashboardService(session=session, cache=cache)


def get_team_dashboard_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: "ICache" = Depends(get_cache_adapter),
) -> "TeamDashboardService":
    from app.application.services.team_dashboard_service import TeamDashboardService
    return TeamDashboardService(session=session, cache=cache)


def get_pipeline_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: "ICache" = Depends(get_cache_adapter),
) -> "PipelineQueryService":
    from app.application.services.pipeline_service import PipelineQueryService
    return PipelineQueryService(session=session, cache=cache)


def get_kanban_service(
    session: AsyncSession = Depends(get_scoped_session),
    cache: "ICache" = Depends(get_cache_adapter),
) -> "KanbanService":
    from app.application.services.kanban_service import KanbanService
    return KanbanService(session=session, cache=cache)


def get_search_service() -> "SearchService":
    """Build SearchService with real or fake PuppetClient based on settings."""
    from app.application.services.search_service import SearchService

    settings = get_settings()
    if settings.puppet.use_fake:
        from tests.fakes.fake_puppet_client import FakePuppetClient
        puppet_client = FakePuppetClient()
    else:
        from app.infrastructure.adapters.puppet_http_client import PuppetHTTPClient
        puppet_client = PuppetHTTPClient(
            base_url=settings.puppet.base_url,
            api_key=settings.puppet.api_key,
        )
    return SearchService(puppet_client=puppet_client)


# ---------------------------------------------------------------------------
# EP-10 — Admin auth helpers
# ---------------------------------------------------------------------------


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """Require the current user to have admin role or is_superadmin.

    Loads the workspace membership from the DB to check role — JWT does not carry role.
    Returns the CurrentUser on success. Raises HTTP 403 on failure.
    This is a FastAPI dependency — testable via dependency_overrides.
    """
    from fastapi import HTTPException
    from fastapi import status as http_status
    from sqlalchemy import select

    from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM

    if current_user.workspace_id is None:
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
    # Superadmin bypasses all role checks
    if current_user.is_superadmin:
        return current_user

    # Check membership role from DB
    stmt = select(WorkspaceMembershipORM).where(
        WorkspaceMembershipORM.workspace_id == current_user.workspace_id,
        WorkspaceMembershipORM.user_id == current_user.id,
        WorkspaceMembershipORM.state == "active",
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None or row.role not in ("admin", "workspace_admin"):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ADMIN_REQUIRED",
                    "message": "admin role required",
                    "details": {},
                }
            },
        )
    return current_user


# ---------------------------------------------------------------------------
# EP-10 — Projects + Routing Rules
# ---------------------------------------------------------------------------


def get_project_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> ProjectService:
    from app.application.services.project_service import ProjectService
    from app.infrastructure.persistence.project_repository_impl import (
        ProjectRepositoryImpl,
        RoutingRuleRepositoryImpl,
    )

    return ProjectService(
        project_repo=ProjectRepositoryImpl(session),
        routing_rule_repo=RoutingRuleRepositoryImpl(session),
    )


def get_validation_rule_template_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> "ValidationRuleTemplateService":
    from app.application.services.validation_rule_template_service import (
        ValidationRuleTemplateService,
    )
    from app.infrastructure.persistence.validation_rule_template_repository_impl import (
        ValidationRuleTemplateRepositoryImpl,
    )

    return ValidationRuleTemplateService(
        repo=ValidationRuleTemplateRepositoryImpl(session)
    )


# ---------------------------------------------------------------------------
# EP-11 — Integrations
# ---------------------------------------------------------------------------


def get_audit_service(
    session: AsyncSession = Depends(get_db_session),
) -> AuditService:
    """Standalone AuditService dependency for controllers that emit audit events directly."""
    return AuditService(AuditRepositoryImpl(session))


def get_integration_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> IntegrationService:
    from app.application.services.integration_service import IntegrationService
    from app.infrastructure.persistence.integration_repository_impl import (
        IntegrationConfigRepositoryImpl,
        IntegrationExportRepositoryImpl,
    )

    return IntegrationService(
        config_repo=IntegrationConfigRepositoryImpl(session),
        export_repo=IntegrationExportRepositoryImpl(session),
    )


def get_export_service(
    session: AsyncSession = Depends(get_scoped_session),
    settings: Settings = Depends(get_settings),
) -> "ExportService":
    from app.application.services.audit_service import AuditService
    from app.application.services.export_service import ExportService
    from app.infrastructure.adapters.jira_adapter import JiraClient
    from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl

    jira_client = JiraClient(
        base_url=settings.jira.base_url,
        email=settings.jira.email,
        api_token=settings.jira.api_token.get_secret_value(),
    )
    audit = AuditService(AuditRepositoryImpl(session))
    return ExportService(
        work_item_repo=WorkItemRepositoryImpl(session),
        jira_client=jira_client,
        audit_service=audit,
    )


# ---------------------------------------------------------------------------
# EP-07 — Versioning + DiffService + TimelineService
# ---------------------------------------------------------------------------


def get_versioning_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> "VersioningService":
    from app.application.services.versioning_service import VersioningService
    from app.infrastructure.persistence.section_repository_impl import (
        SectionRepositoryImpl,
    )
    from app.infrastructure.persistence.task_node_repository_impl import (
        TaskNodeRepositoryImpl,
    )
    from app.infrastructure.persistence.work_item_repository_impl import (
        WorkItemRepositoryImpl,
    )
    from app.infrastructure.persistence.work_item_version_repository_impl import (
        WorkItemVersionRepositoryImpl,
    )

    return VersioningService(
        session=session,
        repo=WorkItemVersionRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
        section_repo=SectionRepositoryImpl(session),
        task_node_repo=TaskNodeRepositoryImpl(session),
    )


def get_diff_service() -> "DiffService":
    from app.application.services.diff_service import DiffService

    return DiffService()


def get_timeline_service(
    session: AsyncSession = Depends(get_scoped_session),
) -> "TimelineService":
    from app.application.services.timeline_service import TimelineService
    from app.infrastructure.persistence.timeline_repository_impl import (
        TimelineEventRepositoryImpl,
    )

    return TimelineService(timeline_repo=TimelineEventRepositoryImpl(session))
