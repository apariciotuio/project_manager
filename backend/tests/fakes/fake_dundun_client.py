"""Backwards-compat shim — the canonical source moved to app.infrastructure.fakes.

All new code should import from:
    from app.infrastructure.fakes.fake_dundun_client import FakeDundunClient
"""

from app.infrastructure.fakes.fake_dundun_client import FakeDundunClient  # noqa: F401

__all__ = ["FakeDundunClient"]
