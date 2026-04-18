"""In-memory fakes of EP-00 repositories for unit tests.

Not mocks — full behavioral implementations against a dict so AuthService can be
exercised end-to-end without touching SQLAlchemy or Postgres. Mirrors the contract
of the real SQLAlchemy impls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.domain.models.audit_event import AuditEvent
from app.domain.models.session import Session
from app.domain.models.user import User
from app.domain.models.work_item import WorkItem
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.domain.queries.page import Page
from app.domain.queries.work_item_filters import WorkItemFilters
from app.domain.queries.work_item_list_filters import WorkItemListFilters
from app.domain.repositories.audit_repository import IAuditRepository
from app.domain.repositories.oauth_state_repository import (
    ConsumedOAuthState,
    IOAuthStateRepository,
)
from app.domain.repositories.session_repository import ISessionRepository
from app.domain.repositories.user_repository import IUserRepository
from app.domain.repositories.work_item_repository import IWorkItemRepository
from app.domain.repositories.workspace_membership_repository import (
    IWorkspaceMembershipRepository,
)
from app.domain.repositories.workspace_repository import IWorkspaceRepository
from app.domain.value_objects.ownership_record import OwnershipRecord
from app.domain.value_objects.state_transition import StateTransition
from app.infrastructure.pagination import PaginationCursor, PaginationResult


class FakeUserRepository(IUserRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        return next((u for u in self._by_id.values() if u.google_sub == google_sub), None)

    async def get_by_email(self, email: str) -> User | None:
        target = email.lower()
        return next((u for u in self._by_id.values() if u.email == target), None)

    async def upsert(self, user: User) -> User:
        existing = await self.get_by_google_sub(user.google_sub)
        if existing:
            existing.email = user.email
            existing.full_name = user.full_name
            existing.avatar_url = user.avatar_url
            existing.status = user.status
            existing.is_superadmin = user.is_superadmin
            existing.updated_at = user.updated_at
            return existing
        self._by_id[user.id] = user
        return user


class FakeSessionRepository(ISessionRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, Session] = {}

    async def create(self, session: Session) -> Session:
        self._by_id[session.id] = session
        return session

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        return next(
            (s for s in self._by_id.values() if s.token_hash == token_hash), None
        )

    async def revoke(self, session_id: UUID) -> None:
        s = self._by_id.get(session_id)
        if s and s.revoked_at is None:
            s.revoke()

    async def delete_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired = [sid for sid, s in self._by_id.items() if s.expires_at < now]
        for sid in expired:
            del self._by_id[sid]
        return len(expired)


class FakeWorkspaceRepository(IWorkspaceRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, Workspace] = {}

    async def create(self, workspace: Workspace) -> Workspace:
        if any(w.slug == workspace.slug for w in self._by_id.values()):
            raise ValueError(f"duplicate slug: {workspace.slug}")
        self._by_id[workspace.id] = workspace
        return workspace

    async def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        return self._by_id.get(workspace_id)

    async def get_by_slug(self, slug: str) -> Workspace | None:
        return next((w for w in self._by_id.values() if w.slug == slug), None)

    async def slug_exists(self, slug: str) -> bool:
        return any(w.slug == slug for w in self._by_id.values())


class FakeWorkspaceMembershipRepository(IWorkspaceMembershipRepository):
    def __init__(self) -> None:
        self._rows: list[WorkspaceMembership] = []

    async def create(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        if any(
            m.workspace_id == membership.workspace_id and m.user_id == membership.user_id
            for m in self._rows
        ):
            raise ValueError("duplicate membership")
        self._rows.append(membership)
        return membership

    async def get_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        return [m for m in self._rows if m.user_id == user_id]

    async def get_active_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        return [m for m in self._rows if m.user_id == user_id and m.state == "active"]

    async def get_default_for_user(self, user_id: UUID) -> WorkspaceMembership | None:
        return next(
            (
                m
                for m in self._rows
                if m.user_id == user_id and m.state == "active" and m.is_default
            ),
            None,
        )


class FakeOAuthStateRepository(IOAuthStateRepository):
    def __init__(self) -> None:
        # state -> (verifier, expires_at, return_to, last_chosen_workspace_id)
        self._rows: dict[str, tuple[str, datetime, str | None, UUID | None]] = {}

    async def create(
        self,
        *,
        state: str,
        verifier: str,
        ttl_seconds: int,
        return_to: str | None = None,
        last_chosen_workspace_id: UUID | None = None,
    ) -> None:
        if state in self._rows:
            raise ValueError(f"duplicate state: {state}")
        from datetime import timedelta

        self._rows[state] = (
            verifier,
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            return_to,
            last_chosen_workspace_id,
        )

    async def consume(self, state: str) -> ConsumedOAuthState | None:
        row = self._rows.get(state)
        if row is None:
            return None
        verifier, expires_at, return_to, last_chosen_workspace_id = row
        del self._rows[state]
        if expires_at <= datetime.now(timezone.utc):
            return None
        return ConsumedOAuthState(
            verifier=verifier,
            return_to=return_to,
            last_chosen_workspace_id=last_chosen_workspace_id,
        )

    async def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired = [s for s, (_, exp, _, _) in self._rows.items() if exp < now]
        for s in expired:
            del self._rows[s]
        return len(expired)


class FakeWorkItemRepository(IWorkItemRepository):
    """In-memory IWorkItemRepository for unit tests.

    Keyed by (workspace_id, item_id). Tracks transitions and ownership records
    in plain lists — tests inspect these directly.
    """

    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], WorkItem] = {}
        self.transitions: list[StateTransition] = []
        self.ownership_records: list[OwnershipRecord] = []

    async def get(self, item_id: UUID, workspace_id: UUID) -> WorkItem | None:
        return self._items.get((workspace_id, item_id))

    async def exists_in_workspace(self, item_id: UUID, workspace_id: UUID) -> bool:
        return (workspace_id, item_id) in self._items

    async def list(
        self,
        workspace_id: UUID,
        project_id: UUID,
        filters: WorkItemFilters,
    ) -> Page[WorkItem]:
        rows = [
            item
            for (ws_id, _), item in self._items.items()
            if ws_id == workspace_id and item.project_id == project_id
        ]
        if not filters.include_deleted:
            rows = [r for r in rows if r.deleted_at is None]
        if filters.state is not None:
            rows = [r for r in rows if r.state == filters.state]
        if filters.type is not None:
            rows = [r for r in rows if r.type == filters.type]
        if filters.owner_id is not None:
            rows = [r for r in rows if r.owner_id == filters.owner_id]
        if filters.has_override is not None:
            rows = [r for r in rows if r.has_override == filters.has_override]
        total = len(rows)
        start = (filters.page - 1) * filters.page_size
        return Page(
            items=rows[start : start + filters.page_size],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    async def save(self, item: WorkItem, workspace_id: UUID) -> WorkItem:
        import copy

        saved = copy.deepcopy(item)
        self._items[(workspace_id, item.id)] = saved
        return saved

    async def delete(self, item_id: UUID, workspace_id: UUID) -> None:
        self._items.pop((workspace_id, item_id), None)

    async def record_transition(
        self, transition: StateTransition, workspace_id: UUID
    ) -> None:
        self.transitions.append(transition)

    async def record_ownership_change(
        self,
        record: OwnershipRecord,
        workspace_id: UUID,
        previous_owner_id: UUID | None = None,
    ) -> None:
        self.ownership_records.append(record)

    async def get_transitions(
        self, item_id: UUID, workspace_id: UUID
    ) -> list[StateTransition]:
        return sorted(
            [t for t in self.transitions if t.work_item_id == item_id],
            key=lambda t: t.triggered_at,
            reverse=True,
        )

    async def get_ownership_history(
        self, item_id: UUID, workspace_id: UUID
    ) -> list[OwnershipRecord]:
        return sorted(
            [r for r in self.ownership_records if r.work_item_id == item_id],
            key=lambda r: r.changed_at,
            reverse=True,
        )

    async def list_cursor(
        self,
        workspace_id: UUID,
        *,
        cursor: PaginationCursor | None,
        page_size: int,
        filters: WorkItemListFilters | None = None,
    ) -> PaginationResult:
        rows = [
            item
            for (ws_id, _), item in self._items.items()
            if ws_id == workspace_id and item.deleted_at is None
        ]
        # naive in-memory filtering
        if filters is not None:
            if getattr(filters, "parent_id", None) is not None:
                rows = [r for r in rows if r.parent_id == filters.parent_id]
            if getattr(filters, "type", None) is not None:
                rows = [r for r in rows if r.type == filters.type]
            if getattr(filters, "state", None) is not None:
                rows = [r for r in rows if r.state == filters.state]
            if getattr(filters, "owner_id", None) is not None:
                rows = [r for r in rows if r.owner_id == filters.owner_id]
        rows = sorted(rows, key=lambda r: (r.created_at, r.id), reverse=True)
        if cursor is not None:
            rows = [
                r
                for r in rows
                if (r.created_at, r.id) < (cursor.created_at, cursor.id)
            ]
        has_next = len(rows) > page_size
        page = rows[:page_size]
        next_cursor: str | None = None
        if has_next and page:
            last = page[-1]
            next_cursor = PaginationCursor(id=last.id, created_at=last.created_at).encode()
        return PaginationResult(rows=page, has_next=has_next, next_cursor=next_cursor)


class FakeAuditRepository(IAuditRepository):
    def __init__(self, *, explode: bool = False) -> None:
        self.events: list[AuditEvent] = []
        self._explode = explode

    async def append(self, event: AuditEvent) -> AuditEvent:
        if self._explode:
            raise RuntimeError("simulated audit DB failure")
        self.events.append(event)
        return event

    async def list_cursor(
        self,
        workspace_id: UUID,
        *,
        cursor: PaginationCursor | None,
        page_size: int,
        category: str | None = None,
        action: str | None = None,
    ) -> PaginationResult:
        rows = [e for e in self.events if e.workspace_id == workspace_id]
        if category is not None:
            rows = [e for e in rows if e.category == category]
        if action is not None:
            rows = [e for e in rows if e.action == action]
        rows = sorted(rows, key=lambda e: (e.created_at, e.id), reverse=True)
        if cursor is not None:
            rows = [
                e
                for e in rows
                if (e.created_at, e.id) < (cursor.created_at, cursor.id)
            ]
        has_next = len(rows) > page_size
        page = rows[:page_size]
        next_cursor: str | None = None
        if has_next and page:
            last = page[-1]
            next_cursor = PaginationCursor(id=last.id, created_at=last.created_at).encode()
        return PaginationResult(rows=page, has_next=has_next, next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# EP-02 fakes
# ---------------------------------------------------------------------------


class FakeCache:
    """In-memory ICache for unit tests. Tracks call counts for assertions."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.get_call_count: int = 0
        self.set_call_count: int = 0
        self.delete_call_count: int = 0

    async def get(self, key: str) -> str | None:
        self.get_call_count += 1
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.set_call_count += 1
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self.delete_call_count += 1
        self._store.pop(key, None)

    def seed(self, key: str, value: str) -> None:
        """Directly seed the cache for test setup without counting the call."""
        self._store[key] = value


