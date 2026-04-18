"""Unit tests for PaginationCursor and paginate() utility.

RED phase: all tests must fail before implementation exists.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest
import sqlalchemy as sa
from sqlalchemy import String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Minimal in-memory ORM fixture
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class ItemORM(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


@pytest.fixture(scope="module")
def sync_engine():
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session(sync_engine):
    from sqlalchemy.orm import Session

    with Session(sync_engine) as s:
        s.query(ItemORM).delete()
        s.commit()
        yield s


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def _seed(session, items: list[dict]) -> None:
    """Insert items and commit."""
    for item in items:
        session.add(ItemORM(**item))
    session.commit()


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from app.infrastructure.pagination import (  # noqa: E402
    InvalidCursorError,
    PaginationCursor,
    PaginationResult,
    paginate,
)

# ---------------------------------------------------------------------------
# PaginationCursor encode / decode round-trip
# ---------------------------------------------------------------------------


class TestPaginationCursorRoundTrip:
    def test_encode_decode_roundtrip(self):
        item_id = uuid.uuid4()
        dt = _dt("2024-03-15T10:30:00")
        cursor = PaginationCursor(id=item_id, created_at=dt)

        token = cursor.encode()
        decoded = PaginationCursor.decode(token)

        assert decoded.id == item_id
        assert decoded.created_at == dt

    def test_encode_produces_str(self):
        cursor = PaginationCursor(id=uuid.uuid4(), created_at=_dt("2024-01-01T00:00:00"))
        assert isinstance(cursor.encode(), str)

    def test_encode_is_opaque_base64(self):
        import base64

        cursor = PaginationCursor(id=uuid.uuid4(), created_at=_dt("2024-01-01T00:00:00"))
        token = cursor.encode()
        # Must be valid base64 (no exception)
        base64.b64decode(token)
        # Must NOT be plain JSON visible
        assert "{" not in token

    def test_different_ids_produce_different_tokens(self):
        dt = _dt("2024-01-01T00:00:00")
        t1 = PaginationCursor(id=uuid.uuid4(), created_at=dt).encode()
        t2 = PaginationCursor(id=uuid.uuid4(), created_at=dt).encode()
        assert t1 != t2


class TestPaginationCursorInvalid:
    def test_garbage_string_raises(self):
        with pytest.raises(InvalidCursorError):
            PaginationCursor.decode("not-a-cursor")

    def test_valid_base64_but_wrong_json_raises(self):
        import base64
        import json

        bad = base64.b64encode(json.dumps({"wrong": "keys"}).encode()).decode()
        with pytest.raises(InvalidCursorError):
            PaginationCursor.decode(bad)

    def test_invalid_uuid_in_cursor_raises(self):
        import base64
        import json

        bad = base64.b64encode(
            json.dumps({"id": "not-a-uuid", "created_at": "2024-01-01T00:00:00+00:00"}).encode()
        ).decode()
        with pytest.raises(InvalidCursorError):
            PaginationCursor.decode(bad)

    def test_invalid_datetime_in_cursor_raises(self):
        import base64
        import json

        bad = base64.b64encode(
            json.dumps({"id": str(uuid.uuid4()), "created_at": "not-a-date"}).encode()
        ).decode()
        with pytest.raises(InvalidCursorError):
            PaginationCursor.decode(bad)


# ---------------------------------------------------------------------------
# page_size validation
# ---------------------------------------------------------------------------


class TestPageSizeValidation:
    def test_page_size_zero_raises(self, session):
        stmt = sa.select(ItemORM)
        with pytest.raises(ValueError, match="page_size"):
            paginate(stmt, session=session, cursor=None, page_size=0)

    def test_page_size_above_max_raises(self, session):
        stmt = sa.select(ItemORM)
        with pytest.raises(ValueError, match="page_size"):
            paginate(stmt, session=session, cursor=None, page_size=101)

    def test_page_size_100_is_valid(self, session):
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None, page_size=100)
        assert isinstance(result, PaginationResult)

    def test_page_size_default_is_20(self, session):
        # Seed 25 items
        _seed(
            session,
            [
                {
                    "id": str(uuid.uuid4()),
                    "created_at": _dt(f"2024-01-{i:02d}T00:00:00"),
                    "name": f"item-{i}",
                }
                for i in range(1, 26)
            ],
        )
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None)
        assert len(result.rows) == 20

    def test_page_size_negative_raises(self, session):
        stmt = sa.select(ItemORM)
        with pytest.raises(ValueError, match="page_size"):
            paginate(stmt, session=session, cursor=None, page_size=-1)


# ---------------------------------------------------------------------------
# paginate() first page — no cursor
# ---------------------------------------------------------------------------


class TestPaginateFirstPage:
    def test_first_page_returns_correct_count(self, session):
        ids = [str(uuid.uuid4()) for _ in range(5)]
        _seed(
            session,
            [
                {
                    "id": ids[i],
                    "created_at": _dt(f"2024-01-{i + 1:02d}T00:00:00"),
                    "name": f"item-{i}",
                }
                for i in range(5)
            ],
        )
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None, page_size=3)
        assert len(result.rows) == 3

    def test_first_page_has_next_when_more(self, session):
        _seed(
            session,
            [
                {
                    "id": str(uuid.uuid4()),
                    "created_at": _dt(f"2024-02-{i + 1:02d}T00:00:00"),
                    "name": f"x-{i}",
                }
                for i in range(5)
            ],
        )
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None, page_size=3)
        assert result.has_next is True
        assert result.next_cursor is not None

    def test_first_page_no_next_when_fits(self, session):
        _seed(
            session,
            [
                {
                    "id": str(uuid.uuid4()),
                    "created_at": _dt(f"2024-03-{i + 1:02d}T00:00:00"),
                    "name": f"y-{i}",
                }
                for i in range(3)
            ],
        )
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None, page_size=5)
        assert result.has_next is False
        assert result.next_cursor is None

    def test_first_page_order_is_desc(self, session):
        ids = [str(uuid.uuid4()) for _ in range(4)]
        _seed(
            session,
            [
                {"id": ids[0], "created_at": _dt("2024-04-01T00:00:00"), "name": "oldest"},
                {"id": ids[1], "created_at": _dt("2024-04-02T00:00:00"), "name": "middle"},
                {"id": ids[2], "created_at": _dt("2024-04-03T00:00:00"), "name": "newer"},
                {"id": ids[3], "created_at": _dt("2024-04-04T00:00:00"), "name": "newest"},
            ],
        )
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None, page_size=4)
        names = [r.name for r in result.rows]
        assert names == ["newest", "newer", "middle", "oldest"]


# ---------------------------------------------------------------------------
# paginate() second page — keyset cursor
# ---------------------------------------------------------------------------


class TestPaginateSecondPage:
    def test_second_page_returns_correct_items(self, session):
        """Cursor from page 1 must return non-overlapping page 2."""
        ids = [str(uuid.uuid4()) for _ in range(6)]
        _seed(
            session,
            [
                {
                    "id": ids[i],
                    "created_at": _dt(f"2024-05-{i + 1:02d}T00:00:00"),
                    "name": f"p-{i}",
                }
                for i in range(6)
            ],
        )
        stmt = sa.select(ItemORM)
        page1 = paginate(stmt, session=session, cursor=None, page_size=3)
        assert page1.has_next is True

        cursor = PaginationCursor.decode(page1.next_cursor)
        page2 = paginate(stmt, session=session, cursor=cursor, page_size=3)

        page1_names = {r.name for r in page1.rows}
        page2_names = {r.name for r in page2.rows}
        assert page1_names.isdisjoint(page2_names), "Pages must not overlap"
        assert len(page2.rows) == 3

    def test_second_page_no_next_when_last(self, session):
        ids = [str(uuid.uuid4()) for _ in range(4)]
        _seed(
            session,
            [
                {
                    "id": ids[i],
                    "created_at": _dt(f"2024-06-{i + 1:02d}T00:00:00"),
                    "name": f"q-{i}",
                }
                for i in range(4)
            ],
        )
        stmt = sa.select(ItemORM)
        page1 = paginate(stmt, session=session, cursor=None, page_size=3)
        cursor = PaginationCursor.decode(page1.next_cursor)
        page2 = paginate(stmt, session=session, cursor=cursor, page_size=3)

        assert page2.has_next is False
        assert page2.next_cursor is None

    def test_keyset_boundary_excludes_cursor_row(self, session):
        """The row at the cursor boundary must not appear in the next page."""
        ids = [str(uuid.uuid4()) for _ in range(5)]
        _seed(
            session,
            [
                {
                    "id": ids[i],
                    "created_at": _dt(f"2024-07-{i + 1:02d}T00:00:00"),
                    "name": f"r-{i}",
                }
                for i in range(5)
            ],
        )
        stmt = sa.select(ItemORM)
        page1 = paginate(stmt, session=session, cursor=None, page_size=2)
        boundary_ids = {str(r.id) for r in page1.rows}

        cursor = PaginationCursor.decode(page1.next_cursor)
        page2 = paginate(stmt, session=session, cursor=cursor, page_size=3)
        page2_ids = {str(r.id) for r in page2.rows}

        assert boundary_ids.isdisjoint(page2_ids)

    def test_all_pages_together_cover_all_rows(self, session):
        """Walking all pages must yield every row exactly once."""
        ids = [str(uuid.uuid4()) for _ in range(7)]
        _seed(
            session,
            [
                {
                    "id": ids[i],
                    "created_at": _dt(f"2024-08-{i + 1:02d}T00:00:00"),
                    "name": f"s-{i}",
                }
                for i in range(7)
            ],
        )
        stmt = sa.select(ItemORM)
        all_rows = []
        cursor = None
        while True:
            result = paginate(stmt, session=session, cursor=cursor, page_size=3)
            all_rows.extend(result.rows)
            if not result.has_next:
                break
            cursor = PaginationCursor.decode(result.next_cursor)

        assert len(all_rows) == 7
        assert len({str(r.id) for r in all_rows}) == 7  # no duplicates


# ---------------------------------------------------------------------------
# PaginationResult shape
# ---------------------------------------------------------------------------


class TestPaginationResultShape:
    def test_result_has_rows_has_next_next_cursor(self, session):
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None, page_size=20)
        assert hasattr(result, "rows")
        assert hasattr(result, "has_next")
        assert hasattr(result, "next_cursor")

    def test_next_cursor_is_none_when_no_next(self, session):
        stmt = sa.select(ItemORM)
        result = paginate(stmt, session=session, cursor=None, page_size=20)
        if not result.has_next:
            assert result.next_cursor is None
