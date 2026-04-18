"""Job progress service — reads/writes Celery job state in Redis.

Keys: job:{job_id}  TTL: 3600s (1h after last update)
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Protocol


class JobState(str, Enum):  # noqa: UP042 — StrEnum is Python 3.11+; keep str+Enum for 3.10 compat
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class _RedisProto(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def setex(self, key: str, ttl: int, value: str) -> None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...


_JOB_TTL = 3600


class JobProgressService:
    def __init__(self, redis: _RedisProto) -> None:
        self._redis = redis

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    async def get_state(self, job_id: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._key(job_id))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def set_state(self, job_id: str, state: JobState, progress: int = 0) -> None:
        data = {"state": state.value, "progress": progress}
        await self._redis.setex(self._key(job_id), _JOB_TTL, json.dumps(data))

    async def complete(self, job_id: str, message_id: str) -> None:
        data = {"state": JobState.DONE.value, "message_id": message_id}
        await self._redis.setex(self._key(job_id), _JOB_TTL, json.dumps(data))

    async def fail(self, job_id: str, error: str) -> None:
        data = {"state": JobState.ERROR.value, "error": error}
        await self._redis.setex(self._key(job_id), _JOB_TTL, json.dumps(data))
