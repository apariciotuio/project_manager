"""Unit tests for the Workspace domain entity."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

import pytest

from app.domain.models.workspace import Workspace


class TestDeriveNameFromDomain:
    @pytest.mark.parametrize(
        "email,expected",
        [
            ("alice@acme.io", "Acme"),
            ("bob@ACME.io", "Acme"),
            ("c@my-company.co.uk", "My-Company"),
            ("d@foo-bar.tech", "Foo-Bar"),
            ("e@sub.example.com", "Example"),
        ],
    )
    def test_company_domain_returns_title_cased_name(self, email: str, expected: str) -> None:
        assert Workspace.derive_name_from_domain(email) == expected

    @pytest.mark.parametrize(
        "email",
        [
            "u@gmail.com",
            "u@googlemail.com",
            "u@yahoo.com",
            "u@ymail.com",
            "u@outlook.com",
            "u@hotmail.com",
            "u@live.com",
            "u@msn.com",
            "u@icloud.com",
            "u@me.com",
            "u@mac.com",
            "u@aol.com",
            "u@proton.me",
            "u@protonmail.com",
            "u@yandex.com",
        ],
    )
    def test_public_provider_returns_fallback(self, email: str) -> None:
        assert Workspace.derive_name_from_domain(email) == "My Workspace"

    @pytest.mark.parametrize("bad", ["", None, "no-at-sign", "@nodomain", "user@"])
    def test_rejects_malformed_email(self, bad: str | None) -> None:
        with pytest.raises(ValueError):
            Workspace.derive_name_from_domain(bad)


class TestGenerateSlug:
    def test_company_slug_is_deterministic(self) -> None:
        assert Workspace.generate_slug("Acme") == "acme"
        assert Workspace.generate_slug("My-Company") == "my-company"
        assert Workspace.generate_slug("  Trim  Me  ") == "trim-me"
        assert Workspace.generate_slug("Foo & Bar") == "foo-bar"

    def test_public_fallback_slug_has_random_suffix(self) -> None:
        slug_a = Workspace.generate_slug("My Workspace", public_fallback=True)
        slug_b = Workspace.generate_slug("My Workspace", public_fallback=True)
        assert slug_a != slug_b, "fallback slugs must not collide"
        assert re.fullmatch(r"my-workspace-[a-z0-9]{6}", slug_a), slug_a

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValueError, match="name"):
            Workspace.generate_slug("")


class TestCreate:
    def test_create_from_email(self) -> None:
        creator = uuid4()
        ws = Workspace.create_from_email(email="alice@acme.io", created_by=creator)

        assert isinstance(ws.id, UUID)
        assert ws.name == "Acme"
        assert ws.slug == "acme"
        assert ws.created_by == creator
        assert ws.status == "active"
        assert ws.created_at == ws.updated_at
        assert ws.created_at.tzinfo is not None

    def test_create_from_email_with_public_provider_uses_fallback(self) -> None:
        ws = Workspace.create_from_email(email="bob@gmail.com", created_by=uuid4())
        assert ws.name == "My Workspace"
        assert ws.slug.startswith("my-workspace-")
        assert len(ws.slug) == len("my-workspace-") + 6
