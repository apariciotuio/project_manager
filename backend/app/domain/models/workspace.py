"""Workspace domain entity — tenant boundary for all multi-tenant tables."""

from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

WorkspaceStatus = Literal["active", "suspended", "deleted"]

_PUBLIC_EMAIL_PROVIDERS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "ymail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "yandex.com",
        "yandex.ru",
    }
)

_PUBLIC_FALLBACK_NAME = "My Workspace"
_SLUG_SUFFIX_ALPHABET = string.ascii_lowercase + string.digits
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9-]+")
_DASH_RUNS = re.compile(r"-+")

# Compound second-level labels that should be skipped when picking the registrable name
# (e.g. "my-company.co.uk" → "my-company", not "co"). Not exhaustive — good enough for
# EP-00 bootstrap; full public-suffix logic lives in `tldextract` if we ever need it.
# NOTE: This hand-rolled list does not cover all PSL edge cases (e.g. foo.com.br);
# replace with `tldextract` if broad international domain coverage becomes needed.
_COMPOUND_SLDS = frozenset(
    {"co", "com", "net", "org", "gov", "edu", "ac", "or", "ne"}
)


def _now() -> datetime:
    return datetime.now(UTC)


def _extract_domain(email: str | None) -> str:
    if not email or "@" not in email:
        raise ValueError(f"email is not a valid address: {email!r}")
    local, _, domain = email.partition("@")
    if not local.strip() or not domain.strip():
        raise ValueError(f"email is not a valid address: {email!r}")
    return domain.strip().lower()


@dataclass
class Workspace:
    id: UUID
    name: str
    slug: str
    created_by: UUID
    status: WorkspaceStatus = "active"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @staticmethod
    def derive_name_from_domain(email: str | None) -> str:
        domain = _extract_domain(email)
        if domain in _PUBLIC_EMAIL_PROVIDERS:
            return _PUBLIC_FALLBACK_NAME
        parts = domain.split(".")
        if len(parts) >= 3 and parts[-2] in _COMPOUND_SLDS:
            head = parts[-3]
        elif len(parts) >= 2:
            head = parts[-2]
        else:
            head = parts[0]
        if not head:
            raise ValueError(f"cannot derive name from domain: {domain!r}")
        return "-".join(segment.capitalize() for segment in head.split("-"))

    @staticmethod
    def generate_slug(name: str, *, public_fallback: bool = False) -> str:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        base = name.strip().lower()
        base = _NON_SLUG_CHARS.sub("-", base)
        base = _DASH_RUNS.sub("-", base).strip("-")
        if not base:
            raise ValueError(f"cannot slugify name: {name!r}")
        if public_fallback:
            suffix = "".join(secrets.choice(_SLUG_SUFFIX_ALPHABET) for _ in range(6))
            return f"{base}-{suffix}"
        return base

    @classmethod
    def create_from_email(cls, *, email: str, created_by: UUID) -> Workspace:
        name = cls.derive_name_from_domain(email)
        public_fallback = name == _PUBLIC_FALLBACK_NAME
        slug = cls.generate_slug(name, public_fallback=public_fallback)
        now = _now()
        return cls(
            id=uuid4(),
            name=name,
            slug=slug,
            created_by=created_by,
            status="active",
            created_at=now,
            updated_at=now,
        )