class FakeWorkItemDraftRepository:
    """In-memory IWorkItemDraftRepository for unit tests."""

    def __init__(self) -> None:
        from app.domain.models.work_item_draft import WorkItemDraft
        from app.domain.value_objects.draft_conflict import DraftConflict

        self._by_user_workspace: dict[tuple, WorkItemDraft] = {}

    async def upsert(self, draft: object, expected_version: int) -> object:
        from app.domain.models.work_item_draft import WorkItemDraft
        from app.domain.value_objects.draft_conflict import DraftConflict

        assert isinstance(draft, WorkItemDraft)
        key = (draft.user_id, draft.workspace_id)
        existing = self._by_user_workspace.get(key)

        if existing is not None and existing.local_version > expected_version:
            return DraftConflict(
                server_version=existing.local_version,
                server_data=existing.data,
            )

        import copy
        from datetime import UTC, datetime, timedelta

        new_version = (existing.local_version + 1) if existing is not None else 1
        now = datetime.now(UTC)
        updated = WorkItemDraft(
            id=existing.id if existing else draft.id,
            user_id=draft.user_id,
            workspace_id=draft.workspace_id,
            data=dict(draft.data),
            local_version=new_version,
            incomplete=draft.incomplete,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            expires_at=now + timedelta(days=30),
        )
        self._by_user_workspace[key] = updated
        return updated

    async def get_by_user_workspace(self, user_id: object, workspace_id: object) -> object:
        return self._by_user_workspace.get((user_id, workspace_id))

    async def delete(self, draft_id: object, user_id: object) -> None:
        from app.domain.exceptions import DraftForbiddenError, WorkItemDraftNotFoundError
        from uuid import UUID

        assert isinstance(draft_id, UUID)
        assert isinstance(user_id, UUID)

        for key, draft in list(self._by_user_workspace.items()):
            if draft.id == draft_id:
                if draft.user_id != user_id:
                    raise DraftForbiddenError(user_id, draft_id)
                del self._by_user_workspace[key]
                return
        raise WorkItemDraftNotFoundError(draft_id)

    async def get_expired(self) -> list:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return [d for d in self._by_user_workspace.values() if d.expires_at < now]

    async def delete_expired(self) -> int:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        expired_keys = [k for k, d in self._by_user_workspace.items() if d.expires_at < now]
        for k in expired_keys:
            del self._by_user_workspace[k]
        return len(expired_keys)


