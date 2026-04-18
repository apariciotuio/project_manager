"""ConversationThread domain entity — pure, no I/O. History owned by Dundun."""
from __future__ import annotations

import dataclasses
from datetime import datetime
from uuid import UUID


@dataclasses.dataclass
class ConversationThread:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    work_item_id: UUID | None
    dundun_conversation_id: str
    last_message_preview: str | None
    last_message_at: datetime | None
    created_at: datetime
    deleted_at: datetime | None
    primer_sent_at: datetime | None = None

    @property
    def is_archived(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_general_thread(self) -> bool:
        return self.work_item_id is None

    @property
    def is_primed(self) -> bool:
        return self.primer_sent_at is not None

    def archive(self, now: datetime) -> ConversationThread:
        if self.is_archived:
            return self
        return dataclasses.replace(self, deleted_at=now)

    def mark_primer_sent(self, now: datetime) -> ConversationThread:
        """Return new immutable instance with primer_sent_at set."""
        return dataclasses.replace(self, primer_sent_at=now)
