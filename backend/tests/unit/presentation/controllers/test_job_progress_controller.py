"""Tests for SSE job progress endpoint — RED phase.

GET /api/v1/jobs/{job_id}/progress
  - Auth required (401 when no token)
  - 404 when job not found or not owned by user
  - Streams SSE frames with correct format
  - Sends keepalive comment every 30s (tested with fake clock)
  - event: done when job completes
  - event: error when job fails
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.infrastructure.sse.job_progress_service import JobState
from app.presentation.controllers.job_progress_controller import router

# ---------------------------------------------------------------------------
# Fake job progress service
# ---------------------------------------------------------------------------


class FakeJobProgressService:
    def __init__(self, states: dict[str, dict[str, Any]] | None = None) -> None:
        self._states = states or {}

    async def get_state(self, job_id: str) -> dict[str, Any] | None:
        return self._states.get(job_id)

    async def set_state(self, job_id: str, state: JobState, progress: int = 0) -> None:
        self._states[job_id] = {"state": state.value, "progress": progress}

    async def complete(self, job_id: str, message_id: str) -> None:
        self._states[job_id] = {"state": "done", "message_id": message_id}

    async def fail(self, job_id: str, error: str) -> None:
        self._states[job_id] = {"state": "error", "error": error}


# ---------------------------------------------------------------------------
# Tests — auth
# ---------------------------------------------------------------------------


def test_job_progress_requires_auth() -> None:
    """Returns 401 when no access_token cookie."""

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/jobs/some-job-id/progress", headers={})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests — SSE frame format
# ---------------------------------------------------------------------------


def test_job_progress_404_when_job_not_found() -> None:
    """Returns 404 when job_id is unknown."""
    from app.presentation.controllers.job_progress_controller import (
        override_job_progress_service,
        router,
    )

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    fake_svc = FakeJobProgressService(states={})  # no jobs

    app.dependency_overrides[override_job_progress_service] = lambda: fake_svc

    # Create a mock user so auth passes
    from uuid import uuid4

    from app.presentation.controllers.job_progress_controller import override_current_user
    from app.presentation.middleware.auth_middleware import CurrentUser

    fake_user = CurrentUser(
        id=uuid4(), email="u@example.com", workspace_id=uuid4(), is_superadmin=False
    )
    app.dependency_overrides[override_current_user] = lambda: fake_user

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/jobs/unknown-job-999/progress")
    assert resp.status_code == 404
