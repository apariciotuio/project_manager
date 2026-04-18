"""In-memory job progress service.

Keys: job_id (str)  TTL: 3600s (1h after last write, evicted lazily on read)

Replaces the Redis-backed JobProgressService. Job state is ephemeral and
acceptable to lose on restart (<100 concurrent jobs, single Uvicorn worker).

Public API is identical to the previous implementation so callers require
no changes.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any


class JobState(str, Enum):  # noqa: UP042 — StrEnum is Python 3.11+; keep str+Enum for 3.10 compat
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_JOB_TTL = 3600  # seconds


class _Entry:
    __slots__ = ("data", "expires_at")

    def __init__(self, data: dict[str, Any], ttl: int) -> None:
        self.data = data
        self.expires_at = time.monotonic() + ttl


class JobProgressService:
    """In-memory job state store with TTL eviction.

    Thread-safety: asyncio single-threaded — dict ops are atomic enough.
    """

    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self, job_id: str, data: dict[str, Any]) -> None:
        self._store[job_id] = _Entry(data, _JOB_TTL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_state(self, job_id: str) -> dict[str, Any] | None:
        entry = self._store.get(job_id)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[job_id]
            return None
        return entry.data

    async def set_state(self, job_id: str, state: JobState, progress: int = 0) -> None:
        self._write(job_id, {"state": state.value, "progress": progress})

    async def complete(self, job_id: str, message_id: str) -> None:
        self._write(job_id, {"state": JobState.DONE.value, "message_id": message_id})

    async def fail(self, job_id: str, error: str) -> None:
        self._write(job_id, {"state": JobState.ERROR.value, "error": error})
