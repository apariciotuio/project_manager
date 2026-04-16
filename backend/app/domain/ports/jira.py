"""EP-11 — JiraClient protocol."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JiraError(Exception):
    pass


class JiraAuthError(JiraError):
    pass


class JiraRateLimitError(JiraError):
    pass


class JiraClient(ABC):
    @abstractmethod
    async def get_issue(self, key: str) -> dict[str, Any]: ...

    @abstractmethod
    async def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def update_issue(self, key: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def ping(self) -> bool: ...
