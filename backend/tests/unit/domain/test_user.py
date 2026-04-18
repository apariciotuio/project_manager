"""Unit tests for the User domain entity.

TDD RED phase: these tests must fail before `app/domain/models/user.py` exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.domain.models.user import User


class TestFromGoogleClaims:
    def test_creates_user_with_all_fields(self) -> None:
        user = User.from_google_claims(
            sub="google-sub-123",
            email="alice@tuio.com",
            name="Alice Example",
            picture="https://example.com/a.png",
        )

        assert isinstance(user.id, UUID)
        assert user.google_sub == "google-sub-123"
        assert user.email == "alice@tuio.com"
        assert user.full_name == "Alice Example"
        assert user.avatar_url == "https://example.com/a.png"
        assert user.status == "active"
        assert user.is_superadmin is False
        assert isinstance(user.created_at, datetime)
        assert user.created_at.tzinfo is not None, "timestamps must be timezone-aware"
        assert user.updated_at == user.created_at

    def test_allows_missing_picture(self) -> None:
        user = User.from_google_claims(sub="sub", email="x@tuio.com", name="X", picture=None)
        assert user.avatar_url is None

    @pytest.mark.parametrize("bad_email", ["", None, "   ", "not-an-email", "@nodomain", "nouser@"])
    def test_rejects_invalid_email(self, bad_email: str | None) -> None:
        with pytest.raises(ValueError, match="email"):
            User.from_google_claims(sub="sub", email=bad_email, name="Name", picture=None)

    @pytest.mark.parametrize("bad_sub", ["", None, "   "])
    def test_rejects_missing_sub(self, bad_sub: str | None) -> None:
        with pytest.raises(ValueError, match="sub"):
            User.from_google_claims(sub=bad_sub, email="x@tuio.com", name="X", picture=None)

    @pytest.mark.parametrize("bad_name", ["", None, "   "])
    def test_rejects_empty_name(self, bad_name: str | None) -> None:
        with pytest.raises(ValueError, match="name"):
            User.from_google_claims(sub="sub", email="x@tuio.com", name=bad_name, picture=None)

    def test_normalizes_email_lowercase(self) -> None:
        user = User.from_google_claims(sub="sub", email="Alice@TUIO.com", name="A", picture=None)
        assert user.email == "alice@tuio.com"


class TestUpdateFromGoogle:
    def _sample(self) -> User:
        return User.from_google_claims(
            sub="sub-abc",
            email="alice@tuio.com",
            name="Alice",
            picture="https://a.example/pic.png",
        )

    def test_updates_name_and_avatar(self) -> None:
        user = self._sample()
        original_id = user.id
        original_sub = user.google_sub
        original_created = user.created_at

        user.update_from_google(name="Alice New", picture="https://a.example/new.png")

        assert user.full_name == "Alice New"
        assert user.avatar_url == "https://a.example/new.png"
        assert user.id == original_id
        assert user.google_sub == original_sub
        assert user.created_at == original_created
        assert user.updated_at >= original_created

    def test_picture_can_be_cleared(self) -> None:
        user = self._sample()
        user.update_from_google(name="Alice", picture=None)
        assert user.avatar_url is None

    def test_updating_name_to_empty_raises(self) -> None:
        user = self._sample()
        with pytest.raises(ValueError, match="name"):
            user.update_from_google(name="", picture=None)

    def test_update_refreshes_updated_at(self) -> None:
        user = self._sample()
        user.updated_at = datetime(2020, 1, 1, tzinfo=UTC)
        user.update_from_google(name="Alice", picture=None)
        assert user.updated_at.year >= 2026
