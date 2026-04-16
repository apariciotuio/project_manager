"""Unit tests for SectionLock domain model — EP-17."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.models.section_lock import LockConflictError, SectionLock


def _make_lock(ttl: int = 30) -> SectionLock:
    return SectionLock.acquire(
        section_id=uuid4(),
        work_item_id=uuid4(),
        held_by=uuid4(),
        ttl_seconds=ttl,
    )


class TestSectionLockAcquire:
    def test_acquire_sets_fields(self) -> None:
        lock = _make_lock()
        assert lock.id is not None
        assert not lock.is_expired()

    def test_acquire_expires_after_ttl(self) -> None:
        lock = _make_lock(ttl=1)
        future = datetime.now(UTC) + timedelta(seconds=2)
        assert lock.is_expired(future)

    def test_acquire_not_expired_within_ttl(self) -> None:
        lock = _make_lock(ttl=60)
        assert not lock.is_expired()


class TestSectionLockHeartbeat:
    def test_heartbeat_extends_expiry(self) -> None:
        lock = _make_lock(ttl=5)
        original_expires = lock.expires_at
        lock.heartbeat(ttl_seconds=60)
        assert lock.expires_at > original_expires

    def test_heartbeat_updates_heartbeat_at(self) -> None:
        lock = _make_lock()
        old_hb = lock.heartbeat_at
        lock.heartbeat()
        assert lock.heartbeat_at >= old_hb


class TestSectionLockRelease:
    def test_release_by_owner_succeeds(self) -> None:
        owner = uuid4()
        lock = SectionLock.acquire(
            section_id=uuid4(),
            work_item_id=uuid4(),
            held_by=owner,
        )
        lock.release(owner)  # should not raise

    def test_release_by_non_owner_raises(self) -> None:
        lock = _make_lock()
        with pytest.raises(LockConflictError):
            lock.release(uuid4())

    def test_force_release_no_ownership_check(self) -> None:
        lock = _make_lock()
        lock.force_release()  # should not raise


class TestSectionLockExpiry:
    def test_is_expired_exactly_at_expiry(self) -> None:
        lock = _make_lock(ttl=10)
        # Exactly at expires_at
        assert lock.is_expired(lock.expires_at)

    def test_is_expired_before_expiry(self) -> None:
        lock = _make_lock(ttl=10)
        before = lock.expires_at - timedelta(seconds=1)
        assert not lock.is_expired(before)
