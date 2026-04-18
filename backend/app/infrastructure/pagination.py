"""Cursor-based pagination utility for SQLAlchemy 2.x synchronous sessions.

Cursor shape: opaque base64-encoded JSON {"id": "<uuid>", "created_at": "<iso>"}
Keyset order: (created_at DESC, id DESC) — stable for concurrent inserts with
ties on the same timestamp.

Usage::

    stmt = select(WorkItemORM)
    result = paginate(stmt, session=session, cursor=None, page_size=20)
    # result.rows, result.has_next, result.next_cursor (str | None)

    if result.next_cursor:
        cursor = PaginationCursor.decode(result.next_cursor)
        result2 = paginate(stmt, session=session, cursor=cursor, page_size=20)
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 20


class InvalidCursorError(ValueError):
    """Raised when a cursor token cannot be decoded or is structurally invalid."""


@dataclass(frozen=True)
class PaginationCursor:
    """Immutable boundary marker for keyset pagination."""

    id: UUID
    created_at: datetime

    def encode(self) -> str:
        payload = json.dumps(
            {
                "id": str(self.id),
                "created_at": self.created_at.isoformat(),
            }
        )
        return base64.b64encode(payload.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> PaginationCursor:
        try:
            raw = base64.b64decode(token.encode())
            data = json.loads(raw)
            item_id = UUID(data["id"])
            created_at = datetime.fromisoformat(data["created_at"])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
        except (KeyError, ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
            raise InvalidCursorError(f"Invalid pagination cursor: {exc}") from exc
        return cls(id=item_id, created_at=created_at)


@dataclass
class PaginationResult:
    rows: Sequence[Any]
    has_next: bool
    next_cursor: str | None


def paginate(
    stmt: sa.Select,
    *,
    session: Session,
    cursor: PaginationCursor | None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> PaginationResult:
    """Execute *stmt* with keyset pagination.

    Args:
        stmt: Base SELECT statement against an ORM model that has ``id`` and
            ``created_at`` columns.
        session: Synchronous SQLAlchemy Session.
        cursor: Boundary from the previous page, or None for the first page.
        page_size: Number of rows per page. Must be 1–100 inclusive.

    Returns:
        PaginationResult with rows, has_next flag, and next_cursor token.

    Raises:
        ValueError: If page_size is outside [1, 100].
    """
    if page_size < 1 or page_size > _MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {_MAX_PAGE_SIZE}, got {page_size}")

    # Determine the entity class from the statement's froms so we can
    # reference its columns without coupling to a specific ORM class.
    froms = stmt.froms
    if not froms:
        raise ValueError("Statement must select from at least one table")
    table = froms[0]

    id_col = table.c.id
    created_at_col = table.c.created_at

    # Apply keyset WHERE clause when a cursor is provided.
    if cursor is not None:
        # Rows strictly before the cursor in (created_at DESC, id DESC) order:
        # (created_at < cursor.created_at)
        # OR (created_at = cursor.created_at AND id < cursor.id)
        stmt = stmt.where(
            sa.or_(
                created_at_col < cursor.created_at,
                sa.and_(
                    created_at_col == cursor.created_at,
                    id_col < str(cursor.id),
                ),
            )
        )

    # Fetch page_size + 1 to detect whether a next page exists.
    stmt = stmt.order_by(created_at_col.desc(), id_col.desc()).limit(page_size + 1)

    rows = session.execute(stmt).scalars().all()

    has_next = len(rows) > page_size
    if has_next:
        rows = rows[:page_size]

    next_cursor: str | None = None
    if has_next and rows:
        last = rows[-1]
        next_cursor = PaginationCursor(
            id=UUID(str(last.id)),
            created_at=last.created_at
            if last.created_at.tzinfo is not None
            else last.created_at.replace(tzinfo=UTC),
        ).encode()

    return PaginationResult(rows=rows, has_next=has_next, next_cursor=next_cursor)