# ---------------------------------------------------------------------------
# EP-03 fakes
# ---------------------------------------------------------------------------


class FakeGapFindingRepository:
    """In-memory IGapFindingRepository for unit tests."""

    def __init__(self) -> None:
        from app.domain.models.gap_finding import StoredGapFinding

        self._rows: list[StoredGapFinding] = []

    async def insert_many(self, findings: list) -> list:
        self._rows.extend(findings)
        return list(findings)

    async def get_active_for_work_item(
        self, work_item_id: UUID, source: str | None = None
    ) -> list:
        result = [
            f for f in self._rows
            if f.work_item_id == work_item_id and f.invalidated_at is None
        ]
        if source is not None:
            result = [f for f in result if f.source == source]
        return result

    async def invalidate_for_work_item(
        self, work_item_id: UUID, now: datetime, source: str | None = None
    ) -> int:
        import dataclasses

        count = 0
        for i, f in enumerate(self._rows):
            if f.work_item_id == work_item_id and f.invalidated_at is None:
                if source is None or f.source == source:
                    self._rows[i] = dataclasses.replace(f, invalidated_at=now)
                    count += 1
        return count


class FakeConversationThreadRepository:
    """In-memory IConversationThreadRepository for unit tests."""

    def __init__(self) -> None:
        from app.domain.models.conversation_thread import ConversationThread

        self._by_id: dict[UUID, ConversationThread] = {}

    async def create(self, thread: object) -> object:
        from app.domain.models.conversation_thread import ConversationThread

        assert isinstance(thread, ConversationThread)
        self._by_id[thread.id] = thread
        return thread

    async def get_by_id(self, thread_id: UUID) -> object:
        return self._by_id.get(thread_id)

    async def get_by_user_and_work_item(
        self, user_id: UUID, work_item_id: UUID | None
    ) -> object:
        for t in self._by_id.values():
            if t.user_id == user_id and t.work_item_id == work_item_id:
                return t
        return None

    async def get_by_dundun_conversation_id(self, dundun_conversation_id: str) -> object:
        return next(
            (t for t in self._by_id.values() if t.dundun_conversation_id == dundun_conversation_id),
            None,
        )

    async def list_for_user(
        self,
        user_id: UUID,
        work_item_id: UUID | None = None,
        include_archived: bool = False,
    ) -> list:
        rows = [t for t in self._by_id.values() if t.user_id == user_id]
        if work_item_id is not None:
            rows = [t for t in rows if t.work_item_id == work_item_id]
        if not include_archived:
            rows = [t for t in rows if t.deleted_at is None]
        return rows

    async def update(self, thread: object) -> object:
        from app.domain.models.conversation_thread import ConversationThread

        assert isinstance(thread, ConversationThread)
        self._by_id[thread.id] = thread
        return thread


