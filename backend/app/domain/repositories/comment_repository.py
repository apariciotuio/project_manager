"""EP-07 — Repository interface for Comment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.comment import Comment


class ICommentRepository(ABC):
    @abstractmethod
    async def create(self, comment: Comment) -> Comment: ...

    @abstractmethod
    async def get(self, comment_id: UUID) -> Comment | None: ...

    @abstractmethod
    async def list_for_work_item(self, work_item_id: UUID) -> list[Comment]: ...

    @abstractmethod
    async def save(self, comment: Comment) -> Comment: ...
