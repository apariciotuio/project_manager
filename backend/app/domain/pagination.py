"""EP-09 — Cursor-based pagination utilities.

Cursor encodes (sort_value, id) as base64(json). The sort_value is
serialized to ISO 8601 for datetime values, or the raw value for other types.

Tampered/invalid cursors raise ValueError — callers map that to HTTP 422.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PaginationCursor:
    sort_value: Any
    last_id: UUID

    def encode(self) -> str:
        payload = {
            "sv": self.sort_value.isoformat()
            if isinstance(self.sort_value, datetime)
            else self.sort_value,
            "id": str(self.last_id),
        }
        raw = json.dumps(payload, separators=(",", ":"))
        return base64.urlsafe_b64encode(raw.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> PaginationCursor:
        try:
            raw = base64.urlsafe_b64decode(token.encode()).decode()
            data = json.loads(raw)
            if "sv" not in data or "id" not in data:
                raise ValueError("missing required cursor fields")
            return cls(sort_value=data["sv"], last_id=UUID(data["id"]))
        except Exception as exc:
            raise ValueError(f"invalid cursor: {exc}") from exc