class FakeAssistantSuggestionRepository:
    """In-memory IAssistantSuggestionRepository for unit tests."""

    def __init__(self) -> None:
        from app.domain.models.assistant_suggestion import AssistantSuggestion

        self._by_id: dict[UUID, AssistantSuggestion] = {}

    async def create_batch(self, suggestions: list) -> list:
        for s in suggestions:
            self._by_id[s.id] = s
        return list(suggestions)

    async def get_by_id(self, suggestion_id: UUID) -> object:
        return self._by_id.get(suggestion_id)

    async def get_by_batch_id(self, batch_id: UUID) -> list:
        return [s for s in self._by_id.values() if s.batch_id == batch_id]

    async def get_by_dundun_request_id(self, dundun_request_id: str) -> list:
        return [s for s in self._by_id.values() if s.dundun_request_id == dundun_request_id]

    async def list_pending_for_work_item(self, work_item_id: UUID) -> list:
        from app.domain.models.assistant_suggestion import SuggestionStatus
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return [
            s for s in self._by_id.values()
            if s.work_item_id == work_item_id
            and s.status == SuggestionStatus.PENDING
            and s.expires_at > now
        ]

    async def update_status(
        self, ids: list, status: object, now: datetime
    ) -> int:
        import dataclasses

        count = 0
        for sid in ids:
            s = self._by_id.get(sid)
            if s is not None:
                self._by_id[sid] = dataclasses.replace(s, status=status, updated_at=now)
                count += 1
        return count


