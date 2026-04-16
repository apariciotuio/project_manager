"""Unit tests for the Session domain entity."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.domain.models.session import Session


class TestHashToken:
    def test_sha256_hex_of_raw_token(self) -> None:
        raw = "opaque-refresh-token-xyz"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert Session.hash_token(raw) == expected

    def test_different_inputs_produce_different_hashes(self) -> None:
        assert Session.hash_token("a") != Session.hash_token("b")

    def test_rejects_empty_token(self) -> None:
        with pytest.raises(ValueError, match="token"):
            Session.hash_token("")


class TestCreate:
    def test_creates_session_with_hashed_token(self) -> None:
        user_id = uuid4()
        raw = "super-secret-refresh"
        session = Session.create(
            user_id=user_id,
            raw_token=raw,
            ttl_seconds=2592000,
            ip_address="10.0.0.1",
            user_agent="pytest",
        )

        assert isinstance(session.id, UUID)
        assert session.user_id == user_id
        assert session.token_hash == hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert session.raw_token_not_stored() is True
        assert session.expires_at.tzinfo is not None
        assert session.revoked_at is None
        assert session.ip_address == "10.0.0.1"
        assert session.user_agent == "pytest"

    def test_expires_at_respects_ttl(self) -> None:
        session = Session.create(
            user_id=uuid4(),
            raw_token="t",
            ttl_seconds=60,
            ip_address=None,
            user_agent=None,
        )
        delta = session.expires_at - session.created_at
        assert 59 <= delta.total_seconds() <= 61

    def test_rejects_non_positive_ttl(self) -> None:
        with pytest.raises(ValueError, match="ttl"):
            Session.create(
                user_id=uuid4(),
                raw_token="t",
                ttl_seconds=0,
                ip_address=None,
                user_agent=None,
            )


class TestLifecycle:
    def _session(self, *, expires_in: int = 60, revoked: bool = False) -> Session:
        session = Session.create(
            user_id=uuid4(),
            raw_token="tok",
            ttl_seconds=expires_in if expires_in > 0 else 1,
            ip_address=None,
            user_agent=None,
        )
        if expires_in <= 0:
            session.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        if revoked:
            session.revoke()
        return session

    def test_fresh_session_is_active(self) -> None:
        s = self._session()
        assert s.is_expired() is False
        assert s.is_revoked() is False
        assert s.is_active() is True

    def test_expired_session_is_not_active(self) -> None:
        s = self._session(expires_in=-1)
        assert s.is_expired() is True
        assert s.is_active() is False

    def test_boundary_expires_at_equals_now_is_expired(self) -> None:
        s = self._session()
        s.expires_at = datetime.now(UTC)
        assert s.is_expired() is True

    def test_revoke_sets_timestamp(self) -> None:
        s = self._session()
        s.revoke()
        assert s.revoked_at is not None
        assert s.is_revoked() is True
        assert s.is_active() is False

    def test_revoke_is_idempotent(self) -> None:
        s = self._session()
        s.revoke()
        first = s.revoked_at
        s.revoke()
        assert s.revoked_at == first, "second revoke must not overwrite timestamp"
