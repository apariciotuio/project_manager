"""EP-09 — Unit tests for PaginationCursor encode/decode."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.pagination import PaginationCursor


def _dt() -> datetime:
    return datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)


class TestEncodeDecode:
    def test_roundtrip_datetime_sort_value(self) -> None:
        cursor = PaginationCursor(sort_value=_dt(), last_id=uuid4())
        decoded = PaginationCursor.decode(cursor.encode())
        # sort_value is stored as ISO string; last_id must round-trip
        assert str(decoded.last_id) == str(cursor.last_id)
        assert decoded.sort_value == cursor.sort_value.isoformat()

    def test_roundtrip_string_sort_value(self) -> None:
        uid = uuid4()
        cursor = PaginationCursor(sort_value="hello", last_id=uid)
        decoded = PaginationCursor.decode(cursor.encode())
        assert decoded.sort_value == "hello"
        assert decoded.last_id == uid

    def test_roundtrip_int_sort_value(self) -> None:
        uid = uuid4()
        cursor = PaginationCursor(sort_value=99, last_id=uid)
        decoded = PaginationCursor.decode(cursor.encode())
        assert decoded.sort_value == 99
        assert decoded.last_id == uid

    def test_different_ids_produce_different_tokens(self) -> None:
        dt = _dt()
        c1 = PaginationCursor(sort_value=dt, last_id=uuid4())
        c2 = PaginationCursor(sort_value=dt, last_id=uuid4())
        assert c1.encode() != c2.encode()


class TestTamperDetection:
    def test_garbage_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="invalid cursor"):
            PaginationCursor.decode("not-a-valid-cursor!!")

    def test_missing_id_field_raises_value_error(self) -> None:
        import base64
        import json
        payload = base64.urlsafe_b64encode(json.dumps({"sv": "2026"}).encode()).decode()
        with pytest.raises(ValueError, match="invalid cursor"):
            PaginationCursor.decode(payload)

    def test_missing_sv_field_raises_value_error(self) -> None:
        import base64
        import json
        uid = str(uuid4())
        payload = base64.urlsafe_b64encode(json.dumps({"id": uid}).encode()).decode()
        with pytest.raises(ValueError, match="invalid cursor"):
            PaginationCursor.decode(payload)

    def test_invalid_uuid_in_id_raises_value_error(self) -> None:
        import base64
        import json
        payload = base64.urlsafe_b64encode(json.dumps({"sv": "x", "id": "not-a-uuid"}).encode()).decode()
        with pytest.raises(ValueError, match="invalid cursor"):
            PaginationCursor.decode(payload)

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="invalid cursor"):
            PaginationCursor.decode("")