class FakeTemplateRepository:
    """In-memory ITemplateRepository for unit tests."""

    def __init__(self) -> None:
        from app.domain.models.template import Template

        self._by_id: dict = {}

    def _all(self) -> list:
        return list(self._by_id.values())

    async def get_by_workspace_and_type(self, workspace_id: object, type: object) -> object:
        for tmpl in self._all():
            if tmpl.workspace_id == workspace_id and tmpl.type == type:
                return tmpl
        return None

    async def get_system_default(self, type: object) -> object:
        for tmpl in self._all():
            if tmpl.is_system and tmpl.type == type:
                return tmpl
        return None

    async def get_by_id(self, template_id: object) -> object:
        return self._by_id.get(template_id)

    async def create(self, template: object) -> object:
        from app.domain.exceptions import DuplicateTemplateError
        from app.domain.models.template import Template

        assert isinstance(template, Template)
        for tmpl in self._all():
            if (
                tmpl.workspace_id is not None
                and tmpl.workspace_id == template.workspace_id
                and tmpl.type == template.type
            ):
                from uuid import UUID
                ws_id = template.workspace_id if template.workspace_id else UUID(int=0)
                raise DuplicateTemplateError(ws_id, template.type.value)
        self._by_id[template.id] = template
        return template

    async def update(self, template_id: object, *, name: object, content: object) -> object:
        from datetime import UTC, datetime

        from app.domain.exceptions import TemplateNotFoundError

        tmpl = self._by_id.get(template_id)
        if tmpl is None:
            from uuid import UUID

            assert isinstance(template_id, UUID)
            raise TemplateNotFoundError(template_id)

        from dataclasses import replace

        updated = replace(
            tmpl,
            name=name if name is not None else tmpl.name,
            content=content if content is not None else tmpl.content,
            updated_at=datetime.now(UTC),
        )
        self._by_id[template_id] = updated
        return updated

    async def delete(self, template_id: object) -> None:
        from app.domain.exceptions import TemplateNotFoundError

        if template_id not in self._by_id:
            from uuid import UUID

            assert isinstance(template_id, UUID)
            raise TemplateNotFoundError(template_id)
        del self._by_id[template_id]

    async def list_for_workspace(self, workspace_id: object) -> list:
        return [t for t in self._all() if t.workspace_id == workspace_id]
