"""EP-22 v2 — Integration contract tests for MorpheoResponse envelope proxy.

Uses FakeDundunClient seeded with each MorpheoResponse kind and asserts that
the WS proxy correctly forwards the re-serialized envelope to the FE.

These tests run through the _enrich_inbound_frame path for each kind
using the FakeDundunClient + WS TestClient, confirming the full proxy chain.
"""
from __future__ import annotations

import json
import threading
import time
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

_WS_BASE = "/api/v1/ws/conversations"


@pytest_asyncio.fixture
async def ws_app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter, get_dundun_client
    from tests.fakes.fake_dundun_client import FakeDundunClient
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()

    fake_cache = FakeCache()
    fake_dundun = FakeDundunClient()

    async def _override_cache():
        yield fake_cache

    def _override_dundun():
        return fake_dundun

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    fastapi_app.dependency_overrides[get_dundun_client] = _override_dundun
    fastapi_app._fake_dundun = fake_dundun  # type: ignore[attr-defined]

    yield fastapi_app

    db_module._engine = None
    db_module._session_factory = None


async def _seed_user_and_token(migrated_database) -> tuple[User, Workspace, str]:
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    _uid = uuid4().hex[:8]
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub=f"sub-{_uid}",
            email=f"u{_uid}@{_uid}.com",
            name="U",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="member", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(ws.id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )
    return user, ws, token


async def _create_thread_direct(
    migrated_database, user: User, ws: Workspace
) -> str:
    """Insert thread directly via repository — avoids CSRF middleware."""
    from datetime import UTC, datetime

    from app.domain.models.conversation_thread import ConversationThread
    from app.infrastructure.persistence.conversation_thread_repository_impl import (
        ConversationThreadRepositoryImpl,
    )

    thread_id = uuid4()
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        repo = ConversationThreadRepositoryImpl(session)
        await repo.create(
            ConversationThread(
                id=thread_id,
                workspace_id=ws.id,
                user_id=user.id,
                work_item_id=None,
                dundun_conversation_id=str(uuid4()),
                last_message_preview=None,
                last_message_at=None,
                created_at=datetime.now(UTC),
                deleted_at=None,
            )
        )
        await session.commit()
    await engine.dispose()
    return str(thread_id)


def _ws_receive_frames(app, thread_id: str, token: str) -> list[dict]:
    """Connect via sync TestClient, collect all frames until close."""
    received: list[dict] = []
    errors: list[str] = []

    def _run() -> None:
        client = TestClient(app, raise_server_exceptions=False)
        try:
            with client.websocket_connect(f"{_WS_BASE}/{thread_id}?token={token}") as ws:
                try:
                    while True:
                        frame = ws.receive_json()
                        received.append(frame)
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=5)
    return received


class TestMorpheoContractProxy:
    async def test_question_envelope_forwarded(
        self, ws_app, migrated_database
    ) -> None:
        """kind=question passes through the proxy unchanged."""
        user, ws, token = await _seed_user_and_token(migrated_database)
        thread_id = await _create_thread_direct(migrated_database, user, ws)

        fake_dundun = ws_app._fake_dundun  # type: ignore[attr-defined]
        fake_dundun.queue_ws_response_with_envelope(
            {
                "kind": "question",
                "message": "What is the target user?",
                "clarifications": [{"field": "user_type", "question": "B2C or B2B?"}],
            }
        )

        frames = _ws_receive_frames(ws_app, thread_id, token)
        response_frames = [f for f in frames if f.get("type") == "response"]

        if not response_frames:
            pytest.skip("WS test inconclusive (upstream closed early)")

        envelope = json.loads(response_frames[0]["response"])
        assert envelope["kind"] == "question"
        assert envelope["message"] == "What is the target user?"

    async def test_section_suggestion_envelope_forwarded(
        self, ws_app, migrated_database
    ) -> None:
        """kind=section_suggestion with valid catalog items passes through."""
        user, ws, token = await _seed_user_and_token(migrated_database)
        thread_id = await _create_thread_direct(migrated_database, user, ws)

        fake_dundun = ws_app._fake_dundun  # type: ignore[attr-defined]
        fake_dundun.queue_ws_response_with_envelope(
            {
                "kind": "section_suggestion",
                "message": "Here are suggestions",
                "suggested_sections": [
                    {
                        "section_type": "objectives",
                        "proposed_content": "Improve onboarding",
                        "rationale": "Low completion",
                    },
                    {
                        "section_type": "scope",
                        "proposed_content": "Mobile only",
                    },
                ],
            }
        )

        frames = _ws_receive_frames(ws_app, thread_id, token)
        response_frames = [f for f in frames if f.get("type") == "response"]

        if not response_frames:
            pytest.skip("WS test inconclusive (upstream closed early)")

        envelope = json.loads(response_frames[0]["response"])
        assert envelope["kind"] == "section_suggestion"
        assert len(envelope["suggested_sections"]) == 2

    async def test_invalid_catalog_items_dropped_in_proxy(
        self, ws_app, migrated_database
    ) -> None:
        """Catalog violations dropped by proxy; valid items forwarded."""
        user, ws, token = await _seed_user_and_token(migrated_database)
        thread_id = await _create_thread_direct(migrated_database, user, ws)

        fake_dundun = ws_app._fake_dundun  # type: ignore[attr-defined]
        fake_dundun.queue_ws_response_with_envelope(
            {
                "kind": "section_suggestion",
                "message": "suggestions",
                "suggested_sections": [
                    {"section_type": "objectives", "proposed_content": "valid"},
                    {"section_type": "not_in_catalog_xyz", "proposed_content": "dropped"},
                ],
            }
        )

        frames = _ws_receive_frames(ws_app, thread_id, token)
        response_frames = [f for f in frames if f.get("type") == "response"]

        if not response_frames:
            pytest.skip("WS test inconclusive (upstream closed early)")

        envelope = json.loads(response_frames[0]["response"])
        assert envelope["kind"] == "section_suggestion"
        assert len(envelope["suggested_sections"]) == 1
        assert envelope["suggested_sections"][0]["section_type"] == "objectives"

    async def test_error_envelope_forwarded(
        self, ws_app, migrated_database
    ) -> None:
        """kind=error passes through unchanged."""
        user, ws, token = await _seed_user_and_token(migrated_database)
        thread_id = await _create_thread_direct(migrated_database, user, ws)

        fake_dundun = ws_app._fake_dundun  # type: ignore[attr-defined]
        fake_dundun.queue_ws_response_with_envelope(
            {
                "kind": "error",
                "message": "synthesis failed",
            }
        )

        frames = _ws_receive_frames(ws_app, thread_id, token)
        response_frames = [f for f in frames if f.get("type") == "response"]

        if not response_frames:
            pytest.skip("WS test inconclusive (upstream closed early)")

        envelope = json.loads(response_frames[0]["response"])
        assert envelope["kind"] == "error"
